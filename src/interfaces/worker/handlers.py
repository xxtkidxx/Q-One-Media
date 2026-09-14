"""Handler cho từng bước nặng, và dây nối giữa chúng.

Cách nối bước: mỗi handler xong thì **xếp việc tiếp theo** vào hàng đợi. Không
gọi trực tiếp handler sau, vì như vậy một job dài sẽ thành một transaction dài và
worker chết giữa đường là mất cả chuỗi. Xếp việc thì mỗi bước tự chịu trách nhiệm
và tự retry được.

Hai chỗ dây **cố tình đứt** — gate của người:

- sau ``transcribe`` → item vào ``transcript_review`` và dừng. Người soát xong thì
  web/API xếp việc ``pick_segment``.
- sau ``render`` → item vào ``human_review`` và dừng. Người duyệt xong thì việc
  ``publish`` mới được xếp.

Không có cách nào để dây tự nối qua hai chỗ đó.

Handler nhận ``UnitOfWork`` — **port của tầng application**, không phải
``SqlUnitOfWork`` cụ thể. Nhờ vậy tầng này không kéo theo SQLAlchemy, và bảng dây
nối test được bằng fake in-memory trong vài milligiây.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from src.application.ports import UnitOfWork
from src.application.use_cases.download_item import download_item
from src.application.use_cases.synthesize_voice import synthesize_voice
from src.application.use_cases.write_script import (
    load_glossary,
    pick_segment,
    save_transcript,
    transcript_dir,
    write_vietnamese_script,
)
from src.domain.production.value_objects import ItemStage
from src.domain.scheduling.entities import Job, JobTask
from src.infrastructure.clock import SystemClock
from src.shared.config import Settings
from src.shared.logging import get_logger

log = get_logger(__name__)

CLOCK = SystemClock()

# Bước nào xong thì xếp bước nào. Thiếu khoá = dây đứt có chủ ý (gate của người).
NEXT_TASK: dict[JobTask, JobTask | None] = {
    JobTask.DOWNLOAD: JobTask.SEPARATE,
    JobTask.SEPARATE: JobTask.TRANSCRIBE,
    JobTask.TRANSCRIBE: None,      # → transcript_review, chờ người
    JobTask.PICK_SEGMENT: JobTask.WRITE_SCRIPT,
    JobTask.WRITE_SCRIPT: JobTask.SYNTHESIZE,
    JobTask.SYNTHESIZE: JobTask.ALIGN,
    JobTask.ALIGN: JobTask.RENDER,
    JobTask.RENDER: None,          # → human_review, chờ người
    JobTask.PUBLISH: None,
}


def enqueue_next(job: Job, uow: UnitOfWork, *, item_id: int) -> None:
    """Xếp bước tiếp theo, nếu có."""
    nxt = NEXT_TASK.get(job.task)
    if nxt is None:
        log.info("worker.chain.stop", after=str(job.task), reason="gate của người hoặc kết thúc")
        return
    with uow:
        uow.jobs.enqueue(Job(task=nxt, item_id=item_id, priority=job.priority))
        uow.commit()
    log.info("worker.chain.next", after=str(job.task), next=str(nxt), item_id=item_id)


# ---------------- Từng bước ----------------


def handle_download(job: Job, uow: UnitOfWork, settings: Settings) -> None:
    from src.infrastructure.ingest.ytdlp import YtDlpDownloader, YtDlpProbe

    item_id = _need_item(job)
    download_item(
        item_id,
        downloader=YtDlpDownloader(),
        probe=YtDlpProbe(),
        media_root=settings.media_root,
        uow=uow,
        clock=CLOCK,
    )


def handle_separate(job: Job, uow: UnitOfWork, settings: Settings) -> None:
    """Tách stem: bỏ giọng, giữ tiếng máy."""
    from src.infrastructure.asr.demucs import separate
    from src.infrastructure.media import ffmpeg

    item_id = _need_item(job)
    with uow:
        item = uow.items.get(item_id)
        if item is None or item.path_source is None:
            raise ValueError(f"item #{item_id} chưa có file nguồn")
        source_path = settings.paths.absolute(item.path_source.relative_path)

    work = transcript_dir(settings.media_root, item_id)
    audio = ffmpeg.extract_audio(source_path, work / "source_audio.wav")
    separate(audio, work)

    with uow:
        item = uow.items.get(item_id)
        item.mark_separated()
        uow.items.update(item)
        uow.commit()


def handle_transcribe(job: Job, uow: UnitOfWork, settings: Settings) -> None:
    """Nhận dạng lời nguồn rồi **dừng ở gate người soát**.

    Chạy ASR trên stem giọng (đã bỏ nhạc/tiếng máy) nên transcript chính xác hơn
    hẳn so với chạy trên audio gốc.
    """
    from src.infrastructure.asr.whisperx import transcribe

    item_id = _need_item(job)
    with uow:
        item = uow.items.get(item_id)
        source = uow.sources.get(item.source_id) if item else None
        if item is None or source is None:
            raise ValueError(f"item #{item_id} hoặc nguồn của nó không tồn tại")
        language = source.audio_lang.base

    work = transcript_dir(settings.media_root, item_id)
    vocals = work / "vocals.wav"
    audio = vocals if vocals.exists() else work / "source_audio.wav"
    result = transcribe(audio, language=language)
    save_transcript(settings.media_root, item_id, text=result.text, segments=result.segments)

    with uow:
        item = uow.items.get(item_id)
        item.mark_transcribed()
        item.send_transcript_to_review()
        uow.items.update(item)
        uow.audit.record(
            entity="item",
            entity_id=item_id,
            action="transcribed",
            actor="worker",
            detail={"language": language, "chars": len(result.text)},
        )
        uow.commit()
    log.info(
        "worker.transcript.awaiting_review",
        item_id=item_id,
        language=language,
        note="nguồn zh cần soát kỹ hơn — CER ~12,8%",
    )


def handle_pick_segment(job: Job, uow: UnitOfWork, settings: Settings) -> None:
    from src.infrastructure.llm.claude import (
        ClaudeSegmentAdvisor,
        format_transcript_with_timestamps,
    )

    item_id = _need_item(job)
    pick_segment(
        item_id,
        advisor=ClaudeSegmentAdvisor(api_key=settings.llm.api_key, model=settings.llm.model),
        format_transcript=format_transcript_with_timestamps,
        media_root=settings.media_root,
        uow=uow,
        clock=CLOCK,
    )


def handle_write_script(job: Job, uow: UnitOfWork, settings: Settings) -> None:
    from src.infrastructure.llm.claude import ClaudeScriptWriter

    item_id = _need_item(job)
    with uow:
        item = uow.items.get(item_id)
        source = uow.sources.get(item.source_id) if item else None
        lang = source.audio_lang.base if source else "en"
        glossary = load_glossary(uow, lang)

    write_vietnamese_script(
        item_id,
        writer=ClaudeScriptWriter(api_key=settings.llm.api_key, model=settings.llm.model),
        speech_rate=settings.tts.measured_rate,
        glossary=glossary,
        media_root=settings.media_root,
        uow=uow,
        clock=CLOCK,
    )


def handle_synthesize(job: Job, uow: UnitOfWork, settings: Settings) -> None:
    """Lồng tiếng. Tràn ngân sách âm tiết thì item quay về bước viết lại."""
    from src.infrastructure.media import ffmpeg
    from src.infrastructure.tts.registry import build_synthesizer
    from src.infrastructure.tts.voxcpm import count_syllables

    class _Probe:
        def duration_sec(self, path: Path) -> float:
            return ffmpeg.probe(path).duration_sec

    item_id = _need_item(job)
    outcome = synthesize_voice(
        item_id,
        synthesizer=build_synthesizer(settings),
        probe=_Probe(),
        count_syllables=count_syllables,
        media_root=settings.media_root,
        uow=uow,
        clock=CLOCK,
    )
    if not outcome.voiced:
        # Kịch bản tràn khung → xếp lại việc VIẾT, không xếp việc lồng tiếng.
        # Nếu xếp sai thì vòng lặp vô hạn: lồng tiếng lại đúng kịch bản đã tràn.
        with uow:
            uow.jobs.enqueue(
                Job(task=JobTask.WRITE_SCRIPT, item_id=item_id, priority=job.priority)
            )
            uow.commit()
        log.info("worker.script.rewrite_queued", item_id=item_id, reason=outcome.reason)
        raise _ChainRedirected(outcome.reason or "kịch bản tràn ngân sách")


def handle_align(job: Job, uow: UnitOfWork, settings: Settings) -> None:
    """Forced alignment: kịch bản đã biết ↔ audio TTS → timing phụ đề."""
    import json

    from src.infrastructure.asr.align import align_known_text
    from src.infrastructure.asr.whisperx import group_words_into_cues

    item_id = _need_item(job)
    with uow:
        item = uow.items.get(item_id)
        if item is None or item.path_work is None or not item.script_vi:
            raise ValueError(f"item #{item_id} chưa có audio giọng hoặc kịch bản")
        voice = settings.paths.absolute(item.path_work.relative_path)
        script = item.script_vi

    words = align_known_text(voice, script, language="vi")
    cues = group_words_into_cues(words)
    work = transcript_dir(settings.media_root, item_id)
    (work / "cues.json").write_text(
        json.dumps([{"start": s, "end": e, "text": t} for s, e, t in cues],
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    with uow:
        item = uow.items.get(item_id)
        item.mark_aligned()
        uow.items.update(item)
        uow.audit.record(
            entity="item", entity_id=item_id, action="aligned", actor="worker",
            detail={"words": len(words), "cues": len(cues)},
        )
        uow.commit()


def handle_render(job: Job, uow: UnitOfWork, settings: Settings) -> None:
    """Dựng video thành phẩm rồi **dừng ở gate người duyệt**."""
    import json

    from src.domain.production.value_objects import MediaAsset
    from src.infrastructure.media.renderer import FfmpegRenderer, RenderRequest

    item_id = _need_item(job)
    with uow:
        item = uow.items.get(item_id)
        source = uow.sources.get(item.source_id) if item else None
        if item is None or source is None:
            raise ValueError(f"item #{item_id} hoặc nguồn không tồn tại")
        if item.path_source is None or item.path_work is None or item.segment is None:
            raise ValueError(f"item #{item_id} thiếu file nguồn, audio giọng, hoặc đoạn")
        source_video = settings.paths.absolute(item.path_source.relative_path)
        voice = settings.paths.absolute(item.path_work.relative_path)
        segment = item.segment
        aspect = item.aspect_ratio
        attribution = source.evidence.attribution_text if source.evidence else None

    work = transcript_dir(settings.media_root, item_id)
    cues_file = work / "cues.json"
    cues = (
        [(c["start"], c["end"], c["text"]) for c in json.loads(cues_file.read_text("utf-8"))]
        if cues_file.exists()
        else []
    )
    background = work / "background.wav"
    out_dir = settings.paths.output / f"item-{item_id:08d}"
    output = out_dir / "final.mp4"

    FfmpegRenderer().render(
        RenderRequest(
            source_video=source_video,
            voice_audio=voice,
            background_audio=background if background.exists() else None,
            subtitle_cues=cues,
            start_sec=segment.start_sec,
            end_sec=segment.end_sec,
            work_dir=work / "render",
            output=output,
            source_aspect=aspect,
            attribution_text=attribution,
            # fonts_dir=None có chủ ý: image worker cài font vào
            # /usr/share/fonts/truetype/qone/ rồi chạy fc-cache, nên libass tìm
            # thấy qua fontconfig. Truyền fontsdir lại làm libass BỎ QUA font hệ
            # thống và chỉ dùng thư mục đó.
        )
    )

    with uow:
        item = uow.items.get(item_id)
        # Đi qua ``mixed`` thật sự: renderer đã trộn audio trong cùng chuỗi, và
        # máy trạng thái không cho nhảy aligned → rendered. Ghi đúng từng bước
        # để dashboard nói đúng việc gì đã làm.
        item.mark_mixed()
        item.mark_rendered(path=MediaAsset(settings.paths.relative(output)))
        item.send_to_human_review()
        uow.items.update(item)
        uow.audit.record(
            entity="item", entity_id=item_id, action="rendered", actor="worker",
            detail={"output": settings.paths.relative(output)},
        )
        uow.commit()
    log.info("worker.render.awaiting_review", item_id=item_id)


def handle_publish(job: Job, uow: UnitOfWork, settings: Settings) -> None:
    """Đăng bài. Chỉ chạy với item đã ở ``approved`` — policy tự chặn nếu không."""
    from src.application.use_cases.publish_item import publish_item
    from src.domain.publishing.value_objects import VideoMetadata
    from src.infrastructure.publish.registry import build_publishers

    item_id = _need_item(job)
    publishers = build_publishers(settings)
    if not publishers:
        raise RuntimeError("chưa cấu hình nền tảng nào để đăng (G3.1 / G4.1)")

    with uow:
        item = uow.items.get(item_id)
        if item is None:
            raise ValueError(f"không có item #{item_id}")
        title = (item.title_original or f"Q One Media #{item_id}")[:100]
        description = item.script_vi or ""

    publish_item(
        item_id,
        metadata=VideoMetadata(title=title, description=description),
        publishers=publishers,
        media_root=settings.media_root,
        uow=uow,
        clock=CLOCK,
        enabled=settings.publish.enabled,
    )


class _ChainRedirected(RuntimeError):
    """Bước này không lỗi, nhưng chuỗi đã được chuyển hướng — đừng xếp bước sau."""

    retryable = False


def _need_item(job: Job) -> int:
    if job.item_id is None:
        raise ValueError(f"job {job.task} thiếu item_id")
    return job.item_id


Handler = Callable[[Job, UnitOfWork, Settings], None]

HANDLERS: dict[JobTask, Handler] = {
    JobTask.DOWNLOAD: handle_download,
    JobTask.SEPARATE: handle_separate,
    JobTask.TRANSCRIBE: handle_transcribe,
    JobTask.PICK_SEGMENT: handle_pick_segment,
    JobTask.WRITE_SCRIPT: handle_write_script,
    JobTask.SYNTHESIZE: handle_synthesize,
    JobTask.ALIGN: handle_align,
    JobTask.RENDER: handle_render,
    JobTask.PUBLISH: handle_publish,
}

# Bước nào chỉ chạy khi item đang ở đúng trạng thái. Chặn ở đây để một job xếp
# nhầm (hoặc xếp lại sau khi người duyệt trả về) không kéo item đi sai đường.
REQUIRED_STAGE: dict[JobTask, tuple[ItemStage, ...]] = {
    JobTask.DOWNLOAD: (ItemStage.INBOX,),
    JobTask.SEPARATE: (ItemStage.DOWNLOADED,),
    JobTask.TRANSCRIBE: (ItemStage.SEPARATED,),
    JobTask.PICK_SEGMENT: (ItemStage.TRANSCRIPT_REVIEW,),
    JobTask.WRITE_SCRIPT: (ItemStage.SEGMENT_PICKED,),
    JobTask.SYNTHESIZE: (ItemStage.SCRIPTED,),
    JobTask.ALIGN: (ItemStage.VOICED,),
    JobTask.RENDER: (ItemStage.ALIGNED, ItemStage.MIXED),
    JobTask.PUBLISH: (ItemStage.APPROVED,),
}

"""Chạy toàn chuỗi Giai đoạn 1 một lần, **không cần GPU**, để có video thật xem được.

    make smoke

Mục đích: chứng minh dây nối chạy được đầu-cuối và cho ra một video nằm trong
trang duyệt (``/web/review``). Không phải test tự động — test nằm ở ``tests/``.

**Bước nào thật, bước nào giả — đọc kỹ chỗ này:**

===================== ============================================================
Thật                  DB + máy trạng thái item · license gate · TTS tiếng Việt
                      (edge-tts) · cắt + reframe blur + trộn audio + burn phụ đề
                      ASS + loudnorm (ffmpeg và script Easel thật)
Giả (cần GPU/LLM)     tải video (dùng video sinh bằng lavfi) · tách stem Demucs ·
                      nhận dạng lời Whisper · chọn đoạn và viết kịch bản bằng LLM ·
                      forced alignment (cues chia đều theo số ký tự)
===================== ============================================================

Vì vậy **timing phụ đề trong video này không phải timing production**: production
gióng bằng word timestamp của Whisper (F2.5). Ở đây chia đều chỉ để có gì mà burn.

Nguồn dùng ``license_type='own'``: video do chính script sinh ra, không mượn
thước phim của ai. License gate vì thế đi qua một cách hợp lệ, không phải bị bỏ qua.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

SCRIPT_VI = (
    "Cpk thấp mà dung sai vẫn đạt là chuyện thường gặp. "
    "Nguyên nhân hay nằm ở độ trôi của trung bình quá trình theo ca, "
    "không nằm ở độ phân tán. "
    "Ở nhà máy Việt Nam, thay dao và đổi ca là hai mốc trôi rõ nhất. "
    "Xem biểu đồ kiểm soát theo ca trước khi đổi dung sai."
)


def _say(msg: str = "") -> None:
    print(msg, flush=True)


def _gpu_available() -> bool:
    """Có torch + CUDA + faster-whisper + demucs hay không.

    Quyết định bước nào chạy thật: trong container **api** thì không có gì, trong
    container **worker** có đủ. Script tự phát hiện thay vì bắt người chạy truyền cờ,
    và **nói rõ** đường nào đã chạy — một script demo im lặng về việc nó giả bao
    nhiêu phần là script vô dụng.
    """
    try:
        import torch

        if not torch.cuda.is_available():
            return False
        import demucs  # noqa: F401
        import faster_whisper  # noqa: F401
    except ImportError:
        return False
    return True


def main() -> int:
    if not os.environ.get("DATABASE_URL"):
        _say("Thiếu DATABASE_URL — chạy trong container: make smoke")
        return 1

    from src.application.use_cases.manage_sources import (
        ApproveSourceCommand,
        DeclareSourceCommand,
        SourceAlreadyDeclared,
        approve_source,
        declare_source,
    )
    from src.application.use_cases.submit_url import ItemAlreadyExists, submit_url
    from src.application.use_cases.synthesize_voice import synthesize_voice
    from src.application.use_cases.write_script import save_transcript, transcript_dir
    from src.domain.production.value_objects import AspectRatio, MediaAsset, Segment
    from src.domain.sourcing.value_objects import LicenseType, Platform, SourceKind
    from src.infrastructure.clock import SystemClock
    from src.infrastructure.media import ffmpeg
    from src.infrastructure.media.renderer import FfmpegRenderer, RenderRequest
    from src.infrastructure.tts.edge import EdgeTtsSynthesizer
    from src.infrastructure.tts.voxcpm import count_syllables
    from src.interfaces.api.deps import get_uow
    from src.shared.config import get_settings

    settings = get_settings()
    clock = SystemClock()
    uow = get_uow()
    has_gpu = _gpu_available()
    _say(
        "Môi trường: "
        + (
            "worker có GPU — Demucs và alignment chạy THẬT"
            if has_gpu
            else "không có GPU — Demucs và alignment dùng dữ liệu mẫu"
        )
    )
    _say()
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    url = f"https://nmi.vn/demo/smoke-{stamp}"

    # ---- 1. Khai báo và duyệt nguồn (THẬT) ----
    _say("1/8  Khai báo nguồn …")
    try:
        source = declare_source(
            DeclareSourceCommand(
                url=url,
                platform=Platform.WEB,
                kind=SourceKind.SINGLE_URL,
                display_name=f"Smoke test {stamp}",
                audio_lang="en",
                notes="Video do scripts/smoke_pipeline.py sinh ra — không mượn của ai.",
            ),
            uow=uow,
            actor="smoke",
        )
    except SourceAlreadyDeclared:
        _say("     nguồn đã có, dùng lại")
        with uow:
            from src.domain.sourcing.value_objects import SourceUrl

            source = uow.sources.get_by_url(SourceUrl(url))

    _say("2/8  Duyệt license (own — nội dung của chính NMI) …")
    approve_source(
        ApproveSourceCommand(
            source_id=source.id,
            actor="smoke",
            license_type=LicenseType.OWN,
            evidence_ref="video do script sinh ra, thuộc NMI",
            may_translate=True,
            may_modify_audio=True,
            may_subtitle=True,
            may_republish=True,
            may_commercial_use=True,
        ),
        uow=uow,
        clock=clock,
    )

    # ---- 2. Nạp URL qua license gate (THẬT) ----
    _say("3/8  Nạp URL qua license gate …")
    try:
        result = submit_url(url, uow=uow, clock=clock, actor="smoke")
    except ItemAlreadyExists as exc:
        _say(f"     {exc}")
        return 1
    if not result.accepted:
        _say(f"     BỊ CHẶN: {result.reason}")
        return 1
    item_id = result.item.id
    _say(f"     item #{item_id}")

    # ---- 3. "Tải" video: sinh bằng lavfi (GIẢ) ----
    _say("4/8  Sinh video nguồn 16:9 bằng lavfi (thay cho bước tải) …")
    src_dir = settings.paths.source / f"item-{item_id:08d}"
    src_dir.mkdir(parents=True, exist_ok=True)
    source_video = src_dir / "video.mp4"
    ffmpeg.run(
        [
            "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=25:duration=40",
            "-f", "lavfi", "-i", "sine=frequency=120:duration=40",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(source_video),
        ]
    )
    with uow:
        item = uow.items.get(item_id)
        item.mark_downloaded(
            path=MediaAsset(settings.paths.relative(source_video)),
            duration_sec=40,
            aspect_ratio=AspectRatio(16, 9),
        )
        uow.items.update(item)
        uow.commit()

    # ---- 4b. Tách stem: THẬT nếu có GPU ----
    work = transcript_dir(settings.media_root, item_id)
    background: Path | None = None
    if has_gpu:
        _say("     Demucs tách stem (THẬT) — bỏ giọng, giữ tiếng máy …")
        from src.infrastructure.asr.demucs import separate

        audio = ffmpeg.extract_audio(source_video, work / "source_audio.wav")
        stems = separate(audio, work)
        background = stems.background
    else:
        _say("     (bỏ qua Demucs — không có GPU, video sẽ không có nền tiếng máy)")

    with uow:
        item = uow.items.get(item_id)
        item.mark_separated()
        item.mark_transcribed()
        item.send_transcript_to_review()
        uow.items.update(item)
        uow.commit()

    save_transcript(
        settings.media_root,
        item_id,
        text="[transcript giả — bước Whisper cần image worker]",
        segments=[],
    )

    # ---- 4. Chọn đoạn + kịch bản (GIẢ: không gọi LLM) ----
    _say("5/8  Gắn đoạn và kịch bản mẫu (thay cho bước LLM) …")
    with uow:
        item = uow.items.get(item_id)
        source = uow.sources.get(item.source_id)
        item.pick_segment(Segment(2.0, 32.0, rationale="đoạn mẫu của smoke test"))
        item.attach_script(script_vi=SCRIPT_VI, clearance=source.clear_for_dubbing(clock.now()))
        uow.items.update(item)
        uow.commit()

    # ---- 5. Lồng tiếng (THẬT, edge-tts) ----
    syllables = count_syllables(SCRIPT_VI)
    _say(f"6/8  Lồng tiếng bằng edge-tts ({syllables} âm tiết) …")

    class _Probe:
        def duration_sec(self, path: Path) -> float:
            return ffmpeg.probe(path).duration_sec

    rate = settings.tts.measured_rate
    outcome = synthesize_voice(
        item_id,
        synthesizer=EdgeTtsSynthesizer(measured_syllables_per_sec=rate),
        probe=_Probe(),
        count_syllables=count_syllables,
        media_root=settings.media_root,
        uow=uow,
        clock=clock,
    )
    if not outcome.voiced:
        # Đây là hành vi ĐÚNG của ngân sách âm tiết, không phải lỗi của script.
        _say(f"     Ngân sách âm tiết chặn: {outcome.reason}")
        _say("     Sửa SCRIPT_VI ngắn lại hoặc nới khung đoạn rồi chạy lại.")
        return 1
    _say(f"     audio {outcome.audio_sec:.1f}s cho khung 30.0s")

    # ---- 6. Forced alignment ----
    with uow:
        voice_path = settings.paths.absolute(uow.items.get(item_id).path_work.relative_path)

    if has_gpu:
        _say("7/8  Gióng kịch bản đã biết với audio TTS bằng word timestamp của Whisper …")
        from src.infrastructure.asr.align import align_known_text
        from src.infrastructure.asr.whisper import group_words_into_cues

        words = align_known_text(voice_path, SCRIPT_VI, language="vi")
        cues = group_words_into_cues(words)
        _say(f"     {len(words)} từ → {len(cues)} dòng phụ đề")
    else:
        _say("7/8  Chia dòng phụ đề theo tỷ lệ ký tự (KHÔNG phải forced alignment) …")
        sentences = [s.strip() for s in SCRIPT_VI.split(". ") if s.strip()]
        total_chars = sum(len(s) for s in sentences)
        cues, cursor = [], 0.0
        for sentence in sentences:
            span = outcome.audio_sec * len(sentence) / total_chars
            cues.append((cursor, cursor + span, sentence.rstrip(".") + "."))
            cursor += span

    # Máy trạng thái không cho trộn audio trước khi gióng — đúng, vì phụ đề phải
    # có timing mới burn được. Ghi nhận bước gióng (dù ở đây là gióng giả).
    with uow:
        item = uow.items.get(item_id)
        item.mark_aligned()
        uow.items.update(item)
        uow.commit()

    # ---- 7. Render (THẬT: ffmpeg + Easel) ----
    _say("8/8  Render: cắt → reframe blur → trộn → burn phụ đề → loudnorm …")
    with uow:
        segment = uow.items.get(item_id).segment
    output = settings.paths.output / f"item-{item_id:08d}" / "final.mp4"

    FfmpegRenderer().render(
        RenderRequest(
            source_video=source_video,
            voice_audio=voice_path,
            background_audio=background,
            subtitle_cues=cues,
            start_sec=segment.start_sec,
            end_sec=segment.end_sec,
            work_dir=work / "render",
            output=output,
            source_aspect=AspectRatio(16, 9),
            attribution_text="Nội dung: NMI Technologies · giọng đọc AI",
            font_name="Be Vietnam Pro",
        )
    )

    with uow:
        item = uow.items.get(item_id)
        item.mark_mixed()
        item.mark_rendered(path=MediaAsset(settings.paths.relative(output)))
        item.send_to_human_review()
        uow.items.update(item)
        uow.commit()

    info = ffmpeg.probe(output)
    _say()
    _say("Xong.")
    _say(f"  Video   : {output}")
    _say(f"  Khung   : {info.width}x{info.height}  ({info.duration_sec:.1f}s)")
    _say(f"  Trạng thái item #{item_id}: human_review")
    _say()
    _say(f"  Mở để duyệt: http://localhost:{os.environ.get('API_PORT', '8008')}"
         f"/web/review/{item_id}")
    _say()
    if has_gpu:
        _say("Đã chạy THẬT: Demucs tách stem, gióng bằng Whisper, VoxCPM2/edge-tts,")
        _say("toàn bộ chuỗi ffmpeg. Còn giả: bước tải (dùng lavfi) và hai bước LLM")
        _say("(chọn đoạn, viết kịch bản) — hai bước đó cần ANTHROPIC_API_KEY.")
    else:
        _say("Nhắc lại: timing phụ đề ở đây chia đều, KHÔNG phải forced alignment, và")
        _say("không có nền tiếng máy vì Demucs chưa chạy. Cả hai cần container worker.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

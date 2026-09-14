"""Chọn đoạn và viết kịch bản tiếng Việt — hai bước dùng chung một transcript.

Transcript được lưu **thành file** trong ``media/work/item-N/`` chứ không vào DB:
nó dài hàng chục KB, chỉ đọc theo item, và để trong file thì người soát mở bằng
editor được. DB chỉ giữ trạng thái và quyết định.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from src.application.ports import Clock, ScriptWriter, SegmentAdvisor, UnitOfWork
from src.domain.errors import DomainError, InvariantViolation
from src.domain.production.entities import Item
from src.domain.production.value_objects import (
    ItemStage,
    Segment,
    SpeechRate,
    SyllableBudget,
)
from src.domain.scheduling.entities import Job, JobTask
from src.domain.sourcing.value_objects import SourceUrl
from src.shared.paths import MediaPaths

TRANSCRIPT_FILE = "transcript.json"
PROPOSALS_FILE = "segment_proposals.json"


def create_manual_clips(
    item_id: int,
    *,
    ranges: list[tuple[float, float]],
    include_attribution: bool,
    media_root: Path,
    uow: UnitOfWork,
    clock: Clock,
    actor: str,
) -> list[Item]:
    """Tạo các item con dùng chung media gốc, mỗi item là một clip độc lập."""
    if not ranges:
        raise InvariantViolation("phải chọn ít nhất một đoạn")
    with uow:
        parent = uow.items.get(item_id)
        if parent is None or parent.path_source is None or parent.duration_sec is None:
            raise InvariantViolation(f"item #{item_id} chưa có video nguồn hoàn chỉnh")
        source = uow.sources.get(parent.source_id)
        if source is None:
            raise ItemNotFound(f"nguồn #{parent.source_id} không tồn tại")
        clearance = source.clear_for_download(clock.now())
        attribution_required = bool(
            source.evidence and source.evidence.license_type.requires_attribution
        )
        created: list[Item] = []
        for index, (start, end) in enumerate(ranges, 1):
            segment = Segment(start, end, rationale="Người dùng chọn thủ công")
            if end > parent.duration_sec:
                raise InvariantViolation(
                    f"đoạn {index} kết thúc sau video ({parent.duration_sec}s)"
                )
            child = Item.accept(
                url=SourceUrl(f"{parent.url.value}#qone-clip-{item_id}-{index}"),
                clearance=clearance,
                external_id=f"{parent.external_id or item_id}-clip-{index}",
                title_original=f"{parent.title_original or 'Video'} · Clip {index}",
                parent_item_id=item_id,
                clip_index=index,
                include_attribution=include_attribution or attribution_required,
            )
            child.mark_downloaded(
                path=parent.path_source,
                duration_sec=parent.duration_sec,
                aspect_ratio=parent.aspect_ratio,
            )
            child.mark_separated()
            child.mark_transcribed()
            child.send_transcript_to_review()
            child.approve_transcript()
            child.pick_segment(segment)
            uow.items.add(child)
            assert child.id is not None

            source_dir = transcript_dir(media_root, item_id)
            child_dir = transcript_dir(media_root, child.id)
            child_dir.mkdir(parents=True, exist_ok=True)
            for name in (TRANSCRIPT_FILE, "background.wav"):
                src, dst = source_dir / name, child_dir / name
                if src.exists() and not dst.exists():
                    try:
                        os.link(src, dst)
                    except OSError:
                        shutil.copy2(src, dst)
            uow.jobs.enqueue(Job(task=JobTask.WRITE_SCRIPT, item_id=child.id))
            uow.audit.record(
                entity="item",
                entity_id=child.id,
                action="manual_clip_created",
                actor=actor,
                detail={"parent_item_id": item_id, "start": start, "end": end},
            )
            created.append(child)
        uow.commit()
    return created


class ItemNotFound(DomainError):
    pass


class TranscriptMissing(DomainError):
    pass


def transcript_dir(media_root: Path, item_id: int) -> Path:
    """Thư mục làm việc của một item.

    Uỷ quyền cho ``MediaPaths.item_work_dir`` thay vì tự ghép chuỗi: hai công thức
    đặt tên song song là hai chỗ có thể lệch nhau (số chữ số padding, tên thư mục),
    và khi lệch thì bước này ghi file vào một chỗ, bước sau đi tìm ở chỗ khác — cả
    hai đều "thành công", pipeline thì đứt.
    """
    return MediaPaths(media_root).item_work_dir(item_id)


def save_transcript(media_root: Path, item_id: int, *, text: str, segments: list[dict]) -> Path:
    d = transcript_dir(media_root, item_id)
    d.mkdir(parents=True, exist_ok=True)
    path = d / TRANSCRIPT_FILE
    path.write_text(
        json.dumps({"text": text, "segments": segments}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return path


def load_transcript(media_root: Path, item_id: int) -> tuple[str, list[dict]]:
    path = transcript_dir(media_root, item_id) / TRANSCRIPT_FILE
    if not path.exists():
        raise TranscriptMissing(f"chưa có transcript tại {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return str(data.get("text", "")), list(data.get("segments") or [])


def edit_transcript(
    item_id: int,
    *,
    starts: list[float],
    ends: list[float],
    texts: list[str],
    media_root: Path,
    uow: UnitOfWork,
    actor: str,
) -> list[dict]:
    """Lưu các dòng subtitle đã được người dùng chỉnh trên timeline."""
    if not starts or not (len(starts) == len(ends) == len(texts)):
        raise InvariantViolation("transcript phải có các dòng thời gian và nội dung tương ứng")
    segments: list[dict] = []
    previous_end = 0.0
    for index, (start, end, value) in enumerate(zip(starts, ends, texts, strict=True), 1):
        clean_text = value.strip()
        if start < 0 or end <= start:
            raise InvariantViolation(f"dòng {index}: thời gian bắt đầu/kết thúc không hợp lệ")
        if start < previous_end:
            raise InvariantViolation(f"dòng {index}: thời gian chồng lên dòng trước")
        if not clean_text:
            raise InvariantViolation(f"dòng {index}: nội dung không được rỗng")
        segments.append({"start": start, "end": end, "text": clean_text})
        previous_end = end

    with uow:
        item = uow.items.get(item_id)
        if item is None:
            raise ItemNotFound(f"không có item #{item_id}")
        if item.stage not in (ItemStage.TRANSCRIPT_REVIEW, ItemStage.TRANSCRIPT_APPROVED):
            raise InvariantViolation(
                f"item #{item_id} đang ở {item.stage}, không thể sửa transcript lúc này"
            )
        if item.duration_sec is not None and segments[-1]["end"] > item.duration_sec:
            overflow = segments[-1]["end"] - item.duration_sec
            if overflow <= 5 and segments[-1]["start"] < item.duration_sec:
                # Metadata video thường làm tròn xuống giây nguyên, còn ASR trả timestamp
                # thập phân và đôi khi kéo dài qua phần đệm cuối. Giới hạn sai số nhỏ
                # về đúng mép video để người duyệt không phải sửa tay một mốc vô hình.
                segments[-1]["end"] = float(item.duration_sec)
            else:
                raise InvariantViolation("dòng cuối kết thúc sau độ dài video")
        save_transcript(
            media_root,
            item_id,
            text=" ".join(segment["text"] for segment in segments),
            segments=segments,
        )
        uow.audit.record(
            entity="item",
            entity_id=item_id,
            action="transcript_edited",
            actor=actor,
            detail={"lines": len(segments)},
        )
        uow.commit()
    return segments


# ---------------- Chọn đoạn ----------------


@dataclass(frozen=True, slots=True)
class PickOutcome:
    item: Item
    segment: Segment
    proposals: list[tuple[float, float, str]]


def pick_segment(
    item_id: int,
    *,
    advisor: SegmentAdvisor,
    format_transcript,
    media_root: Path,
    uow: UnitOfWork,
    clock: Clock,
    actor: str = "worker",
) -> PickOutcome:
    """LLM đề xuất 2–3 đoạn, hệ thống lấy đoạn đầu và **lưu lại toàn bộ đề xuất**.

    Khác đặc tả một chút, có chủ ý (D28): sơ đồ ghi *"LLM đề xuất → người chọn"*.
    Nhưng Giai đoạn 1 đã có hai gate người (soát transcript và duyệt thành phẩm),
    và thêm gate thứ ba sẽ đẩy công duyệt vượt xa mức 13–22 giờ/tháng đã ước
    lượng. Vì vậy: tự lấy đề xuất đầu, ghi cả danh sách kèm lý do vào
    ``segment_proposals.json`` và ``audit_log``, và người duyệt cuối vẫn trả về
    được nếu đoạn chọn sai.
    """
    with uow:
        item = uow.items.get(item_id)
        if item is None:
            raise ItemNotFound(f"không có item #{item_id}")
        if item.duration_sec is None:
            raise InvariantViolation(f"item #{item_id} chưa biết độ dài video")

        text, segments = load_transcript(media_root, item_id)
        if not text.strip():
            raise TranscriptMissing(f"transcript của item #{item_id} rỗng")

        proposals = advisor.propose(
            transcript=format_transcript(segments) if segments else text,
            duration_sec=item.duration_sec,
        )
        start, end, rationale = proposals[0]
        segment = Segment(start_sec=start, end_sec=end, rationale=rationale)

        d = transcript_dir(media_root, item_id)
        d.mkdir(parents=True, exist_ok=True)
        (d / PROPOSALS_FILE).write_text(
            json.dumps(
                [{"start_sec": s, "end_sec": e, "rationale": r} for s, e, r in proposals],
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )

        item.pick_segment(segment)
        uow.items.update(item)
        uow.audit.record(
            entity="item",
            entity_id=item_id,
            action="segment_picked",
            actor=actor,
            detail={
                "chosen": {"start_sec": start, "end_sec": end, "rationale": rationale},
                "alternatives": len(proposals) - 1,
            },
        )
        uow.commit()
    return PickOutcome(item=item, segment=segment, proposals=proposals)


# ---------------- Viết kịch bản ----------------


@dataclass(frozen=True, slots=True)
class ScriptOutcome:
    item: Item
    script_vi: str
    max_syllables: int


def write_vietnamese_script(
    item_id: int,
    *,
    writer: ScriptWriter,
    speech_rate: float | None,
    glossary: dict[str, str],
    media_root: Path,
    uow: UnitOfWork,
    clock: Clock,
    actor: str = "worker",
) -> ScriptOutcome:
    """Viết kịch bản tiếng Việt trong ngân sách âm tiết của đoạn đã chọn.

    Đòi ``DubbingClearance`` qua ``Item.attach_script`` — đây là bước đầu tiên
    **sửa nội dung**, nên từ đây cần quyền sửa audio, không chỉ quyền dùng lại.
    """
    from src.application.use_cases.synthesize_voice import SpeechRateUnknown

    if speech_rate is None:
        raise SpeechRateUnknown(
            "chưa đo tốc độ đọc — không lập được ngân sách âm tiết (G0.7). "
            "Đặt TTS_SYLLABLES_PER_SEC."
        )

    with uow:
        item = uow.items.get(item_id)
        if item is None:
            raise ItemNotFound(f"không có item #{item_id}")
        if item.segment is None:
            raise InvariantViolation(f"item #{item_id} chưa chọn đoạn")
        source = uow.sources.get(item.source_id)
        if source is None:
            raise ItemNotFound(f"nguồn #{item.source_id} không tồn tại")

        # License gate — LicenseViolation cố ý không bắt, phải nổi lên worker
        clearance = source.clear_for_dubbing(clock.now())

        text, segments = load_transcript(media_root, item_id)
        # Chỉ đưa phần đã chọn cho model. Gửi toàn bộ video vừa tốn token, vừa
        # khiến model có thể viết về một đoạn khác với hình đang render.
        selected_parts = [
            str(seg.get("text", "")).strip()
            for seg in segments
            if float(seg.get("start", 0.0)) < item.segment.end_sec
            and float(seg.get("end", seg.get("start", 0.0))) > item.segment.start_sec
            and str(seg.get("text", "")).strip()
        ]
        selected_text = " ".join(selected_parts) or text
        budget = SyllableBudget(
            window_sec=item.segment.duration_sec, rate=SpeechRate(speech_rate)
        )
        script = writer.write(
            transcript=selected_text,
            segment=(item.segment.start_sec, item.segment.end_sec),
            max_syllables=budget.max_syllables,
            glossary=glossary,
            # Khi viết lại, đưa cả bản cũ và lý do vào prompt — nếu không thì model
            # viết lại từ đầu và rất dễ tràn ngân sách đúng như lần trước.
            previous_attempt=item.script_vi,
            rewrite_reason=item.stage_error,
        )
        item.attach_script(script_vi=script, clearance=clearance)
        uow.items.update(item)
        uow.audit.record(
            entity="item",
            entity_id=item_id,
            action="scripted",
            actor=actor,
            detail={"max_syllables": budget.max_syllables, "chars": len(script)},
        )
        uow.commit()
    return ScriptOutcome(item=item, script_vi=script, max_syllables=budget.max_syllables)


def load_glossary(uow: UnitOfWork, src_lang: str) -> dict[str, str]:
    """Đọc bảng thuật ngữ từ DB.

    Trống là bình thường ở giai đoạn này — G1.3 mới rút glossary từ corpus song
    ngữ nmi.vn. Prompt vẫn chạy được, chỉ là không có ràng buộc thuật ngữ.
    """
    from sqlalchemy import text as sql

    rows = uow.session.execute(
        sql("SELECT term_src, term_vi FROM glossary WHERE src_lang = :lang"),
        {"lang": src_lang},
    ).all()
    return {str(a): str(b) for a, b in rows}

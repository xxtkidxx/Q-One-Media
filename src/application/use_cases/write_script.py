"""Chọn đoạn và viết kịch bản tiếng Việt — hai bước dùng chung một transcript.

Transcript được lưu **thành file** trong ``media/work/item-N/`` chứ không vào DB:
nó dài hàng chục KB, chỉ đọc theo item, và để trong file thì người soát mở bằng
editor được. DB chỉ giữ trạng thái và quyết định.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.application.ports import Clock, ScriptWriter, SegmentAdvisor, UnitOfWork
from src.domain.errors import DomainError, InvariantViolation
from src.domain.production.entities import Item
from src.domain.production.value_objects import (
    Segment,
    SpeechRate,
    SyllableBudget,
)

TRANSCRIPT_FILE = "transcript.json"
PROPOSALS_FILE = "segment_proposals.json"


class ItemNotFound(DomainError):
    pass


class TranscriptMissing(DomainError):
    pass


def transcript_dir(media_root: Path, item_id: int) -> Path:
    return media_root / "work" / f"item-{item_id:08d}"


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

        text, _ = load_transcript(media_root, item_id)
        budget = SyllableBudget(
            window_sec=item.segment.duration_sec, rate=SpeechRate(speech_rate)
        )
        script = writer.write(
            transcript=text,
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

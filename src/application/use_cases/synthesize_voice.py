"""Lồng tiếng Việt, và thi hành ngân sách âm tiết.

Đây là chỗ quy tắc F2.3 thành code. Tiếng Việt nói ra thường **dài hơn** tiếng
Anh cùng nội dung, nên kịch bản gần như luôn có xu hướng tràn khung thời gian.
Hai điều tuyệt đối không làm:

- **Không tăng tốc độ đọc** để nhồi cho vừa — giọng nhanh bất thường là dấu hiệu
  video máy làm. Tràn thì viết ngắn lại.
- **Không lấy con số âm tiết/giây trên mạng.** Các nguồn ghi 5,28–6 và không
  thống nhất. Chưa đo giọng đang dùng thì use case này **từ chối chạy**, vì một
  ngân sách sai còn tệ hơn không có ngân sách: nó làm mọi cảnh lệch đều nhau và
  không ai thấy nguyên nhân.

Có hai lần kiểm, cố ý:

1. **Trước khi sinh** — đếm âm tiết của kịch bản. Bắt được ở đây thì không tốn
   một giây GPU nào.
2. **Sau khi sinh** — đo độ dài audio thật. Cần vì tốc độ đọc thay đổi theo nội
   dung: nhiều số liệu và từ viết tắt thì đọc chậm hơn văn xuôi.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from src.application.ports import Clock, SpeechSynthesizer, UnitOfWork
from src.domain.errors import DomainError
from src.domain.production.entities import Item
from src.domain.production.value_objects import (
    MediaAsset,
    SpeechRate,
    SyllableBudget,
)


class ItemNotFound(DomainError):
    pass


class ScriptMissing(DomainError):
    pass


class SpeechRateUnknown(DomainError):
    """Chưa đo tốc độ đọc thật của giọng đang dùng (G0.7)."""


class AudioProbe(Protocol):
    """Đo độ dài audio. Là port để use case không phụ thuộc ffmpeg."""

    def duration_sec(self, path: Path) -> float: ...


class SyllableCounter(Protocol):
    def __call__(self, text: str) -> int: ...


@dataclass(frozen=True, slots=True)
class SynthesizeOutcome:
    item: Item
    voiced: bool
    syllables: int
    max_syllables: int
    audio_sec: float | None = None
    reason: str | None = None


def synthesize_voice(
    item_id: int,
    *,
    synthesizer: SpeechSynthesizer,
    probe: AudioProbe,
    count_syllables: SyllableCounter,
    media_root: Path,
    uow: UnitOfWork,
    clock: Clock,
    actor: str = "worker",
) -> SynthesizeOutcome:
    with uow:
        item = uow.items.get(item_id)
        if item is None:
            raise ItemNotFound(f"không có item #{item_id}")
        if not (item.script_vi or "").strip():
            raise ScriptMissing(f"item #{item_id} chưa có kịch bản tiếng Việt")
        if item.segment is None:
            raise ScriptMissing(f"item #{item_id} chưa chọn đoạn — không biết khung thời gian")

        source = uow.sources.get(item.source_id)
        if source is None:
            raise ItemNotFound(f"nguồn #{item.source_id} không tồn tại")

        # License gate: lồng tiếng cần quyền sửa audio. Lỗi LicenseViolation cố ý
        # KHÔNG bắt ở đây — nó phải nổi lên worker để job dừng hẳn, không retry.
        clearance = source.clear_for_dubbing(clock.now())

        rate = synthesizer.measured_rate()
        if rate is None:
            raise SpeechRateUnknown(
                "chưa đo tốc độ đọc của giọng đang dùng — đặt TTS_SYLLABLES_PER_SEC "
                "sau khi làm G0.7 (đọc một đoạn 200 âm tiết rồi bấm thời gian)"
            )
        budget = SyllableBudget(window_sec=item.segment.duration_sec, rate=SpeechRate(rate))

        syllables = count_syllables(item.script_vi or "")
        if syllables > budget.max_syllables:
            reason = (
                f"kịch bản {syllables} âm tiết, ngân sách {budget.max_syllables} "
                f"cho khung {budget.window_sec:.1f}s — viết ngắn lại"
            )
            item.rewrite_script(reason)
            uow.items.update(item)
            uow.audit.record(
                entity="item", entity_id=item_id, action="script_over_budget",
                actor=actor, detail={"syllables": syllables, "max": budget.max_syllables},
            )
            uow.commit()
            return SynthesizeOutcome(
                item=item, voiced=False, syllables=syllables,
                max_syllables=budget.max_syllables, reason=reason,
            )

        dest = media_root / "work" / f"item-{item_id:08d}" / "voice_vi.wav"
        synthesizer.synthesize(
            text=item.script_vi or "", dest=dest, clearance=clearance
        )
        audio_sec = probe.duration_sec(dest)

        # Kiểm lần hai: nội dung nhiều số liệu và từ viết tắt đọc chậm hơn văn xuôi,
        # nên đếm âm tiết đúng vẫn có thể ra audio dài quá.
        if budget.overruns(audio_sec):
            reason = (
                f"audio TTS dài {audio_sec:.1f}s, khung {budget.window_sec:.1f}s "
                f"(vượt {(audio_sec / budget.window_sec - 1) * 100:.0f}%) — viết ngắn lại, "
                "không tăng tốc độ đọc"
            )
            item.rewrite_script(reason)
            uow.items.update(item)
            uow.audit.record(
                entity="item", entity_id=item_id, action="audio_over_budget",
                actor=actor, detail={"audio_sec": audio_sec, "window_sec": budget.window_sec},
            )
            uow.commit()
            return SynthesizeOutcome(
                item=item, voiced=False, syllables=syllables,
                max_syllables=budget.max_syllables, audio_sec=audio_sec, reason=reason,
            )

        item.mark_voiced(path=MediaAsset(_relative(dest, media_root)))
        uow.items.update(item)
        uow.audit.record(
            entity="item", entity_id=item_id, action="voiced", actor=actor,
            detail={"syllables": syllables, "audio_sec": audio_sec},
        )
        uow.commit()

    return SynthesizeOutcome(
        item=item, voiced=True, syllables=syllables,
        max_syllables=budget.max_syllables, audio_sec=audio_sec,
    )


def _relative(path: Path, media_root: Path) -> str:
    return Path(path).resolve().relative_to(Path(media_root).resolve()).as_posix()

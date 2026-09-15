"""Aggregate ``Item`` — một video đang được sản xuất, từ lúc nạp URL tới lúc đăng.

Hai bất biến quan trọng nằm ở đây, không nằm ở tầng ngoài:

1. **Không tạo được ``Item`` ở trạng thái làm việc mà không có clearance.**
   ``Item.accept()`` đòi một ``DownloadClearance``; đường còn lại là
   ``Item.blocked()`` và nó dừng hẳn ở ``license_blocked``.
2. **Không sang ``published`` mà chưa qua người duyệt.** ``mark_published()``
   chỉ chấp nhận item đang ở ``approved``, và ``approve()`` đòi tên người duyệt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.domain.errors import HumanReviewRequired, InvalidTransition, InvariantViolation
from src.domain.production.value_objects import (
    PORTRAIT_9_16,
    AspectRatio,
    ItemStage,
    MediaAsset,
    ReframeMode,
    Segment,
    choose_reframe_mode,
)
from src.domain.sourcing.clearance import DownloadClearance, DubbingClearance
from src.domain.sourcing.value_objects import SourceUrl

# Máy trạng thái. Viết tường minh vì đây là tài liệu sống của pipeline:
# đọc dict này là biết pipeline đi đường nào, không phải lần theo code.
_ALLOWED: dict[ItemStage, frozenset[ItemStage]] = {
    ItemStage.INBOX: frozenset({ItemStage.DOWNLOADED, ItemStage.FAILED, ItemStage.REJECTED}),
    ItemStage.LICENSE_BLOCKED: frozenset(),  # cụt có chủ ý: phải đi duyệt nguồn, không đi tắt
    ItemStage.DOWNLOADED: frozenset({ItemStage.SEPARATED, ItemStage.FAILED, ItemStage.REJECTED}),
    ItemStage.SEPARATED: frozenset({ItemStage.TRANSCRIBED, ItemStage.FAILED, ItemStage.REJECTED}),
    ItemStage.TRANSCRIBED: frozenset({ItemStage.TRANSCRIPT_REVIEW, ItemStage.FAILED}),
    ItemStage.TRANSCRIPT_REVIEW: frozenset(
        {ItemStage.TRANSCRIPT_APPROVED, ItemStage.TRANSCRIBED, ItemStage.REJECTED}
    ),
    ItemStage.TRANSCRIPT_APPROVED: frozenset({ItemStage.SEGMENT_PICKED, ItemStage.FAILED}),
    ItemStage.SEGMENT_PICKED: frozenset({ItemStage.SCRIPTED, ItemStage.FAILED, ItemStage.REJECTED}),
    # scripted -> segment_picked: kịch bản tràn ngân sách âm tiết thì viết lại (F2.3)
    ItemStage.SCRIPTED: frozenset(
        {ItemStage.VOICED, ItemStage.SEGMENT_PICKED, ItemStage.FAILED, ItemStage.REJECTED}
    ),
    # voiced -> segment_picked: TTS render dài hơn khung quá 5% thì viết lại (F2.3)
    ItemStage.VOICED: frozenset({ItemStage.ALIGNED, ItemStage.SEGMENT_PICKED, ItemStage.FAILED}),
    ItemStage.ALIGNED: frozenset({ItemStage.MIXED, ItemStage.FAILED}),
    ItemStage.MIXED: frozenset({ItemStage.RENDERED, ItemStage.FAILED}),
    ItemStage.RENDERED: frozenset({ItemStage.HUMAN_REVIEW, ItemStage.FAILED}),
    # human_review -> segment_picked: người duyệt trả về viết lại kịch bản
    ItemStage.HUMAN_REVIEW: frozenset(
        {ItemStage.APPROVED, ItemStage.REJECTED, ItemStage.SEGMENT_PICKED, ItemStage.ALIGNED}
    ),
    ItemStage.APPROVED: frozenset({ItemStage.PUBLISHED, ItemStage.FAILED, ItemStage.REJECTED}),
    ItemStage.PUBLISHED: frozenset(),
    ItemStage.FAILED: frozenset({ItemStage.INBOX, ItemStage.REJECTED}),  # cho phép chạy lại
    ItemStage.REJECTED: frozenset(),
}


@dataclass(eq=False)
class Item:
    source_id: int
    url: SourceUrl
    id: int | None = None
    external_id: str | None = None
    title_original: str | None = None
    duration_sec: int | None = None
    aspect_ratio: AspectRatio | None = None
    # None = giữ nguyên tỷ lệ nguồn; có giá trị = khung đầu ra người dùng chọn.
    output_aspect_ratio: AspectRatio | None = None

    stage: ItemStage = ItemStage.INBOX
    stage_error: str | None = None

    path_source: MediaAsset | None = None
    path_work: MediaAsset | None = None
    path_output: MediaAsset | None = None

    segment: Segment | None = None
    script_vi: str | None = None
    script_sources: tuple[str, ...] = ()
    parent_item_id: int | None = None
    clip_index: int = 1
    include_attribution: bool = True
    # Giọng đọc người dùng chọn cho video này; None = theo TTS_ENGINE mặc định.
    voice_id: str | None = None

    review_by: str | None = None
    review_at: datetime | None = None
    review_notes: str | None = None

    _dubbing_cleared: bool = field(default=False, repr=False)

    # ---------------- Khởi tạo: ba đường, không có đường thứ tư ----------------

    @classmethod
    def accept(cls, *, url: SourceUrl, clearance: DownloadClearance, **kw) -> Item:
        """Nạp một item đã qua license gate.

        ``clearance`` không phải tham số trang trí: nó là bằng chứng nguồn cha
        đang ``approved`` và chưa hết hạn, và chỉ ``Source`` phát hành được.
        """
        return cls(source_id=clearance.source_id, url=url, stage=ItemStage.INBOX, **kw)

    @classmethod
    def blocked(cls, *, url: SourceUrl, source_id: int, reason: str) -> Item:
        """Nạp một item mà nguồn cha chưa có quyền.

        Vẫn lưu lại — để thấy nhu cầu thật và biết nên đi xin phép hãng nào
        trước, chứ không im lặng bỏ đi.
        """
        return cls(
            source_id=source_id,
            url=url,
            stage=ItemStage.LICENSE_BLOCKED,
            stage_error=reason,
        )

    @classmethod
    def from_prompt(
        cls,
        *,
        url: SourceUrl,
        source_id: int,
        script_vi: str,
        title: str,
        target_sec: float,
        author: str,
        voice_id: str | None = None,
        output_aspect_ratio: AspectRatio | None = PORTRAIT_9_16,
    ) -> Item:
        """Giai đoạn 2, đường thủ công: **người dùng tự nhập yêu cầu nội dung**.

        Không có ``SynthesisClearance`` ở đây, và đó là đúng chứ không phải lỗ
        hổng: quy tắc ≥3 nguồn tồn tại để khỏi diễn giải lại *cách viết* của
        người khác. Khi đề bài do chính người của NMI viết ra thì không có bài
        nào bị diễn giải — tác giả là NMI.

        Cái thay thế cho clearance là **trách nhiệm có tên**: ``author`` bắt buộc
        và đi vào audit, giống như gate duyệt luôn đòi tên người duyệt. Ai nhập
        nội dung của người khác vào đây thì đó là quyết định có tên người chịu.
        """
        if not script_vi.strip():
            raise InvariantViolation("kịch bản rỗng")
        if not author.strip():
            raise InvariantViolation("phải ghi tên người nhập nội dung")
        return cls(
            source_id=source_id,
            url=url,
            title_original=title,
            stage=ItemStage.SCRIPTED,
            script_vi=script_vi,
            script_sources=(f"prompt:{author.strip()}",),
            segment=Segment(0.0, target_sec, rationale="Giai đoạn 2 · nội dung tự nhập"),
            duration_sec=int(target_sec),
            aspect_ratio=PORTRAIT_9_16,
            output_aspect_ratio=output_aspect_ratio,
            include_attribution=False,
            voice_id=voice_id,
            _dubbing_cleared=True,
        )

    # ---------------- Chuyển trạng thái ----------------

    def _to(self, target: ItemStage) -> None:
        if target not in _ALLOWED[self.stage]:
            raise InvalidTransition(
                f"item #{self.id}: không đi được từ {self.stage} sang {target}"
            )
        self.stage = target
        if target is not ItemStage.FAILED:
            self.stage_error = None

    def mark_downloaded(
        self,
        *,
        path: MediaAsset,
        duration_sec: int | None = None,
        aspect_ratio: AspectRatio | None = None,
    ) -> None:
        self.path_source = path
        if duration_sec is not None:
            self.duration_sec = duration_sec
        if aspect_ratio is not None:
            self.aspect_ratio = aspect_ratio
        self._to(ItemStage.DOWNLOADED)

    def mark_separated(self) -> None:
        """Demucs xong: bỏ stem giọng, **giữ** stem tiếng máy (F2.4)."""
        self._to(ItemStage.SEPARATED)

    def mark_transcribed(self) -> None:
        self._to(ItemStage.TRANSCRIBED)

    def send_transcript_to_review(self) -> None:
        self._to(ItemStage.TRANSCRIPT_REVIEW)

    def approve_transcript(self) -> None:
        self._to(ItemStage.TRANSCRIPT_APPROVED)

    def pick_segment(self, segment: Segment) -> None:
        if self.duration_sec is not None and segment.end_sec > self.duration_sec + 1:
            raise InvariantViolation(
                f"đoạn kết thúc ở {segment.end_sec}s nhưng video chỉ dài {self.duration_sec}s"
            )
        self.segment = segment
        self._to(ItemStage.SEGMENT_PICKED)

    def attach_script(self, *, script_vi: str, clearance: DubbingClearance) -> None:
        """Gắn kịch bản tiếng Việt.

        Đòi ``DubbingClearance`` vì đây là bước đầu tiên **sửa nội dung** — từ
        đây trở đi cần quyền sửa audio, không chỉ quyền dùng lại.
        """
        if clearance.source_id != self.source_id:
            raise InvariantViolation(
                f"clearance của nguồn #{clearance.source_id} không dùng cho item của "
                f"nguồn #{self.source_id}"
            )
        if not script_vi.strip():
            raise InvariantViolation("kịch bản rỗng")
        self.script_vi = script_vi
        self._dubbing_cleared = True
        self._to(ItemStage.SCRIPTED)

    def rewrite_script(self, reason: str) -> None:
        """Kịch bản tràn ngân sách âm tiết → viết ngắn lại.

        Cố tình **không** có đường "tăng tốc độ đọc cho vừa": giọng nhanh bất
        thường là dấu hiệu video máy làm (F2.3).
        """
        self._to(ItemStage.SEGMENT_PICKED)
        # Đặt sau khi chuyển trạng thái: _to() xoá stage_error, mà lý do viết lại
        # phải sống sót để đưa vào prompt lần sau.
        self.stage_error = reason

    def mark_voiced(self, *, path: MediaAsset | None = None) -> None:
        if not self._dubbing_cleared and self.script_vi is None:
            raise InvariantViolation("chưa có kịch bản đã cấp clearance — không lồng tiếng")
        if path is not None:
            self.path_work = path
        self._to(ItemStage.VOICED)

    def mark_aligned(self) -> None:
        """Forced alignment: kịch bản **đã biết** ↔ audio TTS.

        Không chạy ASR trên audio TTS vừa tạo — đó là tự tạo lỗi nhận dạng từ
        một văn bản đã hoàn hảo (F2.5).
        """
        self._to(ItemStage.ALIGNED)

    def mark_mixed(self) -> None:
        self._to(ItemStage.MIXED)

    def mark_rendered(self, *, path: MediaAsset) -> None:
        self.path_output = path
        self._to(ItemStage.RENDERED)

    def send_to_human_review(self) -> None:
        self._to(ItemStage.HUMAN_REVIEW)

    def reopen_visual_edit(self) -> None:
        """Thành phẩm Studio quay lại bước trước compose để dựng lại có kiểm soát."""
        self._to(ItemStage.ALIGNED)

    def approve(self, *, by: str, at: datetime, notes: str | None = None) -> None:
        """Gate duyệt của người — bắt buộc ở Giai đoạn 1, không có chế độ tự động."""
        if not by.strip():
            raise InvariantViolation("phải ghi ai duyệt")
        self.review_by = by
        self.review_at = at
        self.review_notes = notes
        self._to(ItemStage.APPROVED)

    def reject(self, *, by: str, at: datetime, reason: str) -> None:
        self.review_by = by
        self.review_at = at
        self.review_notes = reason
        self._to(ItemStage.REJECTED)

    def mark_published(self) -> None:
        if self.stage is not ItemStage.APPROVED:
            raise HumanReviewRequired(
                f"item #{self.id} đang ở {self.stage} — chỉ đăng item đã qua người duyệt"
            )
        self._to(ItemStage.PUBLISHED)

    def fail(self, error: str) -> None:
        self.stage_error = error
        self._to(ItemStage.FAILED)

    def retry(self) -> None:
        self._to(ItemStage.INBOX)

    # ---------------- Câu hỏi của pipeline ----------------

    @property
    def needs_reframe(self) -> bool:
        """Chưa biết tỷ lệ thì coi như cần reframe — thà làm thừa hơn ra video sai khung."""
        if self.aspect_ratio is None:
            return True
        return self.aspect_ratio.needs_reframe_to(PORTRAIT_9_16)

    @property
    def reframe_mode(self) -> ReframeMode | None:
        if not self.needs_reframe:
            return None
        return choose_reframe_mode(self.aspect_ratio or PORTRAIT_9_16)

    @property
    def is_ready_to_publish(self) -> bool:
        return self.stage is ItemStage.APPROVED and self.path_output is not None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Item):
            return NotImplemented
        return self.id is not None and self.id == other.id

    def __hash__(self) -> int:
        return hash(("Item", self.id))

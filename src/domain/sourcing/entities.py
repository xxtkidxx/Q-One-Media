"""Aggregate ``Source`` — nguồn do người khai báo, và là **kiểm soát pháp lý
cốt lõi** của cả hệ thống.

Mọi quyết định "có được tải / lồng tiếng / đăng lại không" nằm trong đây, không
nằm ở tầng API hay worker. Tầng ngoài chỉ xin clearance và nhận lỗi nếu không được.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.domain.errors import (
    InvariantViolation,
    ScopeNotGranted,
    SourceExpired,
    SourceNotApproved,
)
from src.domain.sourcing.clearance import (
    _GRANT,
    DownloadClearance,
    DubbingClearance,
    PublishClearance,
)
from src.domain.sourcing.value_objects import (
    ApprovalStatus,
    ContentType,
    Language,
    LicenseEvidence,
    LicenseScope,
    Platform,
    SourceKind,
    SourceUrl,
)


@dataclass(eq=False)
class Source:
    platform: Platform
    kind: SourceKind
    url: SourceUrl
    id: int | None = None
    content_type: ContentType = ContentType.VIDEO
    display_name: str | None = None
    audio_lang: Language = field(default_factory=lambda: Language("en"))
    has_baked_watermark: bool = False

    status: ApprovalStatus = ApprovalStatus.PENDING
    evidence: LicenseEvidence | None = None
    scope: LicenseScope = field(default_factory=LicenseScope)
    approved_by: str | None = None
    approved_at: datetime | None = None
    expires_at: datetime | None = None

    topics: tuple[str, ...] = ()
    notes: str | None = None

    def __post_init__(self) -> None:
        if self.status is ApprovalStatus.APPROVED and self.evidence is None:
            raise InvariantViolation(
                "nguồn approved bắt buộc có bằng chứng license "
                "(trùng với CHECK sources_approved_needs_evidence trong DB)"
            )
        # Nền tảng dán watermark cứng thì mặc định coi là có, kể cả khi người
        # khai báo bỏ trống — thà thận trọng thừa hơn đăng sai lên TikTok.
        if self.platform.bakes_watermark:
            self.has_baked_watermark = True

    # ---------------- Chuyển trạng thái ----------------

    def approve(
        self,
        *,
        by: str,
        evidence: LicenseEvidence,
        scope: LicenseScope,
        at: datetime,
        expires_at: datetime | None = None,
    ) -> None:
        if not by.strip():
            raise InvariantViolation("phải ghi ai duyệt (approved_by)")
        if expires_at is not None and expires_at <= at:
            raise InvariantViolation("expires_at phải sau thời điểm duyệt")
        self.status = ApprovalStatus.APPROVED
        self.evidence = evidence
        self.scope = scope
        self.approved_by = by
        self.approved_at = at
        self.expires_at = expires_at

    def reject(self, *, by: str, reason: str, at: datetime) -> None:
        self.status = ApprovalStatus.REJECTED
        self.approved_by = by
        self.approved_at = at
        self.notes = reason

    def expire(self) -> None:
        """Đánh dấu hết hạn — dùng cho job quét định kỳ."""
        if self.status is ApprovalStatus.APPROVED:
            self.status = ApprovalStatus.EXPIRED

    # ---------------- License gate ----------------

    def is_usable(self, now: datetime) -> bool:
        return self.status is ApprovalStatus.APPROVED and not self._is_expired(now)

    def _is_expired(self, now: datetime) -> bool:
        return self.expires_at is not None and self.expires_at <= now

    def _require_usable(self, now: datetime) -> int:
        if self.id is None:
            raise InvariantViolation("nguồn chưa được lưu (thiếu id) — không cấp clearance")
        if self.status is not ApprovalStatus.APPROVED:
            raise SourceNotApproved(
                f"nguồn #{self.id} ({self.url.host}) đang ở trạng thái "
                f"{self.status} — pipeline từ chối xử lý"
            )
        if self._is_expired(now):
            raise SourceExpired(
                f"nguồn #{self.id} ({self.url.host}) hết hạn license lúc {self.expires_at}"
            )
        return self.id

    def clear_for_download(self, now: datetime) -> DownloadClearance:
        sid = self._require_usable(now)
        return DownloadClearance(
            source_id=sid,
            _grant=_GRANT,
            url_expires_fast=self.platform.url_expires_fast,
            platform=str(self.platform),
        )

    def clear_for_dubbing(self, now: datetime) -> DubbingClearance:
        """Clearance để lồng tiếng Việt + phụ đề.

        Đây là chỗ thi hành quy tắc: quyền dùng lại **không** suy ra quyền sửa audio.
        """
        sid = self._require_usable(now)
        assert self.evidence is not None  # bất biến đã kiểm ở __post_init__
        missing = self.scope.missing_for_dubbing()
        if missing:
            raise ScopeNotGranted(
                f"nguồn #{sid} ({self.url.host}) thiếu quyền {', '.join(missing)} "
                "— lồng tiếng cần quyền sửa audio, không suy ra từ quyền dùng lại"
            )
        return DubbingClearance(
            source_id=sid,
            _grant=_GRANT,
            audio_lang=self.audio_lang,
            license_type=self.evidence.license_type,
            attribution_text=self.evidence.attribution_text,
            has_baked_watermark=self.has_baked_watermark,
        )

    def clear_for_publish(self, now: datetime) -> PublishClearance:
        sid = self._require_usable(now)
        assert self.evidence is not None
        missing = self.scope.missing_for_publish()
        if missing:
            raise ScopeNotGranted(
                f"nguồn #{sid} ({self.url.host}) thiếu quyền {', '.join(missing)}"
            )
        return PublishClearance(
            source_id=sid,
            _grant=_GRANT,
            attribution_text=self.evidence.attribution_text,
            has_baked_watermark=self.has_baked_watermark,
        )

    # ---------------- Quyết định phụ ----------------

    @property
    def expected_review_minutes(self) -> tuple[int, int]:
        """Công duyệt dự kiến theo đặc tả F2.8 — dùng để xếp hàng đợi người duyệt."""
        return (35, 55) if self.audio_lang.needs_extra_review else (20, 35)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Source):
            return NotImplemented
        return self.id is not None and self.id == other.id

    def __hash__(self) -> int:
        return hash(("Source", self.id))

"""Aggregate ``Publication`` — một lần đăng một item lên một nền tảng."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain.errors import InvalidTransition, InvariantViolation
from src.domain.publishing.value_objects import PublishPlatform, PublishStatus

_ALLOWED: dict[PublishStatus, frozenset[PublishStatus]] = {
    PublishStatus.QUEUED: frozenset(
        {PublishStatus.UPLOADING, PublishStatus.SKIPPED, PublishStatus.FAILED}
    ),
    PublishStatus.UPLOADING: frozenset({PublishStatus.PUBLISHED, PublishStatus.FAILED}),
    PublishStatus.FAILED: frozenset({PublishStatus.QUEUED}),  # cho phép đăng lại
    PublishStatus.PUBLISHED: frozenset(),
    PublishStatus.SKIPPED: frozenset(),
}


@dataclass(eq=False)
class Publication:
    item_id: int
    platform: PublishPlatform
    id: int | None = None
    status: PublishStatus = PublishStatus.QUEUED
    remote_id: str | None = None
    remote_url: str | None = None
    error: str | None = None
    skipped_reason: str | None = None
    published_at: datetime | None = None

    def _to(self, target: PublishStatus) -> None:
        if target not in _ALLOWED[self.status]:
            raise InvalidTransition(
                f"publication #{self.id} ({self.platform}): "
                f"không đi được từ {self.status} sang {target}"
            )
        self.status = target

    def start_upload(self) -> None:
        self._to(PublishStatus.UPLOADING)

    def mark_published(self, *, remote_id: str, remote_url: str | None, at: datetime) -> None:
        if not remote_id.strip():
            raise InvariantViolation("thiếu remote_id — không xác nhận được là đã đăng")
        self.remote_id = remote_id
        self.remote_url = remote_url
        self.published_at = at
        self.error = None
        self._to(PublishStatus.PUBLISHED)

    def skip(self, reason: str) -> None:
        """Bỏ qua có chủ ý, không phải lỗi.

        Ví dụ dùng thật: nguồn có watermark dán cứng nên không đăng TikTok. Ghi
        lại lý do để sau này không ai tưởng là hệ thống hỏng.
        """
        self.skipped_reason = reason
        self._to(PublishStatus.SKIPPED)

    def fail(self, error: str) -> None:
        self.error = error
        self._to(PublishStatus.FAILED)

    def requeue(self) -> None:
        self._to(PublishStatus.QUEUED)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Publication):
            return NotImplemented
        return self.id is not None and self.id == other.id

    def __hash__(self) -> int:
        return hash(("Publication", self.id))

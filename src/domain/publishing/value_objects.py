"""Value object của bounded context "đăng bài"."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from src.domain.errors import InvariantViolation


class PublishPlatform(StrEnum):
    YOUTUBE = "youtube"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    LINKEDIN = "linkedin"

    @property
    def rejects_baked_watermark(self) -> bool:
        """TikTok coi video mang watermark nền tảng khác là nội dung không nguyên bản.

        Hệ quả thật: video **không bị xoá**, nhưng bị loại khỏi For You feed —
        upload trả 200, dashboard xanh, và không ai xem. Vì thế phải chặn ở đây
        chứ không chờ nền tảng báo lỗi, vì nó sẽ không báo.
        """
        return self is PublishPlatform.TIKTOK

    @property
    def daily_upload_quota(self) -> int | None:
        """Hạn mức đã xác minh (đặc tả F2.7). ``None`` = chưa xác minh được số."""
        if self is PublishPlatform.YOUTUBE:
            return 100  # videos.insert: bucket riêng, 1 unit/lần, 100 lần/ngày
        return None


class PublishStatus(StrEnum):
    QUEUED = "queued"
    UPLOADING = "uploading"
    PUBLISHED = "published"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    """Phần chữ đi kèm video khi đăng."""

    title: str
    description: str
    tags: tuple[str, ...] = ()
    ai_generated_voice: bool = True

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise InvariantViolation("tiêu đề rỗng")
        if len(self.title) > 100:
            raise InvariantViolation(
                f"tiêu đề {len(self.title)} ký tự — YouTube giới hạn 100"
            )

    def with_attribution(self, attribution_text: str | None) -> VideoMetadata:
        """Chèn ghi nguồn vào đầu phần mô tả.

        Bắt buộc với CC BY, và là cách giữ credit gốc như quy tắc nghiệp vụ yêu
        cầu. Không có hàm nào xoá attribution — cố ý không viết.
        """
        if not attribution_text:
            return self
        if attribution_text in self.description:
            return self
        return VideoMetadata(
            title=self.title,
            description=f"{attribution_text}\n\n{self.description}",
            tags=self.tags,
            ai_generated_voice=self.ai_generated_voice,
        )

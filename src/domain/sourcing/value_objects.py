"""Value object của bounded context "khai báo và cấp phép nguồn"."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse

from src.domain.errors import InvariantViolation


class Platform(StrEnum):
    YOUTUBE = "youtube"
    DOUYIN = "douyin"
    BILIBILI = "bilibili"
    TIKTOK = "tiktok"
    FACEBOOK = "facebook"
    VIMEO = "vimeo"
    WEB = "web"

    @property
    def url_expires_fast(self) -> bool:
        """URL CDN hết hạn trong vài giờ → phải tải đồng bộ ngay khi nạp.

        Douyin là trường hợp đã biết; xem đặc tả mục F2.1.
        """
        return self is Platform.DOUYIN

    @property
    def bakes_watermark(self) -> bool:
        """Nền tảng dán watermark cứng vào khung hình.

        Không phải để xoá watermark — để **biết mà không đăng lên TikTok**.
        """
        return self in (Platform.DOUYIN, Platform.TIKTOK)


class SourceKind(StrEnum):
    CHANNEL = "channel"
    PLAYLIST = "playlist"
    CREATOR_PAGE = "creator-page"
    WEBSITE = "website"
    RSS = "rss"
    SINGLE_URL = "single-url"


class ContentType(StrEnum):
    VIDEO = "video"
    ARTICLE = "article"


class LicenseType(StrEnum):
    VENDOR_MEDIAKIT = "vendor-mediakit"
    WRITTEN_PERMISSION = "written-permission"
    CC_BY = "cc-by"
    STOCK = "stock"
    OWN = "own"

    @property
    def requires_attribution(self) -> bool:
        """CC BY buộc ghi nguồn; thiếu là vi phạm license."""
        return self is LicenseType.CC_BY


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


_URL_OK_SCHEMES = ("http", "https")


@dataclass(frozen=True, slots=True)
class SourceUrl:
    value: str

    def __post_init__(self) -> None:
        parsed = urlparse(self.value)
        if parsed.scheme not in _URL_OK_SCHEMES:
            raise InvariantViolation(f"URL phải là http/https: {self.value!r}")
        if not parsed.netloc:
            raise InvariantViolation(f"URL thiếu host: {self.value!r}")

    @property
    def host(self) -> str:
        return urlparse(self.value).netloc.lower().removeprefix("www.")

    def __str__(self) -> str:
        return self.value


_LANG_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z]{2,4})?$")


@dataclass(frozen=True, slots=True)
class Language:
    """Mã ngôn ngữ nguồn. Quyết định nhánh ASR, chiều glossary và công duyệt."""

    code: str

    def __post_init__(self) -> None:
        if not _LANG_RE.match(self.code):
            raise InvariantViolation(f"mã ngôn ngữ không hợp lệ: {self.code!r}")

    @property
    def base(self) -> str:
        return self.code.split("-")[0]

    @property
    def needs_extra_review(self) -> bool:
        """Nguồn tiếng Trung: CER ~12,8% → công duyệt gấp đôi (đặc tả F2.8)."""
        return self.base == "zh"

    def __str__(self) -> str:
        return self.code


@dataclass(frozen=True, slots=True)
class LicenseScope:
    """Các quyền **rời nhau**.

    Cố tình không có cờ "toàn quyền": quyền được dùng lại **không** suy ra
    quyền sửa audio, mà lồng tiếng thì cần đúng quyền sửa audio.
    """

    may_translate: bool = False
    may_modify_audio: bool = False
    may_subtitle: bool = False
    may_republish: bool = False
    may_commercial_use: bool = False

    def missing_for_dubbing(self) -> tuple[str, ...]:
        """Quyền còn thiếu để lồng tiếng + phụ đề (Giai đoạn 1 làm cả hai)."""
        missing = []
        if not self.may_translate:
            missing.append("may_translate")
        if not self.may_modify_audio:
            missing.append("may_modify_audio")
        if not self.may_subtitle:
            missing.append("may_subtitle")
        return tuple(missing)

    def missing_for_publish(self) -> tuple[str, ...]:
        missing = []
        if not self.may_republish:
            missing.append("may_republish")
        if not self.may_commercial_use:
            missing.append("may_commercial_use")
        return tuple(missing)


@dataclass(frozen=True, slots=True)
class LicenseEvidence:
    """Bằng chứng quyền sử dụng. Không có bằng chứng thì không thể approve."""

    license_type: LicenseType
    evidence_ref: str
    attribution_text: str | None = None

    def __post_init__(self) -> None:
        if not self.evidence_ref.strip():
            raise InvariantViolation(
                "evidence_ref không được rỗng — cần link điều khoản, "
                "file email đồng ý, hoặc số hợp đồng"
            )
        if self.license_type.requires_attribution and not (self.attribution_text or "").strip():
            raise InvariantViolation(
                f"license {self.license_type} bắt buộc attribution_text"
            )

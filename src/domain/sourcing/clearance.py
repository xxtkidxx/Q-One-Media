"""Giấy phép thông hành (clearance) — license gate dưới dạng **kiểu dữ liệu**.

Vì sao làm thế này thay vì một câu ``if`` trong handler: câu ``if`` có thể bị
quên, bị bọc trong cờ cấu hình, hoặc bị một đường code mới đi vòng qua. Còn ở
đây hàm tải video **bắt buộc nhận một ``DownloadClearance``**, và vật đó chỉ
``Source`` cấp được. Không có clearance thì không gọi được hàm — trình kiểm tra
kiểu báo lỗi ngay, không cần ai nhớ quy tắc.

Ba clearance tách riêng vì ba việc cần ba nhóm quyền khác nhau:

- ``DownloadClearance`` — nguồn ``approved`` và chưa hết hạn.
- ``DubbingClearance``  — thêm ``may_translate`` + ``may_modify_audio`` + ``may_subtitle``.
- ``PublishClearance``  — thêm ``may_republish`` + ``may_commercial_use``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from src.domain.errors import InvariantViolation
from src.domain.sourcing.value_objects import Language, LicenseType


class _Grant:
    """Chìa khoá riêng của module. Chỉ ``Source`` (cùng package) mượn được."""

    __slots__ = ()


_GRANT: Final = _Grant()


@dataclass(frozen=True, slots=True)
class _Clearance:
    source_id: int
    _grant: _Grant = field(repr=False)

    def __post_init__(self) -> None:
        if self._grant is not _GRANT:
            raise InvariantViolation(
                "clearance chỉ được cấp qua Source.clear_for_*(); "
                "không tự dựng ở tầng ngoài"
            )


@dataclass(frozen=True, slots=True)
class DownloadClearance(_Clearance):
    """Được phép tải nguồn này về đĩa."""

    url_expires_fast: bool = False
    platform: str = "web"


@dataclass(frozen=True, slots=True)
class DubbingClearance(_Clearance):
    """Được phép lồng tiếng Việt và gắn phụ đề."""

    audio_lang: Language = Language("en")
    license_type: LicenseType = LicenseType.WRITTEN_PERMISSION
    attribution_text: str | None = None
    has_baked_watermark: bool = False


@dataclass(frozen=True, slots=True)
class PublishClearance(_Clearance):
    """Được phép đăng lại công khai và dùng cho mục đích thương mại."""

    attribution_text: str | None = None
    has_baked_watermark: bool = False

"""Chính sách đăng bài — quyết định *có đăng hay không*, tách khỏi *cách đăng*.

Ở đây không có HTTP, không có SDK nền tảng. Nhờ vậy toàn bộ quy tắc nghiệp vụ
nhạy cảm nhất của dự án test được bằng unit test thuần, không cần token thật.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.production.entities import Item
from src.domain.production.value_objects import ItemStage
from src.domain.publishing.value_objects import PublishPlatform
from src.domain.sourcing.clearance import PublishClearance


@dataclass(frozen=True, slots=True)
class PublishDecision:
    allowed: bool
    reason: str | None = None

    @classmethod
    def yes(cls) -> PublishDecision:
        return cls(True, None)

    @classmethod
    def no(cls, reason: str) -> PublishDecision:
        return cls(False, reason)


def decide(
    *,
    item: Item,
    platform: PublishPlatform,
    clearance: PublishClearance,
) -> PublishDecision:
    """Bốn cửa, theo đúng thứ tự từ nghiêm ngặt nhất xuống.

    ``clearance`` đã chứng minh nguồn có quyền đăng lại và dùng thương mại —
    không gọi được hàm này mà thiếu nó.
    """
    if clearance.source_id != item.source_id:
        return PublishDecision.no(
            f"clearance của nguồn #{clearance.source_id} không thuộc item này"
        )

    if item.stage is not ItemStage.APPROVED:
        return PublishDecision.no(
            f"item đang ở {item.stage} — gate duyệt của người là bắt buộc ở Giai đoạn 1"
        )

    if item.path_output is None:
        return PublishDecision.no("chưa có file thành phẩm")

    if platform.rejects_baked_watermark and clearance.has_baked_watermark:
        return PublishDecision.no(
            f"nguồn có watermark dán cứng — không đăng lên {platform}. "
            "Giữ nguyên watermark gốc; không xoá để lách"
        )

    return PublishDecision.yes()

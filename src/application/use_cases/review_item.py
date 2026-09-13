"""Gate duyệt của người — bắt buộc ở Giai đoạn 1.

Không có use case nào tự duyệt. Hàm ở đây luôn đòi tên người duyệt, và tên đó
vào cả ``items.review_by`` lẫn ``audit_log``.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application.ports import Clock, UnitOfWork
from src.domain.errors import DomainError
from src.domain.production.entities import Item
from src.domain.production.value_objects import ItemStage


class ItemNotFound(DomainError):
    pass


@dataclass(frozen=True, slots=True)
class ReviewQueueEntry:
    item: Item
    expected_minutes: tuple[int, int]


def list_review_queue(*, uow: UnitOfWork, limit: int = 50) -> list[ReviewQueueEntry]:
    """Hàng đợi duyệt, kèm công duyệt dự kiến theo ngôn ngữ nguồn.

    Hiện số phút vì công duyệt là ràng buộc thật của hệ thống này — không phải
    tiền, mà là thời gian người. Nguồn tiếng Trung tốn gấp đôi (F2.8), nên người
    duyệt cần thấy trước khi nhận việc.
    """
    with uow:
        items = uow.items.list_by_stage(ItemStage.HUMAN_REVIEW, limit=limit)
        out = []
        for item in items:
            source = uow.sources.get(item.source_id)
            expected = source.expected_review_minutes if source else (20, 35)
            out.append(ReviewQueueEntry(item=item, expected_minutes=expected))
    return out


def approve_item(
    item_id: int, *, actor: str, notes: str | None = None, uow: UnitOfWork, clock: Clock
) -> Item:
    with uow:
        item = _get(uow, item_id)
        item.approve(by=actor, at=clock.now(), notes=notes)
        uow.items.update(item)
        uow.audit.record(
            entity="item",
            entity_id=item_id,
            action="review_approved",
            actor=actor,
            detail={"notes": notes},
        )
        uow.commit()
    return item


def reject_item(item_id: int, *, actor: str, reason: str, uow: UnitOfWork, clock: Clock) -> Item:
    with uow:
        item = _get(uow, item_id)
        item.reject(by=actor, at=clock.now(), reason=reason)
        uow.items.update(item)
        uow.audit.record(
            entity="item",
            entity_id=item_id,
            action="review_rejected",
            actor=actor,
            detail={"reason": reason},
        )
        uow.commit()
    return item


def send_back_for_rewrite(
    item_id: int, *, actor: str, reason: str, uow: UnitOfWork, clock: Clock
) -> Item:
    """Người duyệt thấy kịch bản chưa ổn: trả về bước viết lại, không loại bỏ hẳn."""
    with uow:
        item = _get(uow, item_id)
        item.rewrite_script(reason)
        uow.items.update(item)
        uow.audit.record(
            entity="item",
            entity_id=item_id,
            action="sent_back_for_rewrite",
            actor=actor,
            detail={"reason": reason},
        )
        uow.commit()
    return item


def _get(uow: UnitOfWork, item_id: int) -> Item:
    item = uow.items.get(item_id)
    if item is None:
        raise ItemNotFound(f"không có item #{item_id}")
    return item

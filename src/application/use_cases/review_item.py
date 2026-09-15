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
from src.domain.scheduling.entities import Job, JobTask


class ItemNotFound(DomainError):
    pass


class TranscriptNotAwaitingReview(DomainError):
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


def approve_transcript(item_id: int, *, actor: str, uow: UnitOfWork) -> Item:
    """Người soát transcript xong → chờ người chọn một hoặc nhiều đoạn.

    Đây là một trong hai chỗ dây nối giữa các bước **cố tình đứt**: worker dừng
    sau khi nhận dạng lời, và chỉ thao tác của người mới nối tiếp được. Nhất là
    với nguồn tiếng Trung, nơi khoảng 1/8 ký tự nhận sai.
    """
    with uow:
        item = _get(uow, item_id)
        if item.stage is not ItemStage.TRANSCRIPT_REVIEW:
            raise TranscriptNotAwaitingReview(
                f"item #{item_id} đang ở {item.stage}, không phải đang chờ soát transcript"
            )
        item.approve_transcript()
        uow.items.update(item)
        uow.audit.record(
            entity="item",
            entity_id=item_id,
            action="transcript_approved_awaiting_segment_selection",
            actor=actor,
        )
        uow.commit()
    return item


def approve_item(
    item_id: int,
    *,
    actor: str,
    notes: str | None = None,
    uow: UnitOfWork,
    clock: Clock,
    queue_publish: bool = False,
) -> Item:
    """Duyệt thành phẩm, và xếp việc đăng nếu publish đang bật.

    ``queue_publish`` mặc định ``False``: xếp việc đăng khi ``PUBLISH_ENABLED=false``
    chỉ sinh ra job thất bại ở mỗi lần duyệt — tiếng ồn che mất lỗi thật. Người gọi
    truyền cờ thật từ cấu hình.
    """
    with uow:
        item = _get(uow, item_id)
        item.approve(by=actor, at=clock.now(), notes=notes)
        uow.items.update(item)
        if queue_publish:
            uow.jobs.enqueue(Job(task=JobTask.PUBLISH, item_id=item_id))
        uow.audit.record(
            entity="item",
            entity_id=item_id,
            action="review_approved",
            actor=actor,
            detail={"notes": notes, "publish_queued": queue_publish},
        )
        uow.commit()
    return item


def queue_publish(item_id: int, *, actor: str, uow: UnitOfWork, enabled: bool) -> Item:
    """Xếp việc đăng cho một item **đã duyệt**.

    Tách khỏi ``approve_item`` vì hai lý do khác nhau về thời điểm: người duyệt có
    thể duyệt hôm nay và đăng ngày mai, và khi ``PUBLISH_ENABLED=false`` thì lúc
    duyệt không xếp gì cả — nút đăng là chỗ người dùng quay lại sau. Cờ kill-switch
    vẫn chỉ chặn thêm, không bao giờ mở thêm: không có đường nào đăng khi nó tắt.
    """
    from src.application.use_cases.publish_item import PublishDisabled

    if not enabled:
        raise PublishDisabled("PUBLISH_ENABLED=false — hệ thống đang không đăng gì")
    with uow:
        item = _get(uow, item_id)
        if item.stage is not ItemStage.APPROVED:
            raise DomainError(
                f"item #{item_id} đang ở {item.stage}, chỉ item đã duyệt mới đăng được"
            )
        uow.jobs.enqueue(Job(task=JobTask.PUBLISH, item_id=item_id))
        uow.audit.record(
            entity="item", entity_id=item_id, action="publish_queued", actor=actor
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
        uow.jobs.enqueue(Job(task=JobTask.WRITE_SCRIPT, item_id=item_id))
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

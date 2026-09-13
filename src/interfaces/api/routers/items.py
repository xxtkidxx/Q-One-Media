"""Hộp thư URL và gate duyệt của người."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from src.application.use_cases.review_item import (
    ItemNotFound,
    TranscriptNotAwaitingReview,
    approve_item,
    approve_transcript,
    list_review_queue,
    reject_item,
    send_back_for_rewrite,
)
from src.application.use_cases.submit_url import (
    ItemAlreadyExists,
    SourceNotDeclared,
    submit_url,
)
from src.domain.production.value_objects import ItemStage
from src.infrastructure.clock import SystemClock
from src.infrastructure.db.uow import SqlUnitOfWork
from src.shared.config import Settings
from src.interfaces.api.deps import get_clock, get_config, get_uow
from src.interfaces.api.schemas import (
    ItemOut,
    RejectIn,
    ReviewDecisionIn,
    ReviewQueueItemOut,
    SubmitUrlIn,
    SubmitUrlOut,
)

router = APIRouter(prefix="/items", tags=["items"])

Uow = Annotated[SqlUnitOfWork, Depends(get_uow)]
Clock = Annotated[SystemClock, Depends(get_clock)]
Config = Annotated["Settings", Depends(get_config)]


@router.post("", response_model=SubmitUrlOut, status_code=202)
def submit(body: SubmitUrlIn, uow: Uow, clock: Clock) -> SubmitUrlOut:
    """Nạp một URL video.

    Trả **202 kể cả khi bị license gate chặn** — vì item vẫn được lưu và đó là
    kết quả nghiệp vụ hợp lệ, không phải lỗi của người gọi. Đọc ``accepted`` và
    ``reason`` để biết có đi tiếp hay không.
    """
    try:
        result = submit_url(body.url, uow=uow, clock=clock, actor=body.actor)
    except SourceNotDeclared as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ItemAlreadyExists as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return SubmitUrlOut(
        item=ItemOut.of(result.item),
        accepted=result.accepted,
        job_id=result.job_id,
        reason=result.reason,
    )


@router.get("", response_model=list[ItemOut])
def list_items(
    uow: Uow,
    stage: ItemStage = Query(default=ItemStage.INBOX),
    limit: int = Query(default=50, le=200),
) -> list[ItemOut]:
    with uow:
        return [ItemOut.of(i) for i in uow.items.list_by_stage(stage, limit=limit)]


@router.get("/stats", response_model=dict[str, int])
def stats(uow: Uow) -> dict[str, int]:
    """Đếm item theo từng bước — dùng làm dashboard tối giản."""
    with uow:
        return {str(k): v for k, v in uow.items.count_by_stage().items()}


@router.get("/review-queue", response_model=list[ReviewQueueItemOut])
def review_queue(uow: Uow, limit: int = Query(default=50, le=200)) -> list[ReviewQueueItemOut]:
    """Hàng đợi duyệt kèm công duyệt dự kiến.

    Hiện số phút vì ràng buộc thật của hệ thống này là thời gian người, không
    phải tiền — nguồn tiếng Trung tốn khoảng gấp đôi tiếng Anh.
    """
    return [
        ReviewQueueItemOut(item=ItemOut.of(e.item), expected_review_minutes=e.expected_minutes)
        for e in list_review_queue(uow=uow, limit=limit)
    ]


@router.get("/{item_id}", response_model=ItemOut)
def get_item(item_id: int, uow: Uow) -> ItemOut:
    with uow:
        item = uow.items.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"không có item #{item_id}")
    return ItemOut.of(item)


@router.post("/{item_id}/transcript-approve", response_model=ItemOut)
def transcript_approve(item_id: int, body: ReviewDecisionIn, uow: Uow) -> ItemOut:
    """Người soát transcript xong → xếp việc chọn đoạn.

    Worker dừng sau bước nhận dạng lời; chỉ thao tác này nối tiếp được.
    """
    try:
        item = approve_transcript(item_id, actor=body.actor, uow=uow)
    except ItemNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TranscriptNotAwaitingReview as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ItemOut.of(item)


@router.post("/{item_id}/approve", response_model=ItemOut)
def approve(
    item_id: int, body: ReviewDecisionIn, uow: Uow, clock: Clock, config: Config
) -> ItemOut:
    """Người duyệt chấp nhận. Đây là bước không thể tự động hoá ở Giai đoạn 1."""
    try:
        item = approve_item(
            item_id,
            actor=body.actor,
            notes=body.notes,
            uow=uow,
            clock=clock,
            queue_publish=config.publish.enabled,
        )
    except ItemNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ItemOut.of(item)


@router.post("/{item_id}/reject", response_model=ItemOut)
def reject(item_id: int, body: RejectIn, uow: Uow, clock: Clock) -> ItemOut:
    try:
        item = reject_item(item_id, actor=body.actor, reason=body.reason, uow=uow, clock=clock)
    except ItemNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ItemOut.of(item)


@router.post("/{item_id}/rewrite", response_model=ItemOut)
def rewrite(item_id: int, body: RejectIn, uow: Uow, clock: Clock) -> ItemOut:
    """Trả về bước viết lại kịch bản — không loại bỏ hẳn item."""
    try:
        item = send_back_for_rewrite(
            item_id, actor=body.actor, reason=body.reason, uow=uow, clock=clock
        )
    except ItemNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ItemOut.of(item)

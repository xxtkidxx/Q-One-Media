"""Quản lý nguồn — khai báo, duyệt, từ chối, xem.

Đây là màn hình quan trọng nhất với người dùng: mọi thứ pipeline làm về sau đều
bị chặn hoặc cho phép bởi dữ liệu khai ở đây.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from src.application.use_cases.manage_sources import (
    ApproveSourceCommand,
    DeclareSourceCommand,
    SourceAlreadyDeclared,
    SourceNotFound,
    approve_source,
    declare_source,
    reject_source,
)
from src.domain.sourcing.value_objects import ApprovalStatus
from src.infrastructure.clock import SystemClock
from src.infrastructure.db.uow import SqlUnitOfWork
from src.interfaces.api.deps import get_clock, get_uow
from src.interfaces.api.schemas import (
    ApproveSourceIn,
    DeclareSourceIn,
    RejectIn,
    SourceOut,
)

router = APIRouter(prefix="/sources", tags=["sources"])

STATUS_QUERY = Query(default=ApprovalStatus.PENDING)

Uow = Annotated[SqlUnitOfWork, Depends(get_uow)]
Clock = Annotated[SystemClock, Depends(get_clock)]


@router.post("", response_model=SourceOut, status_code=201)
def declare(body: DeclareSourceIn, uow: Uow) -> SourceOut:
    """Khai báo nguồn. Luôn vào ``pending`` — không có tham số nào tự duyệt."""
    try:
        source = declare_source(
            DeclareSourceCommand(
                url=body.url,
                platform=body.platform,
                kind=body.kind,
                content_type=body.content_type,
                display_name=body.display_name,
                audio_lang=body.audio_lang,
                external_owner_id=body.external_owner_id,
                has_baked_watermark=body.has_baked_watermark,
                topics=tuple(body.topics),
                notes=body.notes,
            ),
            uow=uow,
            actor=body.display_name or "api",
        )
    except SourceAlreadyDeclared as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return SourceOut.of(source)


@router.post("/{source_id}/approve", response_model=SourceOut)
def approve(source_id: int, body: ApproveSourceIn, uow: Uow, clock: Clock) -> SourceOut:
    """Duyệt nguồn kèm bằng chứng và phạm vi quyền.

    Lưu ý nghiệp vụ: để lồng tiếng được thì ``may_modify_audio`` phải TRUE.
    Duyệt mà bỏ trống quyền đó thì nguồn tải được nhưng dừng ở bước viết kịch bản.
    """
    try:
        source = approve_source(
            ApproveSourceCommand(
                source_id=source_id,
                actor=body.actor,
                license_type=body.license_type,
                evidence_ref=body.evidence_ref,
                attribution_text=body.attribution_text,
                may_translate=body.may_translate,
                may_modify_audio=body.may_modify_audio,
                may_subtitle=body.may_subtitle,
                may_republish=body.may_republish,
                may_commercial_use=body.may_commercial_use,
                expires_at=body.expires_at,
            ),
            uow=uow,
            clock=clock,
        )
    except SourceNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SourceOut.of(source)


@router.post("/{source_id}/reject", response_model=SourceOut)
def reject(source_id: int, body: RejectIn, uow: Uow, clock: Clock) -> SourceOut:
    try:
        source = reject_source(
            source_id, reason=body.reason, actor=body.actor, uow=uow, clock=clock
        )
    except SourceNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SourceOut.of(source)


@router.get("", response_model=list[SourceOut])
def list_sources(
    uow: Uow,
    status: ApprovalStatus = STATUS_QUERY,
    limit: int = Query(default=100, le=500),
) -> list[SourceOut]:
    with uow:
        return [SourceOut.of(s) for s in uow.sources.list_by_status(status, limit=limit)]


@router.get("/{source_id}", response_model=SourceOut)
def get_source(source_id: int, uow: Uow) -> SourceOut:
    with uow:
        source = uow.sources.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail=f"không có nguồn #{source_id}")
    return SourceOut.of(source)

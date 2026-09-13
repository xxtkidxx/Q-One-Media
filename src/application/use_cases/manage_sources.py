"""Use case khai báo và duyệt nguồn.

Đây là cửa vào duy nhất để một nguồn trở thành ``approved``. Không có đường nào
khác trong hệ thống đặt ``status = approved``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.application.ports import Clock, UnitOfWork
from src.domain.errors import DomainError
from src.domain.sourcing.entities import Source
from src.domain.sourcing.value_objects import (
    ApprovalStatus,
    ContentType,
    Language,
    LicenseEvidence,
    LicenseScope,
    LicenseType,
    Platform,
    SourceKind,
    SourceUrl,
)


class SourceAlreadyDeclared(DomainError):
    pass


class SourceNotFound(DomainError):
    pass


@dataclass(frozen=True, slots=True)
class DeclareSourceCommand:
    url: str
    platform: Platform
    kind: SourceKind
    content_type: ContentType = ContentType.VIDEO
    display_name: str | None = None
    audio_lang: str = "en"
    has_baked_watermark: bool = False
    topics: tuple[str, ...] = ()
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class ApproveSourceCommand:
    source_id: int
    actor: str
    license_type: LicenseType
    evidence_ref: str
    attribution_text: str | None = None
    may_translate: bool = False
    may_modify_audio: bool = False
    may_subtitle: bool = False
    may_republish: bool = False
    may_commercial_use: bool = False
    expires_at: datetime | None = None


def declare_source(cmd: DeclareSourceCommand, *, uow: UnitOfWork, actor: str) -> Source:
    """Khai báo một nguồn. Luôn vào trạng thái ``pending`` — không có đường tự duyệt."""
    url = SourceUrl(cmd.url)
    with uow:
        if uow.sources.get_by_url(url) is not None:
            raise SourceAlreadyDeclared(f"nguồn {url.host} đã được khai báo")
        source = uow.sources.add(
            Source(
                platform=cmd.platform,
                kind=cmd.kind,
                url=url,
                content_type=cmd.content_type,
                display_name=cmd.display_name,
                audio_lang=Language(cmd.audio_lang),
                has_baked_watermark=cmd.has_baked_watermark,
                topics=cmd.topics,
                notes=cmd.notes,
            )
        )
        assert source.id is not None
        uow.audit.record(
            entity="source",
            entity_id=source.id,
            action="declared",
            actor=actor,
            detail={"url": cmd.url, "platform": str(cmd.platform)},
        )
        uow.commit()
    return source


def approve_source(cmd: ApproveSourceCommand, *, uow: UnitOfWork, clock: Clock) -> Source:
    """Duyệt nguồn kèm bằng chứng và phạm vi quyền.

    ``LicenseEvidence`` tự kiểm bất biến (bằng chứng không rỗng, CC BY bắt buộc
    ghi nguồn) nên không cần kiểm lại ở đây.
    """
    evidence = LicenseEvidence(
        license_type=cmd.license_type,
        evidence_ref=cmd.evidence_ref,
        attribution_text=cmd.attribution_text,
    )
    scope = LicenseScope(
        may_translate=cmd.may_translate,
        may_modify_audio=cmd.may_modify_audio,
        may_subtitle=cmd.may_subtitle,
        may_republish=cmd.may_republish,
        may_commercial_use=cmd.may_commercial_use,
    )
    with uow:
        source = uow.sources.get(cmd.source_id)
        if source is None:
            raise SourceNotFound(f"không có nguồn #{cmd.source_id}")
        source.approve(
            by=cmd.actor,
            evidence=evidence,
            scope=scope,
            at=clock.now(),
            expires_at=cmd.expires_at,
        )
        uow.sources.update(source)
        uow.audit.record(
            entity="source",
            entity_id=cmd.source_id,
            action="approved",
            actor=cmd.actor,
            detail={
                "license_type": str(cmd.license_type),
                "evidence_ref": cmd.evidence_ref,
                "scope": {
                    "may_translate": cmd.may_translate,
                    "may_modify_audio": cmd.may_modify_audio,
                    "may_subtitle": cmd.may_subtitle,
                    "may_republish": cmd.may_republish,
                    "may_commercial_use": cmd.may_commercial_use,
                },
                "expires_at": cmd.expires_at.isoformat() if cmd.expires_at else None,
            },
        )
        uow.commit()
    return source


def reject_source(
    source_id: int, *, reason: str, actor: str, uow: UnitOfWork, clock: Clock
) -> Source:
    with uow:
        source = uow.sources.get(source_id)
        if source is None:
            raise SourceNotFound(f"không có nguồn #{source_id}")
        source.reject(by=actor, reason=reason, at=clock.now())
        uow.sources.update(source)
        uow.audit.record(
            entity="source",
            entity_id=source_id,
            action="rejected",
            actor=actor,
            detail={"reason": reason},
        )
        uow.commit()
    return source


def expire_stale_licenses(*, uow: UnitOfWork, clock: Clock) -> int:
    """Quét định kỳ: license quá hạn chuyển sang ``expired``.

    Gate đã tự từ chối nguồn quá hạn dù cột ``status`` chưa đổi, nên việc này
    chỉ để bảng nguồn nói đúng sự thật cho người đọc.
    """
    now = clock.now()
    changed = 0
    with uow:
        for source in uow.sources.list_by_status(ApprovalStatus.APPROVED, limit=1000):
            if source.expires_at is not None and source.expires_at <= now:
                source.expire()
                uow.sources.update(source)
                assert source.id is not None
                uow.audit.record(
                    entity="source",
                    entity_id=source.id,
                    action="expired",
                    detail={"expires_at": source.expires_at.isoformat()},
                )
                changed += 1
        uow.commit()
    return changed

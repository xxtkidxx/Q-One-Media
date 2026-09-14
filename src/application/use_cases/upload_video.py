"""Đăng ký một file video do người dùng tải lên và đưa thẳng vào pipeline."""

from __future__ import annotations

from src.application.ports import Clock, UnitOfWork
from src.domain.errors import DomainError, OwnershipMismatch
from src.domain.production.entities import Item
from src.domain.production.value_objects import AspectRatio, MediaAsset
from src.domain.scheduling.entities import Job, JobTask
from src.domain.sourcing.value_objects import SourceUrl


class SourceNotFound(DomainError):
    pass


def register_uploaded_video(
    *,
    source_id: int,
    upload_id: str,
    original_filename: str,
    asset: MediaAsset,
    duration_sec: int,
    aspect_ratio: AspectRatio,
    uow: UnitOfWork,
    clock: Clock,
    actor: str,
) -> Item:
    """Gắn file đã lưu với nguồn đã duyệt và xếp bước tách audio đầu tiên."""
    with uow:
        source = uow.sources.get(source_id)
        if source is None:
            raise SourceNotFound(f"nguồn #{source_id} không tồn tại")
        clearance = source.clear_for_download(clock.now())
        if not source.ownership_is_verifiable:
            raise OwnershipMismatch(
                f"nguồn #{source_id} chưa có external_owner_id để xác minh chủ sở hữu"
            )

        item = Item.accept(
            url=SourceUrl(f"https://upload.qone.local/{source_id}/{upload_id}"),
            clearance=clearance,
            external_id=f"upload-{upload_id}",
            title_original=original_filename,
        )
        item.mark_downloaded(
            path=asset,
            duration_sec=duration_sec,
            aspect_ratio=aspect_ratio,
        )
        uow.items.add(item)
        assert item.id is not None
        uow.jobs.enqueue(Job(task=JobTask.SEPARATE, item_id=item.id))
        uow.audit.record(
            entity="item",
            entity_id=item.id,
            action="video_uploaded",
            actor=actor,
            detail={
                "source_id": source_id,
                "filename": original_filename,
                "path": asset.relative_path,
            },
        )
        uow.commit()
    return item

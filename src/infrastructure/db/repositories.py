"""Repository trên SQLAlchemy. Hiện thực các Protocol ở tầng domain."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from src.domain.production.entities import Item
from src.domain.production.value_objects import ItemStage
from src.domain.publishing.entities import Publication
from src.domain.publishing.value_objects import PublishPlatform, PublishStatus
from src.domain.scheduling.entities import Job, JobStatus, JobTask
from src.domain.sourcing.entities import Source
from src.domain.sourcing.value_objects import ApprovalStatus, SourceUrl
from src.infrastructure.db import mappers
from src.infrastructure.db.orm import (
    AuditLogRow,
    ItemRow,
    JobRow,
    PublicationRow,
    SourceRow,
)


class SqlSourceRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(self, source: Source) -> Source:
        row = mappers.source_to_row(source)
        self._s.add(row)
        self._s.flush()
        source.id = row.id
        return source

    def get(self, source_id: int) -> Source | None:
        row = self._s.get(SourceRow, source_id)
        return mappers.source_to_domain(row) if row else None

    def get_by_url(self, url: SourceUrl) -> Source | None:
        row = self._s.scalar(select(SourceRow).where(SourceRow.source_url == url.value))
        return mappers.source_to_domain(row) if row else None

    def find_owning(self, item_url: SourceUrl) -> Source | None:
        """Lọc thô bằng host trong SQL, rồi để ``Source.claims()`` quyết định.

        Quy tắc "nguồn nào bao trùm URL nào" là nghiệp vụ, nên nó phải sống ở
        tầng domain, không nằm rải trong câu SQL. Bảng ``sources`` chỉ có cỡ vài
        chục dòng (nguồn do người khai báo từng cái một) nên quét thô ở đây
        không phải vấn đề hiệu năng.

        Kết quả chỉ là **ứng viên** — quyền sở hữu thật được xác minh bằng
        ``Source.assert_owns()`` với id chủ kênh lấy từ metadata.
        """
        host = item_url.host
        rows = self._s.scalars(
            select(SourceRow).where(SourceRow.source_url.ilike(f"%{host}%"))
        ).all()
        candidates = [
            s for s in (mappers.source_to_domain(r) for r in rows) if s.claims(item_url)
        ]
        if not candidates:
            return None
        # Khớp chính xác (single-url) thắng nguồn dạng bao; trong cùng loại thì
        # URL dài hơn cụ thể hơn nên thắng.
        return max(candidates, key=lambda s: (not s.kind.is_container, len(s.url.value)))

    def list_by_status(self, status: ApprovalStatus, *, limit: int = 100) -> list[Source]:
        rows = self._s.scalars(
            select(SourceRow).where(SourceRow.status == status).order_by(SourceRow.id).limit(limit)
        ).all()
        return [mappers.source_to_domain(r) for r in rows]

    def update(self, source: Source) -> None:
        assert source.id is not None
        row = self._s.get(SourceRow, source.id)
        if row is None:
            raise LookupError(f"không có nguồn #{source.id} để cập nhật")
        mappers.source_apply(row, source)
        self._s.flush()


class SqlItemRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(self, item: Item) -> Item:
        row = mappers.item_to_row(item)
        self._s.add(row)
        self._s.flush()
        item.id = row.id
        return item

    def get(self, item_id: int) -> Item | None:
        row = self._s.get(ItemRow, item_id)
        return mappers.item_to_domain(row) if row else None

    def get_by_url(self, url: SourceUrl) -> Item | None:
        row = self._s.scalar(select(ItemRow).where(ItemRow.item_url == url.value))
        return mappers.item_to_domain(row) if row else None

    def list_by_stage(self, stage: ItemStage, *, limit: int = 50) -> list[Item]:
        rows = self._s.scalars(
            select(ItemRow).where(ItemRow.stage == stage).order_by(ItemRow.id).limit(limit)
        ).all()
        return [mappers.item_to_domain(r) for r in rows]

    def count_by_stage(self) -> dict[ItemStage, int]:
        rows = self._s.execute(
            select(ItemRow.stage, func.count()).group_by(ItemRow.stage)
        ).all()
        return {ItemStage(stage): count for stage, count in rows}

    def list_children(self, parent_item_id: int) -> list[Item]:
        rows = self._s.scalars(
            select(ItemRow)
            .where(ItemRow.parent_item_id == parent_item_id)
            .order_by(ItemRow.clip_index)
        ).all()
        return [mappers.item_to_domain(row) for row in rows]

    def update(self, item: Item) -> None:
        assert item.id is not None
        row = self._s.get(ItemRow, item.id)
        if row is None:
            raise LookupError(f"không có item #{item.id} để cập nhật")
        mappers.item_apply(row, item)
        self._s.flush()


class SqlPublicationRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(self, publication: Publication) -> Publication:
        row = mappers.publication_to_row(publication)
        self._s.add(row)
        self._s.flush()
        publication.id = row.id
        return publication

    def get(self, publication_id: int) -> Publication | None:
        row = self._s.get(PublicationRow, publication_id)
        return mappers.publication_to_domain(row) if row else None

    def get_for(self, item_id: int, platform: PublishPlatform) -> Publication | None:
        row = self._s.scalar(
            select(PublicationRow).where(
                PublicationRow.item_id == item_id, PublicationRow.platform == platform
            )
        )
        return mappers.publication_to_domain(row) if row else None

    def list_for_item(self, item_id: int) -> list[Publication]:
        rows = self._s.scalars(
            select(PublicationRow).where(PublicationRow.item_id == item_id)
        ).all()
        return [mappers.publication_to_domain(r) for r in rows]

    def count_published_today(self, platform: PublishPlatform) -> int:
        """Đếm theo cửa sổ 24 giờ trượt, không theo ngày lịch.

        Hạn mức của nền tảng tính theo 24 giờ (TikTok ghi rõ "trong mỗi cửa sổ
        24 giờ"), nên đếm theo ngày lịch sẽ cho phép vượt quanh nửa đêm.
        """
        since = datetime.now(UTC) - timedelta(hours=24)
        return (
            self._s.scalar(
                select(func.count())
                .select_from(PublicationRow)
                .where(
                    PublicationRow.platform == platform,
                    PublicationRow.status == PublishStatus.PUBLISHED,
                    PublicationRow.published_at >= since,
                )
            )
            or 0
        )

    def update(self, publication: Publication) -> None:
        assert publication.id is not None
        row = self._s.get(PublicationRow, publication.id)
        if row is None:
            raise LookupError(f"không có publication #{publication.id} để cập nhật")
        mappers.publication_apply(row, publication)
        self._s.flush()


class SqlJobRepository:
    """Hàng đợi trên Postgres. Không cần Redis cho khối lượng của dự án này."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def enqueue(self, job: Job) -> Job:
        row = mappers.job_to_row(job)
        self._s.add(row)
        self._s.flush()
        job.id = row.id
        return job

    def get(self, job_id: int) -> Job | None:
        row = self._s.get(JobRow, job_id)
        return mappers.job_to_domain(row) if row else None

    def claim_next(self, *, worker: str, tasks: tuple[JobTask, ...] | None = None) -> Job | None:
        """``FOR UPDATE SKIP LOCKED``: nhiều worker không giành nhau, cũng không chặn nhau.

        ``SKIP LOCKED`` là phần quan trọng: không có nó, worker thứ hai sẽ *đợi*
        worker thứ nhất nhả khoá thay vì đi lấy việc khác — hàng đợi biến thành
        hàng một làn.
        """
        stmt = (
            select(JobRow)
            .where(JobRow.status == JobStatus.PENDING)
            .order_by(JobRow.priority, JobRow.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if tasks:
            stmt = stmt.where(JobRow.task.in_([str(t) for t in tasks]))
        row = self._s.scalar(stmt)
        if row is None:
            return None
        job = mappers.job_to_domain(row)
        job.claim(worker=worker, at=datetime.now(UTC))
        mappers.job_apply(row, job)
        self._s.flush()
        return job

    def update(self, job: Job) -> None:
        assert job.id is not None
        row = self._s.get(JobRow, job.id)
        if row is None:
            raise LookupError(f"không có job #{job.id} để cập nhật")
        mappers.job_apply(row, job)
        self._s.flush()

    def release_stale(self, *, older_than_sec: int) -> int:
        """Worker chết giữa đường thì việc bị treo ở ``running`` mãi — trả lại hàng đợi.

        Không đếm thêm lần thử: lần đó không phải lỗi nội dung, và đếm sẽ làm
        item tốt bị loại oan sau vài lần container restart.
        """
        cutoff = datetime.now(UTC) - timedelta(seconds=older_than_sec)
        result = self._s.execute(
            update(JobRow)
            .where(
                JobRow.status == JobStatus.RUNNING,
                JobRow.locked_at.is_not(None),
                JobRow.locked_at < cutoff,
            )
            .values(status=JobStatus.PENDING, locked_by=None, locked_at=None)
        )
        self._s.flush()
        return result.rowcount or 0


class SqlAuditLog:
    def __init__(self, session: Session) -> None:
        self._s = session

    def record(
        self,
        *,
        entity: str,
        entity_id: int,
        action: str,
        actor: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self._s.add(
            AuditLogRow(
                entity=entity,
                entity_id=entity_id,
                action=action,
                actor=actor,
                detail=detail,
            )
        )


def ping(session: Session) -> bool:
    return session.scalar(text("SELECT 1")) == 1

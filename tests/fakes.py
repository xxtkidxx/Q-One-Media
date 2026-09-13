"""Hiện thực in-memory của các port, dùng cho unit test.

Đây là lý do thực dụng của Clean Architecture trong dự án này: toàn bộ quy tắc
nghiệp vụ về license và duyệt nội dung test được trong vài chục milligiây, không
Postgres, không GPU, không token nền tảng.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.domain.production.entities import Item
from src.domain.production.value_objects import ItemStage
from src.domain.publishing.entities import Publication
from src.domain.publishing.value_objects import PublishPlatform, PublishStatus, VideoMetadata
from src.domain.scheduling.entities import Job, JobStatus, JobTask
from src.domain.sourcing.clearance import DownloadClearance, PublishClearance
from src.domain.sourcing.entities import Source
from src.domain.sourcing.value_objects import ApprovalStatus, SourceUrl


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def advance(self, **kw) -> None:
        self._now += timedelta(**kw)


class FakeAuditLog:
    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def record(
        self,
        *,
        entity: str,
        entity_id: int,
        action: str,
        actor: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.entries.append(
            {
                "entity": entity,
                "entity_id": entity_id,
                "action": action,
                "actor": actor,
                "detail": detail or {},
            }
        )

    def actions(self) -> list[str]:
        return [e["action"] for e in self.entries]


class _Seq:
    def __init__(self) -> None:
        self._n = 0

    def next(self) -> int:
        self._n += 1
        return self._n


class FakeSourceRepository:
    def __init__(self, seq: _Seq) -> None:
        self._seq = seq
        self._rows: dict[int, Source] = {}

    def add(self, source: Source) -> Source:
        source.id = self._seq.next()
        self._rows[source.id] = source
        return source

    def get(self, source_id: int) -> Source | None:
        return self._rows.get(source_id)

    def get_by_url(self, url: SourceUrl) -> Source | None:
        return next((s for s in self._rows.values() if s.url.value == url.value), None)

    def find_owning(self, item_url: SourceUrl) -> Source | None:
        """Khớp theo host, rồi ưu tiên nguồn có URL là tiền tố dài nhất.

        Bản thật (Postgres) cần khớp tinh hơn — theo channel id, theo user path.
        Ở đây đủ để test quy tắc, và điều đó là chủ ý: fake không phải bản nháp
        của production, nó là bản đơn giản nhất còn đúng nghiệp vụ.
        """
        candidates = [s for s in self._rows.values() if s.url.host == item_url.host]
        if not candidates:
            return None
        return max(candidates, key=lambda s: len(s.url.value))

    def list_by_status(self, status: ApprovalStatus, *, limit: int = 100) -> list[Source]:
        return [s for s in self._rows.values() if s.status is status][:limit]

    def update(self, source: Source) -> None:
        assert source.id is not None
        self._rows[source.id] = source


class FakeItemRepository:
    def __init__(self, seq: _Seq) -> None:
        self._seq = seq
        self._rows: dict[int, Item] = {}

    def add(self, item: Item) -> Item:
        item.id = self._seq.next()
        self._rows[item.id] = item
        return item

    def get(self, item_id: int) -> Item | None:
        return self._rows.get(item_id)

    def get_by_url(self, url: SourceUrl) -> Item | None:
        return next((i for i in self._rows.values() if i.url.value == url.value), None)

    def list_by_stage(self, stage: ItemStage, *, limit: int = 50) -> list[Item]:
        return [i for i in self._rows.values() if i.stage is stage][:limit]

    def count_by_stage(self) -> dict[ItemStage, int]:
        out: dict[ItemStage, int] = {}
        for i in self._rows.values():
            out[i.stage] = out.get(i.stage, 0) + 1
        return out

    def update(self, item: Item) -> None:
        assert item.id is not None
        self._rows[item.id] = item


class FakePublicationRepository:
    def __init__(self, seq: _Seq) -> None:
        self._seq = seq
        self._rows: dict[int, Publication] = {}

    def add(self, publication: Publication) -> Publication:
        publication.id = self._seq.next()
        self._rows[publication.id] = publication
        return publication

    def get(self, publication_id: int) -> Publication | None:
        return self._rows.get(publication_id)

    def get_for(self, item_id: int, platform: PublishPlatform) -> Publication | None:
        return next(
            (
                p
                for p in self._rows.values()
                if p.item_id == item_id and p.platform is platform
            ),
            None,
        )

    def list_for_item(self, item_id: int) -> list[Publication]:
        return [p for p in self._rows.values() if p.item_id == item_id]

    def count_published_today(self, platform: PublishPlatform) -> int:
        return sum(
            1
            for p in self._rows.values()
            if p.platform is platform and p.status is PublishStatus.PUBLISHED
        )

    def update(self, publication: Publication) -> None:
        assert publication.id is not None
        self._rows[publication.id] = publication


class FakeJobRepository:
    def __init__(self, seq: _Seq) -> None:
        self._seq = seq
        self._rows: dict[int, Job] = {}

    def enqueue(self, job: Job) -> Job:
        job.id = self._seq.next()
        self._rows[job.id] = job
        return job

    def get(self, job_id: int) -> Job | None:
        return self._rows.get(job_id)

    def claim_next(self, *, worker: str, tasks: tuple[JobTask, ...] | None = None) -> Job | None:
        pending = [
            j
            for j in self._rows.values()
            if j.status is JobStatus.PENDING and (tasks is None or j.task in tasks)
        ]
        if not pending:
            return None
        job = min(pending, key=lambda j: (j.priority, j.id or 0))
        job.claim(worker=worker, at=datetime.now())
        return job

    def update(self, job: Job) -> None:
        assert job.id is not None
        self._rows[job.id] = job

    def release_stale(self, *, older_than_sec: int) -> int:
        return 0

    def all(self) -> list[Job]:
        return list(self._rows.values())


class FakeUnitOfWork:
    """UoW in-memory. ``commit()`` chỉ đếm số lần — dữ liệu đã ở trong dict.

    Vẫn theo dõi commit/rollback vì test cần biết use case có commit hay không:
    quên commit trong bản thật là mất dữ liệu.
    """

    def __init__(self) -> None:
        seq = _Seq()
        self.sources = FakeSourceRepository(seq)
        self.items = FakeItemRepository(seq)
        self.publications = FakePublicationRepository(seq)
        self.jobs = FakeJobRepository(seq)
        self.audit = FakeAuditLog()
        self.commits = 0
        self.rollbacks = 0
        self._depth = 0

    def __enter__(self) -> FakeUnitOfWork:
        self._depth += 1
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._depth -= 1
        if exc_type is not None:
            self.rollbacks += 1

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


# ---------------- Gateway ----------------


@dataclass
class FakeDownloadResult:
    path: Path
    duration_sec: int | None = 600
    width: int | None = 1920
    height: int | None = 1080
    external_id: str | None = "abc123"
    title: str | None = "Vendor demo"


class FakeDownloader:
    """Ghi lại clearance đã nhận — test kiểm được là gate thật sự chạy trước."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, DownloadClearance]] = []

    def download(
        self, *, url: str, clearance: DownloadClearance, dest_dir: Path
    ) -> FakeDownloadResult:
        self.calls.append((url, clearance))
        return FakeDownloadResult(path=dest_dir / "video.mp4")


@dataclass
class FakePublishResult:
    remote_id: str
    remote_url: str | None


@dataclass
class FakePublisher:
    platform: PublishPlatform
    fail_with: Exception | None = None
    calls: list[VideoMetadata] = field(default_factory=list)

    def publish(
        self, *, video: Path, metadata: VideoMetadata, clearance: PublishClearance
    ) -> FakePublishResult:
        self.calls.append(metadata)
        if self.fail_with is not None:
            raise self.fail_with
        return FakePublishResult(
            remote_id=f"{self.platform}-remote-1",
            remote_url=f"https://{self.platform}.example/watch/1",
        )

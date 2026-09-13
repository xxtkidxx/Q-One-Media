"""Port của hàng đợi việc."""

from __future__ import annotations

from typing import Protocol

from src.domain.scheduling.entities import Job, JobTask


class JobRepository(Protocol):
    def enqueue(self, job: Job) -> Job: ...

    def get(self, job_id: int) -> Job | None: ...

    def claim_next(self, *, worker: str, tasks: tuple[JobTask, ...] | None = None) -> Job | None:
        """Lấy một việc pending và khoá nó ngay trong cùng một transaction.

        Hiện thực bằng ``SELECT ... FOR UPDATE SKIP LOCKED`` nên nhiều worker
        chạy song song không giành cùng một việc và cũng không chặn nhau.
        """
        ...

    def update(self, job: Job) -> None: ...

    def release_stale(self, *, older_than_sec: int) -> int:
        """Trả lại hàng đợi những việc bị worker chết giữa đường (locked_at quá cũ)."""
        ...

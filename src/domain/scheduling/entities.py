"""Aggregate ``Job`` — một việc nặng cho worker.

Hàng đợi chạy trên Postgres (``FOR UPDATE SKIP LOCKED``), không thêm Redis: một
hệ thống 20–30 video/tháng không cần thêm một thành phần phải vận hành.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from src.domain.errors import InvalidTransition, InvariantViolation


class JobTask(StrEnum):
    """Các bước nặng — **mỗi thành viên phải có handler** trong ``interfaces/worker``.

    Không có ``mix`` và ``reframe`` riêng: hai việc đó nằm bên trong ``render``, vì
    thứ tự cắt → reframe → trộn → burn phụ đề là một chuỗi ffmpeg không tách rời
    được (tách ra thì mỗi bước phải encode lại một lần nữa). Để chúng thành
    ``JobTask`` riêng mà không có handler là mời một job treo vĩnh viễn.
    """

    DOWNLOAD = "download"
    SEPARATE = "separate"
    TRANSCRIBE = "transcribe"
    PICK_SEGMENT = "pick_segment"
    WRITE_SCRIPT = "write_script"
    SYNTHESIZE = "synthesize"
    ALIGN = "align"
    RENDER = "render"
    PUBLISH = "publish"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


_ALLOWED: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.PENDING: frozenset({JobStatus.RUNNING, JobStatus.CANCELLED}),
    JobStatus.RUNNING: frozenset({JobStatus.DONE, JobStatus.FAILED, JobStatus.PENDING}),
    JobStatus.FAILED: frozenset({JobStatus.PENDING, JobStatus.CANCELLED}),
    JobStatus.DONE: frozenset(),
    JobStatus.CANCELLED: frozenset(),
}

# Việc tải Douyin phải chạy trước mọi việc khác: URL CDN hết hạn trong vài giờ.
PRIORITY_URGENT = 10
PRIORITY_NORMAL = 100
PRIORITY_LOW = 200


@dataclass(eq=False)
class Job:
    task: JobTask
    item_id: int | None = None
    id: int | None = None
    status: JobStatus = JobStatus.PENDING
    priority: int = PRIORITY_NORMAL
    attempts: int = 0
    max_attempts: int = 3
    payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    locked_by: str | None = None
    locked_at: datetime | None = None
    finished_at: datetime | None = None

    def _to(self, target: JobStatus) -> None:
        if target not in _ALLOWED[self.status]:
            raise InvalidTransition(
                f"job #{self.id} ({self.task}): không đi được từ {self.status} sang {target}"
            )
        self.status = target

    def claim(self, *, worker: str, at: datetime) -> None:
        if not worker.strip():
            raise InvariantViolation("worker phải có tên để lần lại được khi treo")
        self.locked_by = worker
        self.locked_at = at
        self.attempts += 1
        self._to(JobStatus.RUNNING)

    def succeed(self, at: datetime) -> None:
        self.finished_at = at
        self.error = None
        self.locked_by = None
        self._to(JobStatus.DONE)

    def fail(self, *, error: str, at: datetime, retryable: bool) -> None:
        """Lỗi có phân loại.

        Lỗi **không** retry được (license, input sai, cấu hình) thì dừng luôn —
        thử lại chỉ tốn thời gian và làm nhiễu log. Lỗi mạng/rate limit thì xếp lại.
        """
        self.error = error
        self.locked_by = None
        self.locked_at = None
        if retryable and self.attempts < self.max_attempts:
            self._to(JobStatus.PENDING)
        else:
            self.finished_at = at
            self._to(JobStatus.FAILED)

    def cancel(self) -> None:
        self._to(JobStatus.CANCELLED)

    @property
    def attempts_left(self) -> int:
        return max(0, self.max_attempts - self.attempts)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Job):
            return NotImplemented
        return self.id is not None and self.id == other.id

    def __hash__(self) -> int:
        return hash(("Job", self.id))

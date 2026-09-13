"""Worker: lấy việc từ hàng đợi Postgres và chạy.

Vòng lặp cố tình đơn giản — mỗi lần một việc, không thread pool. Lý do: các
bước nặng (WhisperX, Demucs, VoxCPM2) đều chiếm trọn GPU, nên chạy song song
trong cùng tiến trình chỉ làm tăng nguy cơ hết VRAM chứ không nhanh hơn. Muốn
nhiều việc cùng lúc thì tăng số container worker, và ``SKIP LOCKED`` đã bảo đảm
chúng không giành nhau.

Việc nào chưa có handler thì **thất bại rõ ràng**, không bỏ qua im lặng: một
job pending mãi mãi khó phát hiện hơn một job failed có thông báo.
"""

from __future__ import annotations

import os
import signal
import socket
import time
from collections.abc import Callable
from datetime import UTC, datetime

from src.application.use_cases.download_item import download_item
from src.domain.scheduling.entities import Job, JobTask
from src.infrastructure.clock import SystemClock
from src.infrastructure.db.uow import SqlUnitOfWork, make_engine, make_session_factory
from src.infrastructure.ingest.ytdlp import YtDlpDownloader, YtDlpProbe
from src.shared.config import Settings, get_settings
from src.shared.logging import configure_logging, get_logger

log = get_logger(__name__)

IDLE_SLEEP_SEC = 3.0
STALE_LOCK_SEC = 3600  # job running quá 1 giờ coi như worker đã chết

_shutdown = False


def _request_shutdown(signum: int, _frame: object) -> None:
    """Dừng êm: làm xong việc đang chạy rồi mới thoát.

    Quan trọng với việc tải và render — bị cắt giữa đường thì để lại file dở
    trong ``media/work`` và một job ở trạng thái ``running`` không ai nhận lại.
    """
    global _shutdown
    _shutdown = True
    log.info("worker.shutdown.requested", signal=signum)


Handler = Callable[[Job, SqlUnitOfWork, Settings], None]


def _handle_download(job: Job, uow: SqlUnitOfWork, settings: Settings) -> None:
    if job.item_id is None:
        raise ValueError("job download thiếu item_id")
    download_item(
        job.item_id,
        downloader=YtDlpDownloader(),
        probe=YtDlpProbe(),
        media_root=settings.media_root,
        uow=uow,
        clock=SystemClock(),
    )


# Các handler còn lại thuộc G2.6–G2.13, chưa hiện thực. Không đăng ký ở đây thì
# job sẽ failed kèm thông báo rõ tên bước — dễ thấy hơn là pending vô hạn.
HANDLERS: dict[JobTask, Handler] = {
    JobTask.DOWNLOAD: _handle_download,
}


def run_once(uow: SqlUnitOfWork, settings: Settings, *, worker_id: str) -> bool:
    """Lấy và chạy một việc. Trả về False nếu hàng đợi rỗng."""
    with uow:
        job = uow.jobs.claim_next(worker=worker_id, tasks=tuple(HANDLERS))
        uow.commit()
    if job is None:
        return False

    log.info("worker.job.start", job_id=job.id, task=str(job.task), item_id=job.item_id)
    handler = HANDLERS.get(job.task)
    try:
        if handler is None:
            raise NotImplementedError(f"chưa có handler cho bước {job.task}")
        handler(job, uow, settings)
    except Exception as exc:  # noqa: BLE001 — handler nào cũng có thể ném gì đó
        # Phân loại theo thuộc tính ``retryable`` mà lớp lỗi tự khai. Lỗi license
        # và lỗi input không retry; lỗi mạng và rate limit thì có.
        retryable = bool(getattr(exc, "retryable", False))
        with uow:
            job.fail(error=f"{type(exc).__name__}: {exc}", at=datetime.now(UTC), retryable=retryable)
            uow.jobs.update(job)
            uow.commit()
        log.error(
            "worker.job.failed",
            job_id=job.id,
            task=str(job.task),
            error=str(exc),
            kind=type(exc).__name__,
            retryable=retryable,
            attempts_left=job.attempts_left,
        )
        return True

    with uow:
        job.succeed(at=datetime.now(UTC))
        uow.jobs.update(job)
        uow.commit()
    log.info("worker.job.done", job_id=job.id, task=str(job.task))
    return True


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.is_prod)
    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    worker_id = f"{socket.gethostname()}-{os.getpid()}"
    engine = make_engine(settings.database_url)
    uow = SqlUnitOfWork(make_session_factory(engine))

    settings.paths.ensure()
    log.info(
        "worker.start",
        worker_id=worker_id,
        tasks=[str(t) for t in HANDLERS],
        gpu_count=settings.gpu_count,
    )

    idle_rounds = 0
    while not _shutdown:
        try:
            did_work = run_once(uow, settings, worker_id=worker_id)
        except Exception as exc:  # noqa: BLE001 — vòng lặp không được chết vì một lỗi DB
            log.error("worker.loop.error", error=str(exc), kind=type(exc).__name__)
            time.sleep(IDLE_SLEEP_SEC)
            continue

        if did_work:
            idle_rounds = 0
            continue

        idle_rounds += 1
        # Mỗi ~5 phút rỗi thì thu hồi job của worker đã chết.
        if idle_rounds % int(300 / IDLE_SLEEP_SEC) == 0:
            with uow:
                released = uow.jobs.release_stale(older_than_sec=STALE_LOCK_SEC)
                uow.commit()
            if released:
                log.warning("worker.stale.released", count=released)
        time.sleep(IDLE_SLEEP_SEC)

    log.info("worker.stopped", worker_id=worker_id)


if __name__ == "__main__":
    main()

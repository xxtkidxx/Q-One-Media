"""Worker: lấy việc từ hàng đợi Postgres và chạy.

Vòng lặp cố tình đơn giản — **một việc một lần, không thread pool**. Lý do: các
bước nặng (Whisper large-v3, Demucs, VoxCPM2) đều chiếm trọn GPU, nên chạy song
song trong cùng tiến trình chỉ làm tăng nguy cơ hết VRAM chứ không nhanh hơn.
Muốn nhiều việc cùng lúc thì tăng số container worker, và ``FOR UPDATE SKIP
LOCKED`` đã bảo đảm chúng không giành nhau.

Việc nào chưa có handler thì **thất bại rõ ràng**, không bỏ qua im lặng: một job
pending mãi mãi khó phát hiện hơn một job failed có thông báo.
"""

from __future__ import annotations

import os
import signal
import socket
import time
from datetime import UTC, datetime

from src.domain.production.value_objects import ItemStage
from src.domain.scheduling.entities import Job
from src.infrastructure.db.uow import SqlUnitOfWork, make_engine, make_session_factory
from src.interfaces.worker.handlers import (
    HANDLERS,
    REQUIRED_STAGE,
    _ChainRedirected,
    enqueue_next,
)
from src.shared.config import Settings, get_settings
from src.shared.logging import configure_logging, get_logger

log = get_logger(__name__)

IDLE_SLEEP_SEC = 3.0
STALE_LOCK_SEC = 3600  # job running quá 1 giờ coi như worker đã chết
STALE_SWEEP_EVERY = int(300 / IDLE_SLEEP_SEC)

_shutdown = False


def _request_shutdown(signum: int, _frame: object) -> None:
    """Dừng êm: làm xong việc đang chạy rồi mới thoát.

    Quan trọng với việc tải và render — bị cắt giữa đường thì để lại file dở
    trong ``media/work`` và một job ở trạng thái ``running`` không ai nhận lại.
    """
    global _shutdown
    _shutdown = True
    log.info("worker.shutdown.requested", signal=signum)


def _stage_ok(job: Job, uow: SqlUnitOfWork) -> tuple[bool, str]:
    """Kiểm item đang ở đúng bước trước khi chạy handler.

    Cần thiết vì hàng đợi có thể chứa job cũ: người duyệt trả item về viết lại
    thì job ``render`` đã xếp trước đó vẫn còn đó. Không kiểm thì nó sẽ render
    lại bản cũ và đẩy item đi sai đường.
    """
    wanted = REQUIRED_STAGE.get(job.task)
    if wanted is None or job.item_id is None:
        return True, ""
    with uow:
        item = uow.items.get(job.item_id)
    if item is None:
        return False, f"item #{job.item_id} không còn tồn tại"
    if item.stage not in wanted:
        return False, (
            f"item #{job.item_id} đang ở {item.stage}, việc {job.task} cần "
            f"{' hoặc '.join(str(s) for s in wanted)}"
        )
    return True, ""


def _mark_item_failed(job: Job, uow: SqlUnitOfWork, error: str) -> None:
    """Phản ánh lỗi job không retry được lên item để UI không hiện stage cũ."""
    if job.item_id is None:
        return
    with uow:
        item = uow.items.get(job.item_id)
        if item is None or item.stage.is_terminal or item.stage is ItemStage.FAILED:
            return
        item.fail(error)
        uow.items.update(item)
        uow.commit()


def run_once(uow: SqlUnitOfWork, settings: Settings, *, worker_id: str) -> bool:
    """Lấy và chạy một việc. Trả về False nếu hàng đợi rỗng."""
    with uow:
        job = uow.jobs.claim_next(worker=worker_id, tasks=tuple(HANDLERS))
        uow.commit()
    if job is None:
        return False

    log.info("worker.job.start", job_id=job.id, task=str(job.task), item_id=job.item_id)

    ok, why = _stage_ok(job, uow)
    if not ok:
        # Không phải lỗi: job đã lạc hậu. Đánh dấu cancelled để hàng đợi sạch,
        # và KHÔNG xếp bước sau.
        with uow:
            job.cancel()
            uow.jobs.update(job)
            uow.commit()
        log.info("worker.job.stale", job_id=job.id, task=str(job.task), reason=why)
        return True

    handler = HANDLERS.get(job.task)
    try:
        if handler is None:
            raise NotImplementedError(f"chưa có handler cho bước {job.task}")
        handler(job, uow, settings)
    except _ChainRedirected as exc:
        # Handler đã tự xếp việc khác (ví dụ kịch bản tràn → viết lại). Job này
        # coi như xong, nhưng không xếp bước tiếp theo của chuỗi bình thường.
        with uow:
            job.succeed(at=datetime.now(UTC))
            job.error = str(exc)
            uow.jobs.update(job)
            uow.commit()
        log.info("worker.job.redirected", job_id=job.id, reason=str(exc))
        return True
    except Exception as exc:
        # Phân loại theo thuộc tính ``retryable`` mà chính lớp lỗi khai. Lỗi
        # license và lỗi input không retry; lỗi mạng và rate limit thì có.
        retryable = bool(getattr(exc, "retryable", False))
        error = f"{type(exc).__name__}: {exc}"
        if not retryable:
            _mark_item_failed(job, uow, error)
        with uow:
            job.fail(
                error=error,
                at=datetime.now(UTC),
                retryable=retryable,
            )
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

    if job.item_id is not None:
        enqueue_next(job, uow, item_id=job.item_id)
    return True


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.is_prod)
    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    worker_id = f"{socket.gethostname()}-{os.getpid()}"
    uow = SqlUnitOfWork(make_session_factory(make_engine(settings.database_url)))

    settings.paths.ensure()
    log.info(
        "worker.start",
        worker_id=worker_id,
        tasks=[str(t) for t in HANDLERS],
        gpu_count=settings.gpu_count,
        tts_engine=settings.tts.engine,
        speech_rate=settings.tts.measured_rate,
    )
    if settings.tts.measured_rate is None:
        log.warning(
            "worker.speech_rate.unmeasured",
            note="TTS_SYLLABLES_PER_SEC chưa đặt — bước viết kịch bản sẽ từ chối chạy (G0.7)",
        )

    idle_rounds = 0
    while not _shutdown:
        try:
            did_work = run_once(uow, settings, worker_id=worker_id)
        except Exception as exc:
            log.error("worker.loop.error", error=str(exc), kind=type(exc).__name__)
            time.sleep(IDLE_SLEEP_SEC)
            continue

        if did_work:
            idle_rounds = 0
            continue

        idle_rounds += 1
        if idle_rounds % STALE_SWEEP_EVERY == 0:
            with uow:
                released = uow.jobs.release_stale(older_than_sec=STALE_LOCK_SEC)
                uow.commit()
            if released:
                log.warning("worker.stale.released", count=released)
        time.sleep(IDLE_SLEEP_SEC)

    log.info("worker.stopped", worker_id=worker_id)


if __name__ == "__main__":
    main()

"""Health check. Phân biệt "tiến trình còn sống" với "phụ thuộc còn dùng được"."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response

from src.infrastructure.db.repositories import ping
from src.infrastructure.db.uow import SqlUnitOfWork
from src.interfaces.api.deps import get_config, get_uow
from src.shared.config import Settings

router = APIRouter(tags=["health"])

Uow = Annotated[SqlUnitOfWork, Depends(get_uow)]
Config = Annotated[Settings, Depends(get_config)]


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness: tiến trình còn sống. Không gọi DB, để restart loop không tự nuôi nó."""
    return {"status": "ok"}


@router.get("/readyz")
def readyz(uow: Uow, config: Config, response: Response) -> dict[str, Any]:
    """Readiness: có nhận việc được không. DB chết thì trả 503."""
    try:
        with uow:
            db_ok = ping(uow.session)
    except Exception as exc:  # noqa: BLE001 — driver DB ném nhiều họ exception
        response.status_code = 503
        return {"status": "degraded", "database": f"{type(exc).__name__}: {exc}"}

    if not db_ok:
        response.status_code = 503
        return {"status": "degraded", "database": "ping thất bại"}

    return {
        "status": "ok",
        "app_env": config.app_env,
        "database": "ok",
        "publish_enabled": config.publish.enabled,
        "tts_engine": config.tts.engine,
        "gpu_count": config.gpu_count,
    }

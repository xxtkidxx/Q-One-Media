"""Ứng dụng FastAPI.

Tầng này mỏng có chủ ý: nhận HTTP, gọi use case, đổi lỗi domain thành mã trạng
thái. Không có quy tắc nghiệp vụ nào ở đây — quy tắc nằm trong ``src/domain``.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.domain.errors import (
    DomainError,
    HumanReviewRequired,
    InvalidTransition,
    InvariantViolation,
    LicenseViolation,
)
from src.interfaces.api.routers import health, items, sources
from src.shared.config import get_settings
from src.shared.logging import configure_logging, get_logger

log = get_logger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.is_prod)

    app = FastAPI(
        title="Q One Media",
        version="0.1.0",
        description=(
            "Pipeline short video tiếng Việt cho NMI Technologies. "
            "Nguồn phải được khai báo và duyệt license trước khi nạp URL."
        ),
        docs_url="/docs",
    )
    app.include_router(health.router)
    app.include_router(sources.router)
    app.include_router(items.router)
    _install_error_handlers(app)
    return app


def _install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(LicenseViolation)
    async def _license(_: Request, exc: LicenseViolation) -> JSONResponse:
        """409 chứ không 403.

        Không phải "bạn không được phép gọi API này" mà là "trạng thái license
        của nguồn không cho phép việc này" — một xung đột trạng thái, và người
        gọi sửa được bằng cách đi duyệt nguồn.
        """
        log.warning("license.refused", error=str(exc), kind=type(exc).__name__)
        return JSONResponse(
            status_code=409,
            content={"error": str(exc), "kind": type(exc).__name__, "retryable": False},
        )

    @app.exception_handler(HumanReviewRequired)
    async def _review(_: Request, exc: HumanReviewRequired) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"error": str(exc), "kind": "HumanReviewRequired", "retryable": False},
        )

    @app.exception_handler(InvalidTransition)
    async def _transition(_: Request, exc: InvalidTransition) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"error": str(exc), "kind": "InvalidTransition", "retryable": False},
        )

    @app.exception_handler(InvariantViolation)
    async def _invariant(_: Request, exc: InvariantViolation) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": str(exc), "kind": "InvariantViolation", "retryable": False},
        )

    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={
                "error": str(exc),
                "kind": type(exc).__name__,
                "retryable": getattr(exc, "retryable", False),
            },
        )


app = create_app()

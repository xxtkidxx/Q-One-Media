"""Dependency injection cho FastAPI.

Tầng interface là nơi duy nhất biết cả cấu hình lẫn hạ tầng cụ thể. Use case chỉ
nhận port, nên đổi Postgres sang thứ khác không cần sửa một dòng nghiệp vụ nào.
"""

from __future__ import annotations

from functools import lru_cache

from src.infrastructure.clock import SystemClock
from src.infrastructure.db.uow import SqlUnitOfWork, make_engine, make_session_factory
from src.shared.config import Settings, get_settings


@lru_cache(maxsize=1)
def _session_factory():
    settings = get_settings()
    engine = make_engine(settings.database_url, echo=settings.log_level == "DEBUG")
    return make_session_factory(engine)


def get_uow() -> SqlUnitOfWork:
    return SqlUnitOfWork(_session_factory())


def get_clock() -> SystemClock:
    return SystemClock()


def get_config() -> Settings:
    return get_settings()


def reset_dependencies() -> None:
    """Dùng cho test tích hợp: bỏ cache engine sau khi đổi biến môi trường."""
    _session_factory.cache_clear()
    get_settings.cache_clear()

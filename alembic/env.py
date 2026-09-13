"""Alembic env.

Đọc ``DATABASE_URL`` từ biến môi trường, dùng lại ``normalize_database_url`` để
không có hai chỗ quyết định driver.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool

from src.infrastructure.db.orm import Base
from src.infrastructure.db.uow import make_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "thiếu DATABASE_URL — chạy trong container: make migrate"
        )
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # n8n có schema riêng; alembic không được dòm vào đó
        include_schemas=False,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = make_engine(_url())
    engine.dispose()  # không giữ pool cho một lần chạy migration
    with make_engine(_url(), echo=False).connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=False,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

"""Unit of Work trên SQLAlchemy Session.

Một transaction cho một use case. Thoát khỏi ``with`` mà chưa ``commit()`` thì
rollback — mặc định an toàn: quên commit thì mất việc vừa làm, chứ không lưu
nửa vời một quyết định license.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.infrastructure.db.repositories import (
    SqlAuditLog,
    SqlItemRepository,
    SqlJobRepository,
    SqlPublicationRepository,
    SqlSeriesRepository,
    SqlSourceRepository,
)


def normalize_database_url(url: str) -> str:
    """Ép dùng driver psycopg3.

    ``DATABASE_URL`` để ở dạng chuẩn ``postgresql://`` vì alembic, ``psql`` và
    n8n đều đọc chung biến đó. Nhưng SQLAlchemy mặc định hiểu dạng đó là
    psycopg2, mà image chỉ cài ``psycopg[binary]`` (psycopg3) — nên phải nói rõ
    driver ở đây thay vì bắt mọi nơi khác viết một URL phi chuẩn.
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


def make_engine(database_url: str, *, echo: bool = False) -> Engine:
    return create_engine(
        normalize_database_url(database_url),
        echo=echo,
        pool_pre_ping=True,  # container postgres restart thì không chết cả API
        future=True,
    )


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


class SqlUnitOfWork:
    """Dùng lại được nhiều lần, mỗi lần ``with`` là một session mới.

    Lồng ``with`` (use case gọi use case) được xử lý bằng đếm độ sâu: chỉ lần
    thoát ngoài cùng mới đóng session, nên không có chuyện transaction bị cắt
    giữa đường.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._factory = session_factory
        self._session: Session | None = None
        self._depth = 0

    def __enter__(self) -> SqlUnitOfWork:
        if self._depth == 0:
            self._session = self._factory()
            self._bind(self._session)
        self._depth += 1
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._depth -= 1
        if self._depth > 0:
            return
        assert self._session is not None
        try:
            if exc_type is not None:
                self._session.rollback()
        finally:
            self._session.close()
            self._session = None

    def _bind(self, session: Session) -> None:
        self.session = session
        self.sources = SqlSourceRepository(session)
        self.items = SqlItemRepository(session)
        self.publications = SqlPublicationRepository(session)
        self.jobs = SqlJobRepository(session)
        self.series = SqlSeriesRepository(session)
        self.audit = SqlAuditLog(session)

    def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("commit ngoài phạm vi with — không có session nào đang mở")
        self._session.commit()

    def rollback(self) -> None:
        if self._session is not None:
            self._session.rollback()

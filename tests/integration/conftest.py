"""Database riêng cho test tích hợp — **không dùng DB dev**.

Vì sao cần: test tích hợp `TRUNCATE ... RESTART IDENTITY CASCADE` để mỗi test
chạy trên schema sạch. Nếu nó chạy trên DB dev thì `make test-int` xoá sạch mọi
thứ người dùng đang xem — nguồn đã khai báo, item đang chờ duyệt, vết audit. Đã
xảy ra thật: một lần chạy test làm mất item demo đang mở trong trang duyệt.

Cách làm: conftest tự đổi ``DATABASE_URL`` sang một DB tên ``<db>_test``, tạo nó
nếu chưa có, và chạy migration. DB dev không bị chạm tới.

Hệ quả cần biết: đổi biến môi trường phải xảy ra **trước** khi bất cứ module nào
đọc config, nên fixture này ở scope ``session`` và ``autouse``.
"""

from __future__ import annotations

import os

import pytest

TEST_DB_SUFFIX = "_test"


def _swap_db_name(url: str, new_name: str) -> str:
    base, _, _ = url.rpartition("/")
    return f"{base}/{new_name}"


def _db_name(url: str) -> str:
    return url.rpartition("/")[2].split("?")[0]


@pytest.fixture(scope="session", autouse=True)
def test_database() -> None:
    """Trỏ mọi test tích hợp sang DB test, tạo và migrate nếu cần."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("thiếu DATABASE_URL — chạy trong container")

    dev_name = _db_name(url)
    if dev_name.endswith(TEST_DB_SUFFIX):
        return  # đã trỏ sẵn vào DB test (ví dụ khi CI đặt thẳng)

    test_name = dev_name + TEST_DB_SUFFIX
    admin_url = _swap_db_name(url, "postgres")
    test_url = _swap_db_name(url, test_name)

    from sqlalchemy import text

    from src.infrastructure.db.uow import make_engine

    # CREATE DATABASE không chạy trong transaction — phải AUTOCOMMIT.
    admin = make_engine(admin_url).execution_options(isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": test_name}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{test_name}"'))
    admin.dispose()

    os.environ["DATABASE_URL"] = test_url

    # Cache config và engine đã có thể được tạo trước khi ta đổi biến — bỏ cache.
    from src.interfaces.api.deps import reset_dependencies

    reset_dependencies()

    _migrate(test_url)


def _migrate(url: str) -> None:
    """Chạy alembic lên DB test.

    Dùng alembic thay vì `Base.metadata.create_all()` có chủ ý: test phải chạy
    trên **đúng schema mà production sẽ có**, gồm cả CHECK constraint và index
    một phần — hai thứ `create_all()` bỏ qua vì chúng khai trong migration.
    """
    from pathlib import Path

    from alembic.config import Config

    from alembic import command

    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    os.environ["DATABASE_URL"] = url
    command.upgrade(cfg, "head")

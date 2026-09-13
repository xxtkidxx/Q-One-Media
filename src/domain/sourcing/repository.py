"""Port của tầng domain. Tầng infrastructure hiện thực; domain không biết SQL."""

from __future__ import annotations

from typing import Protocol

from src.domain.sourcing.entities import Source
from src.domain.sourcing.value_objects import ApprovalStatus, SourceUrl


class SourceRepository(Protocol):
    def add(self, source: Source) -> Source:
        """Lưu nguồn mới, trả về bản đã có ``id``."""
        ...

    def get(self, source_id: int) -> Source | None: ...

    def get_by_url(self, url: SourceUrl) -> Source | None: ...

    def find_owning(self, item_url: SourceUrl) -> Source | None:
        """Tìm nguồn đã khai báo bao trùm một URL video cụ thể.

        Đây là mảnh nối hộp thư URL với license gate: người dán một URL video,
        hệ thống phải tự tìm ra nguồn cha để biết có quyền hay không.
        """
        ...

    def list_by_status(self, status: ApprovalStatus, *, limit: int = 100) -> list[Source]: ...

    def update(self, source: Source) -> None: ...

"""Port của bounded context sản xuất."""

from __future__ import annotations

from typing import Protocol

from src.domain.production.entities import Item
from src.domain.production.value_objects import ItemStage
from src.domain.sourcing.value_objects import SourceUrl


class ItemRepository(Protocol):
    def add(self, item: Item) -> Item: ...

    def get(self, item_id: int) -> Item | None: ...

    def get_by_url(self, url: SourceUrl) -> Item | None:
        """Chống nạp trùng: một URL video chỉ có một item."""
        ...

    def list_by_stage(self, stage: ItemStage, *, limit: int = 50) -> list[Item]: ...

    def count_by_stage(self) -> dict[ItemStage, int]: ...

    def update(self, item: Item) -> None: ...

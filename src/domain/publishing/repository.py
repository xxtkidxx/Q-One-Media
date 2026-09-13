"""Port của bounded context đăng bài."""

from __future__ import annotations

from typing import Protocol

from src.domain.publishing.entities import Publication
from src.domain.publishing.value_objects import PublishPlatform


class PublicationRepository(Protocol):
    def add(self, publication: Publication) -> Publication: ...

    def get(self, publication_id: int) -> Publication | None: ...

    def get_for(self, item_id: int, platform: PublishPlatform) -> Publication | None: ...

    def list_for_item(self, item_id: int) -> list[Publication]: ...

    def count_published_today(self, platform: PublishPlatform) -> int:
        """Để không vượt hạn mức ngày của nền tảng (YouTube: 100 upload/ngày)."""
        ...

    def update(self, publication: Publication) -> None: ...

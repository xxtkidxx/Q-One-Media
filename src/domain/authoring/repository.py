"""Port của bounded context biên soạn nội dung."""

from __future__ import annotations

from typing import Protocol

from src.domain.authoring.series import Series


class SeriesRepository(Protocol):
    def add(self, series: Series) -> Series: ...

    def get(self, series_id: int) -> Series | None: ...

    def list_all(self) -> list[Series]: ...

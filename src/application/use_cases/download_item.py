"""Tải video về đĩa — và xác minh video đó thật sự thuộc nguồn đã duyệt.

Thứ tự ở đây quan trọng và không được đảo:

1. xin ``DownloadClearance`` (nguồn approved, chưa hết hạn)
2. đọc metadata, **xác minh id chủ kênh** khớp nguồn đã duyệt
3. mới tải phần media

Bước 2 đứng trước bước 3 vì duyệt một kênh YouTube không mở quyền cho cả
youtube.com. Nếu chỉ khớp host thì một URL bất kỳ cùng nền tảng sẽ đi qua gate —
đó là lỗ thật, không phải lo xa.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from src.application.ports import Clock, UnitOfWork, VideoDownloader
from src.domain.errors import DomainError, LicenseViolation
from src.domain.production.entities import Item
from src.domain.production.value_objects import AspectRatio, MediaAsset


class ItemNotFound(DomainError):
    pass


class SourceVanished(DomainError):
    pass


class MetadataProbe(Protocol):
    """Đọc metadata mà **không** tải media (yt-dlp --dump-json).

    Tách khỏi ``VideoDownloader`` có chủ ý: xác minh quyền sở hữu phải rẻ, để
    không bao giờ có lý do bỏ qua nó vì tốn băng thông.
    """

    def probe(self, url: str) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class DownloadOutcome:
    item: Item
    downloaded: bool
    reason: str | None = None


def download_item(
    item_id: int,
    *,
    downloader: VideoDownloader,
    probe: MetadataProbe,
    media_root: Path,
    uow: UnitOfWork,
    clock: Clock,
    actor: str = "worker",
) -> DownloadOutcome:
    with uow:
        item = uow.items.get(item_id)
        if item is None:
            raise ItemNotFound(f"không có item #{item_id}")
        source = uow.sources.get(item.source_id)
        if source is None:
            raise SourceVanished(f"item #{item_id} trỏ tới nguồn #{item.source_id} không tồn tại")

        try:
            clearance = source.clear_for_download(clock.now())
            meta = probe.probe(item.url.value)
            source.assert_owns(_owner_id_from(meta))
        except LicenseViolation as exc:
            item.fail(f"license: {exc}")
            uow.items.update(item)
            uow.audit.record(
                entity="item",
                entity_id=item_id,
                action="download_refused",
                actor=actor,
                detail={"reason": str(exc)},
            )
            uow.commit()
            return DownloadOutcome(item=item, downloaded=False, reason=str(exc))

        dest_dir = media_root / "source" / f"item-{item_id:08d}"
        result = downloader.download(
            url=item.url.value, clearance=clearance, dest_dir=dest_dir
        )

        item.external_id = result.external_id or item.external_id
        item.title_original = result.title or item.title_original
        item.mark_downloaded(
            path=MediaAsset(_relative(result.path, media_root)),
            duration_sec=result.duration_sec,
            aspect_ratio=(
                AspectRatio.from_size(result.width, result.height)
                if result.width and result.height
                else None
            ),
        )
        uow.items.update(item)
        uow.audit.record(
            entity="item",
            entity_id=item_id,
            action="downloaded",
            actor=actor,
            detail={"external_id": item.external_id, "owner_verified": True},
        )
        uow.commit()

    return DownloadOutcome(item=item, downloaded=True)


# Khoá metadata theo thứ tự đáng tin giảm dần. yt-dlp đặt tên khác nhau theo
# extractor nên phải thử nhiều khoá, không giả định một khoá duy nhất.
_OWNER_KEYS = ("channel_id", "uploader_id", "uploader_url", "channel_url")


def _owner_id_from(meta: dict[str, Any]) -> str | None:
    for key in _OWNER_KEYS:
        value = meta.get(key)
        if value:
            return str(value)
    return None


def _relative(path: Path, media_root: Path) -> str:
    return Path(path).resolve().relative_to(Path(media_root).resolve()).as_posix()

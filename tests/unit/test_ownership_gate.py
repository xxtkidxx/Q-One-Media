"""Xác minh quyền sở hữu — lỗ dễ bỏ sót nhất của license gate.

Duyệt **một** kênh YouTube không có nghĩa là được dùng **mọi** video trên
youtube.com. Nếu chỉ khớp theo host thì một URL bất kỳ cùng nền tảng sẽ đi qua
gate, và điều tệ nhất là nó đi qua *im lặng*.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.application.use_cases.download_item import download_item
from src.application.use_cases.manage_sources import (
    DeclareSourceCommand,
    declare_source,
)
from src.application.use_cases.submit_url import submit_url
from src.domain.errors import OwnershipMismatch
from src.domain.production.value_objects import ItemStage
from src.domain.sourcing.value_objects import Platform, SourceKind, SourceUrl
from tests.fakes import FakeClock, FakeDownloader, FakeUnitOfWork
from tests.unit.test_submit_url import approve

NOW = datetime(2026, 9, 13, 10, 0, tzinfo=UTC)
MEDIA_ROOT = Path("/data/media")

VENDOR_CHANNEL = "https://www.youtube.com/@VendorAutomation"
VENDOR_OWNER = "UCvendor0000000000000000"
VENDOR_VIDEO = "https://www.youtube.com/watch?v=vendor01"
STRANGER_VIDEO = "https://www.youtube.com/watch?v=stranger9"


class StubProbe:
    """Metadata giả. ``owner`` là id chủ kênh mà nền tảng trả về."""

    def __init__(self, owner: str | None, keys: tuple[str, ...] = ("channel_id",)) -> None:
        self.owner = owner
        self.keys = keys
        self.calls: list[str] = []

    def probe(self, url: str) -> dict:
        self.calls.append(url)
        if self.owner is None:
            return {}
        return dict.fromkeys(self.keys, self.owner)


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(NOW)


def declare_channel(uow, *, owner_id: str | None = VENDOR_OWNER):
    return declare_source(
        DeclareSourceCommand(
            url=VENDOR_CHANNEL,
            platform=Platform.YOUTUBE,
            kind=SourceKind.CHANNEL,
            external_owner_id=owner_id,
        ),
        uow=uow,
        actor="quan.nguyen",
    )


# ---------------- Chặn sớm ở hộp thư URL ----------------


def test_nguon_dang_bao_chua_khai_owner_id_thi_khong_nap_duoc(uow, clock):
    """Thiếu cách xác minh là lý do hợp lệ để dừng, không phải lý do cho qua."""
    source = declare_channel(uow, owner_id=None)
    approve(uow, clock, source.id)

    result = submit_url(VENDOR_VIDEO, uow=uow, clock=clock, actor="q")

    assert result.accepted is False
    assert result.item.stage is ItemStage.LICENSE_BLOCKED
    assert "external_owner_id" in (result.reason or "")


def test_nguon_single_url_khong_can_owner_id(uow, clock):
    """Khớp chính xác URL thì bản thân việc khớp đã là xác minh."""
    source = declare_source(
        DeclareSourceCommand(
            url=VENDOR_VIDEO, platform=Platform.YOUTUBE, kind=SourceKind.SINGLE_URL
        ),
        uow=uow,
        actor="q",
    )
    approve(uow, clock, source.id)
    assert submit_url(VENDOR_VIDEO, uow=uow, clock=clock, actor="q").accepted is True


def test_single_url_khong_bao_trum_url_khac(uow, clock):
    from src.application.use_cases.submit_url import SourceNotDeclared

    source = declare_source(
        DeclareSourceCommand(
            url=VENDOR_VIDEO, platform=Platform.YOUTUBE, kind=SourceKind.SINGLE_URL
        ),
        uow=uow,
        actor="q",
    )
    approve(uow, clock, source.id)
    with pytest.raises(SourceNotDeclared):
        submit_url(STRANGER_VIDEO, uow=uow, clock=clock, actor="q")


# ---------------- Chặn thật ở bước tải, bằng metadata ----------------


def test_video_cua_kenh_khac_bi_tu_choi_du_cung_host(uow, clock):
    """Đây chính là lỗ: cùng youtube.com nhưng khác chủ."""
    source = declare_channel(uow)
    approve(uow, clock, source.id)
    item = submit_url(STRANGER_VIDEO, uow=uow, clock=clock, actor="q").item

    downloader = FakeDownloader()
    outcome = download_item(
        item.id,
        downloader=downloader,
        probe=StubProbe(owner="UCstranger999999999999"),
        media_root=MEDIA_ROOT,
        uow=uow,
        clock=clock,
    )

    assert outcome.downloaded is False
    assert "duyệt một kênh không mở quyền cho cả nền tảng" in (outcome.reason or "")
    assert downloader.calls == []  # chưa tải một byte nào
    assert uow.items.get(item.id).stage is ItemStage.FAILED
    assert "download_refused" in uow.audit.actions()


def test_video_dung_kenh_thi_tai_duoc(uow, clock):
    source = declare_channel(uow)
    approve(uow, clock, source.id)
    item = submit_url(VENDOR_VIDEO, uow=uow, clock=clock, actor="q").item

    downloader = FakeDownloader()
    outcome = download_item(
        item.id,
        downloader=downloader,
        probe=StubProbe(owner=VENDOR_OWNER),
        media_root=MEDIA_ROOT,
        uow=uow,
        clock=clock,
    )

    assert outcome.downloaded is True
    assert len(downloader.calls) == 1
    saved = uow.items.get(item.id)
    assert saved.stage is ItemStage.DOWNLOADED
    assert saved.path_source.relative_path == "source/item-00000002/video.mp4"
    assert str(saved.aspect_ratio) == "16:9"  # 1920x1080 từ FakeDownloader


def test_xac_minh_chay_truoc_khi_tai_du_metadata_thieu_khoa_chuan(uow, clock):
    """yt-dlp đặt tên khoá khác nhau theo extractor — thử nhiều khoá, không giả định một."""
    source = declare_channel(uow)
    approve(uow, clock, source.id)
    item = submit_url(VENDOR_VIDEO, uow=uow, clock=clock, actor="q").item

    downloader = FakeDownloader()
    outcome = download_item(
        item.id,
        downloader=downloader,
        probe=StubProbe(owner=VENDOR_OWNER, keys=("uploader_id",)),
        media_root=MEDIA_ROOT,
        uow=uow,
        clock=clock,
    )
    assert outcome.downloaded is True


def test_metadata_khong_co_id_chu_kenh_thi_tu_choi(uow, clock):
    source = declare_channel(uow)
    approve(uow, clock, source.id)
    item = submit_url(VENDOR_VIDEO, uow=uow, clock=clock, actor="q").item

    downloader = FakeDownloader()
    outcome = download_item(
        item.id,
        downloader=downloader,
        probe=StubProbe(owner=None),
        media_root=MEDIA_ROOT,
        uow=uow,
        clock=clock,
    )
    assert outcome.downloaded is False
    assert downloader.calls == []


# ---------------- Mức aggregate ----------------


def test_assert_owns_o_muc_aggregate(uow, clock):
    source = declare_channel(uow)
    approve(uow, clock, source.id)

    source.assert_owns(VENDOR_OWNER)  # đúng chủ: im lặng đi qua
    with pytest.raises(OwnershipMismatch):
        source.assert_owns("UCkhac")
    with pytest.raises(OwnershipMismatch):
        source.assert_owns(None)


def test_claims_chi_la_buoc_loc_ung_vien(uow):
    source = declare_channel(uow)
    assert source.claims(SourceUrl(STRANGER_VIDEO)) is True  # cùng host → ứng viên
    assert source.claims(SourceUrl("https://vimeo.com/1")) is False

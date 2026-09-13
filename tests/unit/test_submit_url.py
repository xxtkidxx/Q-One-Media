"""Hộp thư URL — license gate chạy trên đường thật, không chỉ ở mức aggregate."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.application.use_cases.manage_sources import (
    ApproveSourceCommand,
    DeclareSourceCommand,
    SourceAlreadyDeclared,
    approve_source,
    declare_source,
    expire_stale_licenses,
)
from src.application.use_cases.submit_url import (
    ItemAlreadyExists,
    SourceNotDeclared,
    submit_url,
)
from src.domain.production.value_objects import ItemStage
from src.domain.scheduling.entities import PRIORITY_NORMAL, PRIORITY_URGENT, JobTask
from src.domain.sourcing.value_objects import (
    ApprovalStatus,
    LicenseType,
    Platform,
    SourceKind,
)
from tests.fakes import FakeClock, FakeUnitOfWork

NOW = datetime(2026, 9, 13, 10, 0, tzinfo=UTC)

YT_CHANNEL = "https://www.youtube.com/@VendorAutomation"
YT_VIDEO = "https://www.youtube.com/watch?v=abc123"
DOUYIN_USER = "https://www.douyin.com/user/MS4wLjAB"
DOUYIN_VIDEO = "https://www.douyin.com/video/7412345678901234567"


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(NOW)


def declare(uow, url=YT_CHANNEL, platform=Platform.YOUTUBE, kind=SourceKind.CHANNEL, **kw):
    return declare_source(
        DeclareSourceCommand(url=url, platform=platform, kind=kind, **kw),
        uow=uow,
        actor="quan.nguyen",
    )


def approve(uow, clock, source_id, *, full=True, **overrides):
    rights = (
        dict(
            may_translate=True,
            may_modify_audio=True,
            may_subtitle=True,
            may_republish=True,
            may_commercial_use=True,
        )
        if full
        else {}
    )
    return approve_source(
        ApproveSourceCommand(
            source_id=source_id,
            actor="quan.nguyen",
            license_type=LicenseType.VENDOR_MEDIAKIT,
            evidence_ref="https://vendor.example.com/media-kit-terms",
            **{**rights, **overrides},
        ),
        uow=uow,
        clock=clock,
    )


# ---------------- Nguồn chưa khai báo ----------------


def test_url_khong_thuoc_nguon_nao_thi_tu_choi_va_khong_tu_tao_nguon(uow, clock):
    """Khai báo nguồn là hành vi có trách nhiệm pháp lý — không để hệ thống suy ra."""
    with pytest.raises(SourceNotDeclared) as exc:
        submit_url(YT_VIDEO, uow=uow, clock=clock, actor="quan.nguyen")
    assert "youtube.com" in str(exc.value)
    assert uow.items.count_by_stage() == {}


# ---------------- Nguồn đã khai báo nhưng chưa duyệt ----------------


def test_nguon_pending_thi_item_bi_chan_va_van_duoc_luu_lai(uow, clock):
    """Lưu lại để thấy nhu cầu thật: biết nên đi xin phép hãng nào trước."""
    declare(uow)
    result = submit_url(YT_VIDEO, uow=uow, clock=clock, actor="quan.nguyen")

    assert result.accepted is False
    assert result.item.stage is ItemStage.LICENSE_BLOCKED
    assert result.job_id is None
    assert uow.jobs.all() == []  # không xếp việc tải
    assert "license_blocked" in uow.audit.actions()


def test_item_bi_chan_khong_co_duong_di_tiep(uow, clock):
    declare(uow)
    item = submit_url(YT_VIDEO, uow=uow, clock=clock, actor="q").item
    assert item.stage.is_terminal


# ---------------- Nguồn đã duyệt ----------------


def test_nguon_approved_thi_nap_duoc_va_xep_viec_tai(uow, clock):
    source = declare(uow)
    approve(uow, clock, source.id)

    result = submit_url(YT_VIDEO, uow=uow, clock=clock, actor="quan.nguyen")

    assert result.accepted is True
    assert result.item.stage is ItemStage.INBOX
    jobs = uow.jobs.all()
    assert len(jobs) == 1
    assert jobs[0].task is JobTask.DOWNLOAD
    assert jobs[0].priority == PRIORITY_NORMAL
    assert "accepted" in uow.audit.actions()


def test_url_douyin_duoc_xep_uu_tien_khan(uow, clock):
    """URL CDN Douyin hết hạn sau vài giờ — đứng hàng đợi thường là mất nguồn."""
    source = declare(uow, url=DOUYIN_USER, platform=Platform.DOUYIN, kind=SourceKind.CREATOR_PAGE)
    approve(uow, clock, source.id)

    result = submit_url(DOUYIN_VIDEO, uow=uow, clock=clock, actor="q")

    job = uow.jobs.get(result.job_id)
    assert job.priority == PRIORITY_URGENT
    assert job.payload["platform"] == "douyin"


def test_nguon_thieu_quyen_sua_audio_van_tai_duoc(uow, clock):
    """Tải cần ít quyền hơn lồng tiếng — gate chặn ở đúng bước cần quyền đó."""
    source = declare(uow)
    approve(uow, clock, source.id, full=False, may_republish=True)
    result = submit_url(YT_VIDEO, uow=uow, clock=clock, actor="q")
    assert result.accepted is True


# ---------------- Hết hạn license ----------------


def test_license_het_han_thi_url_moi_bi_chan(uow, clock):
    source = declare(uow)
    approve(uow, clock, source.id, expires_at=NOW + timedelta(days=7))

    clock.advance(days=8)
    result = submit_url(YT_VIDEO, uow=uow, clock=clock, actor="q")

    assert result.accepted is False
    assert "hết hạn" in (result.reason or "")


def test_quet_dinh_ky_doi_status_nguon_qua_han(uow, clock):
    source = declare(uow)
    approve(uow, clock, source.id, expires_at=NOW + timedelta(days=7))
    clock.advance(days=8)

    assert expire_stale_licenses(uow=uow, clock=clock) == 1
    assert uow.sources.get(source.id).status is ApprovalStatus.EXPIRED
    assert "expired" in uow.audit.actions()


# ---------------- Chống trùng ----------------


def test_nap_lai_cung_url_thi_bao_da_ton_tai(uow, clock):
    source = declare(uow)
    approve(uow, clock, source.id)
    submit_url(YT_VIDEO, uow=uow, clock=clock, actor="q")
    with pytest.raises(ItemAlreadyExists):
        submit_url(YT_VIDEO, uow=uow, clock=clock, actor="q")


def test_khai_bao_trung_nguon_thi_bao_loi(uow):
    declare(uow)
    with pytest.raises(SourceAlreadyDeclared):
        declare(uow)


# ---------------- Vết thao tác ----------------


def test_moi_quyet_dinh_license_deu_co_vet_kem_bang_chung(uow, clock):
    source = declare(uow)
    approve(uow, clock, source.id)

    approved = next(e for e in uow.audit.entries if e["action"] == "approved")
    assert approved["actor"] == "quan.nguyen"
    assert approved["detail"]["evidence_ref"].startswith("https://")
    assert approved["detail"]["scope"]["may_modify_audio"] is True


def test_use_case_co_commit(uow, clock):
    source = declare(uow)
    approve(uow, clock, source.id)
    submit_url(YT_VIDEO, uow=uow, clock=clock, actor="q")
    assert uow.commits == 3

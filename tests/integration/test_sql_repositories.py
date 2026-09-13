"""Repository và mapper trên Postgres thật.

Cần container đang chạy — đánh dấu ``integration`` nên ``make test`` bỏ qua.
Chạy bằng: ``make test-all``.

Vì sao nhóm test này đáng có dù đã có 112 unit test: mapper là chỗ duy nhất
trong hệ thống có thể **mất dữ liệu im lặng**. Một value object không được ghi
xuống cột đúng thì unit test vẫn xanh (chúng không đi qua DB), và lỗi chỉ lộ ra
khi đọc lại ở một phiên khác.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest

from src.domain.production.entities import Item
from src.domain.production.value_objects import (
    AspectRatio,
    ItemStage,
    MediaAsset,
    Segment,
)
from src.domain.publishing.entities import Publication
from src.domain.publishing.value_objects import PublishPlatform, PublishStatus
from src.domain.scheduling.entities import PRIORITY_URGENT, Job, JobStatus, JobTask
from src.domain.sourcing.entities import Source
from src.domain.sourcing.value_objects import (
    ApprovalStatus,
    ContentType,
    Language,
    LicenseEvidence,
    LicenseScope,
    LicenseType,
    Platform,
    SourceKind,
    SourceUrl,
)
from src.infrastructure.db.uow import SqlUnitOfWork, make_engine, make_session_factory

pytestmark = pytest.mark.integration

NOW = datetime(2026, 9, 13, 10, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def uow_factory():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("thiếu DATABASE_URL — chạy trong container")
    factory = make_session_factory(make_engine(url))
    return lambda: SqlUnitOfWork(factory)


@pytest.fixture
def uow(uow_factory):
    """Mỗi test một schema sạch: xoá theo thứ tự khoá ngoại."""
    u = uow_factory()
    with u:
        u.session.execute(
            __import__("sqlalchemy").text(
                "TRUNCATE publications, jobs, items, audit_log, sources RESTART IDENTITY CASCADE"
            )
        )
        u.commit()
    return u


def _unique(prefix: str) -> str:
    return f"{prefix}{datetime.now(UTC).timestamp()}".replace(".", "")


# ---------------- Source ----------------


def test_source_di_qua_db_va_ve_khong_mat_gi(uow):
    src = Source(
        platform=Platform.YOUTUBE,
        kind=SourceKind.CHANNEL,
        url=SourceUrl("https://www.youtube.com/@Vendor1"),
        content_type=ContentType.VIDEO,
        display_name="Vendor Automation",
        audio_lang=Language("zh"),
        external_owner_id="UCabc123",
        topics=("spc", "vision"),
        notes="ghi chú",
    )
    src.approve(
        by="quan.nguyen",
        evidence=LicenseEvidence(
            license_type=LicenseType.CC_BY,
            evidence_ref="https://youtu.be/x",
            attribution_text="Nguồn: Vendor GmbH (CC BY 4.0)",
        ),
        scope=LicenseScope(
            may_translate=True, may_modify_audio=True, may_subtitle=True, may_republish=True
        ),
        at=NOW,
        expires_at=NOW + timedelta(days=365),
    )

    with uow:
        saved = uow.sources.add(src)
        uow.commit()
        sid = saved.id

    with uow:
        got = uow.sources.get(sid)

    assert got is not None
    assert got.url.value == "https://www.youtube.com/@Vendor1"
    assert got.audio_lang == Language("zh")
    assert got.external_owner_id == "UCabc123"
    assert got.topics == ("spc", "vision")
    assert got.status is ApprovalStatus.APPROVED
    assert got.evidence.license_type is LicenseType.CC_BY
    assert got.evidence.attribution_text == "Nguồn: Vendor GmbH (CC BY 4.0)"
    assert got.scope.may_modify_audio is True
    assert got.scope.may_commercial_use is False  # không cấp thì phải vẫn là False
    assert got.expires_at == NOW + timedelta(days=365)
    # Clearance cấp được sau khi đi qua DB — bất biến vẫn nguyên
    assert got.clear_for_dubbing(NOW).source_id == sid


def test_enum_luu_gia_tri_chu_khong_luu_ten_thanh_vien(uow):
    """``creator-page`` phải vào DB đúng như vậy, không phải ``CREATOR_PAGE``."""
    with uow:
        saved = uow.sources.add(
            Source(
                platform=Platform.DOUYIN,
                kind=SourceKind.CREATOR_PAGE,
                url=SourceUrl("https://www.douyin.com/user/abc"),
            )
        )
        uow.commit()
        sid = saved.id
    with uow:
        raw = uow.session.execute(
            __import__("sqlalchemy").text("SELECT kind::text, platform::text FROM sources WHERE id=:i"),
            {"i": sid},
        ).one()
    assert raw == ("creator-page", "douyin")


def test_find_owning_uu_tien_khop_chinh_xac_hon_nguon_dang_bao(uow):
    video = "https://www.youtube.com/watch?v=exact1"
    with uow:
        uow.sources.add(
            Source(
                platform=Platform.YOUTUBE,
                kind=SourceKind.CHANNEL,
                url=SourceUrl("https://www.youtube.com/@Broad"),
                external_owner_id="UCbroad",
            )
        )
        exact = uow.sources.add(
            Source(
                platform=Platform.YOUTUBE, kind=SourceKind.SINGLE_URL, url=SourceUrl(video)
            )
        )
        uow.commit()
        exact_id = exact.id

    with uow:
        found = uow.sources.find_owning(SourceUrl(video))
        other = uow.sources.find_owning(SourceUrl("https://www.youtube.com/watch?v=random"))

    assert found is not None and found.id == exact_id
    assert other is not None and other.kind is SourceKind.CHANNEL  # chỉ là ứng viên


# ---------------- Item ----------------


def test_item_giu_nguyen_segment_duong_dan_va_ty_le(uow):
    with uow:
        src = uow.sources.add(
            Source(
                platform=Platform.YOUTUBE,
                kind=SourceKind.SINGLE_URL,
                url=SourceUrl("https://www.youtube.com/watch?v=one"),
            )
        )
        src.approve(
            by="q",
            evidence=LicenseEvidence(
                license_type=LicenseType.OWN, evidence_ref="nội bộ NMI"
            ),
            scope=LicenseScope(may_translate=True, may_modify_audio=True, may_subtitle=True),
            at=NOW,
        )
        uow.sources.update(src)

        item = uow.items.add(
            Item.accept(
                url=SourceUrl("https://www.youtube.com/watch?v=one"),
                clearance=src.clear_for_download(NOW),
            )
        )
        item.mark_downloaded(
            path=MediaAsset("source/item-00000001/video.mp4"),
            duration_sec=612,
            aspect_ratio=AspectRatio(16, 9),
        )
        item.mark_separated()
        item.mark_transcribed()
        item.send_transcript_to_review()
        item.pick_segment(Segment(120.5, 180.25, rationale="có số liệu Cpk"))
        item.attach_script(script_vi="Kịch bản có dấu: ậ ả ằ ộ ự", clearance=src.clear_for_dubbing(NOW))
        uow.items.update(item)
        uow.commit()
        iid = item.id

    with uow:
        got = uow.items.get(iid)

    assert got.stage is ItemStage.SCRIPTED
    assert got.segment == Segment(120.5, 180.25)
    assert got.path_source.relative_path == "source/item-00000001/video.mp4"
    assert str(got.aspect_ratio) == "16:9"
    assert got.needs_reframe is True
    assert got.script_vi == "Kịch bản có dấu: ậ ả ằ ộ ự"  # UTF-8 đi qua DB nguyên vẹn
    # Đọc lại từ DB rồi đi tiếp được — không bị chặn oan vì mất cờ clearance
    got.mark_voiced()
    assert got.stage is ItemStage.VOICED


def test_count_by_stage(uow):
    with uow:
        src = uow.sources.add(
            Source(
                platform=Platform.VIMEO,
                kind=SourceKind.CHANNEL,
                url=SourceUrl("https://vimeo.com/ch"),
                external_owner_id="v1",
            )
        )
        src.approve(
            by="q",
            evidence=LicenseEvidence(license_type=LicenseType.STOCK, evidence_ref="hoá đơn 123"),
            scope=LicenseScope(),
            at=NOW,
        )
        uow.sources.update(src)
        for n in range(3):
            uow.items.add(
                Item.accept(
                    url=SourceUrl(f"https://vimeo.com/{n}"),
                    clearance=src.clear_for_download(NOW),
                )
            )
        uow.items.add(Item.blocked(url=SourceUrl("https://vimeo.com/x"), source_id=src.id, reason="r"))
        uow.commit()

    with uow:
        counts = uow.items.count_by_stage()
    assert counts[ItemStage.INBOX] == 3
    assert counts[ItemStage.LICENSE_BLOCKED] == 1


# ---------------- Job queue ----------------


def test_claim_next_lay_viec_uu_tien_cao_truoc(uow):
    with uow:
        uow.jobs.enqueue(Job(task=JobTask.RENDER, priority=100))
        urgent = uow.jobs.enqueue(Job(task=JobTask.DOWNLOAD, priority=PRIORITY_URGENT))
        uow.commit()
        urgent_id = urgent.id

    with uow:
        claimed = uow.jobs.claim_next(worker="w1")
        uow.commit()

    assert claimed is not None
    assert claimed.id == urgent_id
    assert claimed.status is JobStatus.RUNNING
    assert claimed.attempts == 1
    assert claimed.locked_by == "w1"


def test_claim_next_loc_theo_task(uow):
    with uow:
        uow.jobs.enqueue(Job(task=JobTask.RENDER))
        uow.commit()
    with uow:
        assert uow.jobs.claim_next(worker="w1", tasks=(JobTask.DOWNLOAD,)) is None
        assert uow.jobs.claim_next(worker="w1", tasks=(JobTask.RENDER,)) is not None
        uow.commit()


def test_hang_doi_rong_tra_ve_none(uow):
    with uow:
        assert uow.jobs.claim_next(worker="w1") is None


def test_release_stale_thu_hoi_viec_cua_worker_da_chet(uow):
    with uow:
        uow.jobs.enqueue(Job(task=JobTask.DOWNLOAD))
        uow.commit()
    with uow:
        job = uow.jobs.claim_next(worker="w-chet")
        uow.commit()
        jid = job.id

    with uow:
        # Chưa quá hạn thì không thu hồi
        assert uow.jobs.release_stale(older_than_sec=3600) == 0
        # Quá hạn (0 giây) thì thu hồi, và KHÔNG đếm thêm lần thử
        assert uow.jobs.release_stale(older_than_sec=0) == 1
        uow.commit()

    with uow:
        got = uow.jobs.get(jid)
    assert got.status is JobStatus.PENDING
    assert got.locked_by is None
    assert got.attempts == 1


def test_payload_jsonb_di_ve_nguyen_ven(uow):
    with uow:
        job = uow.jobs.enqueue(
            Job(task=JobTask.DOWNLOAD, payload={"url": "https://x/1", "platform": "douyin", "n": 3})
        )
        uow.commit()
        jid = job.id
    with uow:
        got = uow.jobs.get(jid)
    assert got.payload == {"url": "https://x/1", "platform": "douyin", "n": 3}


# ---------------- Publication ----------------


def test_publication_unique_theo_item_va_nen_tang(uow):
    with uow:
        src = uow.sources.add(
            Source(
                platform=Platform.YOUTUBE,
                kind=SourceKind.SINGLE_URL,
                url=SourceUrl("https://www.youtube.com/watch?v=pub"),
            )
        )
        src.approve(
            by="q",
            evidence=LicenseEvidence(license_type=LicenseType.OWN, evidence_ref="nội bộ"),
            scope=LicenseScope(),
            at=NOW,
        )
        uow.sources.update(src)
        item = uow.items.add(
            Item.accept(
                url=SourceUrl("https://www.youtube.com/watch?v=pub"),
                clearance=src.clear_for_download(NOW),
            )
        )
        uow.commit()
        iid = item.id

    with uow:
        pub = uow.publications.add(Publication(item_id=iid, platform=PublishPlatform.YOUTUBE))
        pub.start_upload()
        pub.mark_published(remote_id="yt1", remote_url="https://youtu.be/yt1", at=datetime.now(UTC))
        uow.publications.update(pub)
        uow.commit()

    with uow:
        got = uow.publications.get_for(iid, PublishPlatform.YOUTUBE)
        assert got.status is PublishStatus.PUBLISHED
        assert got.remote_id == "yt1"
        # Cửa sổ 24 giờ trượt, không phải ngày lịch
        assert uow.publications.count_published_today(PublishPlatform.YOUTUBE) == 1
        assert uow.publications.count_published_today(PublishPlatform.TIKTOK) == 0


# ---------------- Rollback ----------------


def test_thoat_khoi_with_ma_khong_commit_thi_khong_luu_gi(uow):
    """Mặc định an toàn: quên commit thì mất việc vừa làm, không lưu nửa vời."""
    url = "https://www.youtube.com/@Forgotten"
    with uow:
        uow.sources.add(
            Source(platform=Platform.YOUTUBE, kind=SourceKind.CHANNEL, url=SourceUrl(url))
        )
        # cố tình không commit

    with uow:
        assert uow.sources.get_by_url(SourceUrl(url)) is None

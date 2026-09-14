"""Luồng đăng bài đầu-cuối qua use case, với publisher giả.

Không cần token YouTube/Facebook thật vì chính sách và điều phối tách khỏi adapter.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.application.use_cases import review_item
from src.application.use_cases.publish_item import (
    PublishDisabled,
    QuotaExhausted,
    publish_item,
)
from src.domain.errors import DomainError
from src.domain.production.entities import Item
from src.domain.production.value_objects import (
    AspectRatio,
    ItemStage,
    MediaAsset,
    Segment,
)
from src.domain.publishing.value_objects import (
    PublishPlatform,
    PublishStatus,
    VideoMetadata,
)
from src.domain.scheduling.entities import JobTask
from src.domain.sourcing.entities import Source
from src.domain.sourcing.value_objects import (
    Language,
    LicenseEvidence,
    LicenseScope,
    LicenseType,
    Platform,
    SourceKind,
    SourceUrl,
)
from tests.fakes import FakeClock, FakePublisher, FakeUnitOfWork

NOW = datetime(2026, 9, 13, 10, 0, tzinfo=UTC)
MEDIA_ROOT = Path("/data/media")
META = VideoMetadata(title="Cpk nói gì, và Cpk không nói gì", description="Phân tích của NMI.")

FULL_SCOPE = LicenseScope(
    may_translate=True,
    may_modify_audio=True,
    may_subtitle=True,
    may_republish=True,
    may_commercial_use=True,
)


def build_approved_item(
    uow: FakeUnitOfWork,
    *,
    platform: Platform = Platform.YOUTUBE,
    url: str = "https://www.youtube.com/@Vendor",
    scope: LicenseScope = FULL_SCOPE,
    attribution: str | None = None,
    license_type: LicenseType = LicenseType.VENDOR_MEDIAKIT,
) -> Item:
    """Dựng một item đã đi hết pipeline và đã qua người duyệt."""
    source = uow.sources.add(
        Source(
            platform=platform,
            kind=SourceKind.CHANNEL,
            url=SourceUrl(url),
            audio_lang=Language("en"),
        )
    )
    source.approve(
        by="quan.nguyen",
        evidence=LicenseEvidence(
            license_type=license_type,
            evidence_ref="https://vendor.example.com/terms",
            attribution_text=attribution,
        ),
        scope=scope,
        at=NOW,
    )
    uow.sources.update(source)

    item = uow.items.add(
        Item.accept(url=SourceUrl(url + "/video/1"), clearance=source.clear_for_download(NOW))
    )
    item.mark_downloaded(
        path=MediaAsset("source/a.mp4"), duration_sec=600, aspect_ratio=AspectRatio(16, 9)
    )
    item.mark_separated()
    item.mark_transcribed()
    item.send_transcript_to_review()
    item.approve_transcript()
    item.pick_segment(Segment(120.0, 180.0))
    item.attach_script(script_vi="Kịch bản tiếng Việt.", clearance=source.clear_for_dubbing(NOW))
    item.mark_voiced()
    item.mark_aligned()
    item.mark_mixed()
    item.mark_rendered(path=MediaAsset("output/item-00000001/final.mp4"))
    item.send_to_human_review()
    uow.items.update(item)
    return item


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(NOW)


def run(uow, clock, item_id, publishers, *, enabled=True):
    return publish_item(
        item_id,
        metadata=META,
        publishers=publishers,
        media_root=MEDIA_ROOT,
        uow=uow,
        clock=clock,
        enabled=enabled,
    )


# ---------------- Kill-switch ----------------


def test_publish_enabled_false_thi_khong_dang_gi(uow, clock):
    item = build_approved_item(uow)
    review_item.approve_item(item.id, actor="q", uow=uow, clock=clock)
    with pytest.raises(PublishDisabled):
        run(uow, clock, item.id, {PublishPlatform.YOUTUBE: FakePublisher(PublishPlatform.YOUTUBE)},
            enabled=False)


# ---------------- Đường thành công ----------------


def test_da_duyet_thi_dang_duoc_youtube_va_item_sang_published(uow, clock):
    item = build_approved_item(uow)
    review_item.approve_item(item.id, actor="quan.nguyen", uow=uow, clock=clock)

    yt = FakePublisher(PublishPlatform.YOUTUBE)
    outcomes = run(uow, clock, item.id, {PublishPlatform.YOUTUBE: yt})

    assert [o.status for o in outcomes] == [PublishStatus.PUBLISHED]
    assert uow.items.get(item.id).stage is ItemStage.PUBLISHED
    assert "published" in uow.audit.actions()


def test_chua_duyet_thi_bo_qua_khong_phai_loi(uow, clock):
    """Gate duyệt chặn ở đây, và ghi rõ lý do để không ai tưởng hệ thống hỏng."""
    item = build_approved_item(uow)  # còn ở human_review
    yt = FakePublisher(PublishPlatform.YOUTUBE)
    outcomes = run(uow, clock, item.id, {PublishPlatform.YOUTUBE: yt})

    assert outcomes[0].status is PublishStatus.SKIPPED
    assert "gate duyệt" in (outcomes[0].reason or "")
    assert yt.calls == []  # adapter không hề được gọi
    assert uow.items.get(item.id).stage is ItemStage.HUMAN_REVIEW


# ---------------- Watermark dán cứng ----------------


def test_nguon_douyin_bo_qua_tiktok_nhung_van_dang_youtube(uow, clock):
    item = build_approved_item(
        uow, platform=Platform.DOUYIN, url="https://www.douyin.com/user/abc"
    )
    review_item.approve_item(item.id, actor="q", uow=uow, clock=clock)

    yt = FakePublisher(PublishPlatform.YOUTUBE)
    tt = FakePublisher(PublishPlatform.TIKTOK)
    outcomes = run(
        uow, clock, item.id, {PublishPlatform.YOUTUBE: yt, PublishPlatform.TIKTOK: tt}
    )

    by_platform = {o.platform: o for o in outcomes}
    assert by_platform[PublishPlatform.YOUTUBE].status is PublishStatus.PUBLISHED
    assert by_platform[PublishPlatform.TIKTOK].status is PublishStatus.SKIPPED
    assert "watermark dán cứng" in (by_platform[PublishPlatform.TIKTOK].reason or "")
    assert tt.calls == []


# ---------------- Thiếu quyền đăng lại ----------------


def test_thieu_quyen_dang_lai_thi_bo_qua_moi_nen_tang(uow, clock):
    item = build_approved_item(
        uow, scope=LicenseScope(may_translate=True, may_modify_audio=True, may_subtitle=True)
    )
    review_item.approve_item(item.id, actor="q", uow=uow, clock=clock)

    yt = FakePublisher(PublishPlatform.YOUTUBE)
    outcomes = run(uow, clock, item.id, {PublishPlatform.YOUTUBE: yt})

    assert outcomes[0].status is PublishStatus.SKIPPED
    assert "may_republish" in (outcomes[0].reason or "")
    assert yt.calls == []


# ---------------- Ghi nguồn ----------------


def test_cc_by_thi_ghi_nguon_di_vao_mo_ta_khi_dang(uow, clock):
    item = build_approved_item(
        uow,
        license_type=LicenseType.CC_BY,
        attribution="Nguồn: Vendor GmbH — CC BY 4.0",
    )
    review_item.approve_item(item.id, actor="q", uow=uow, clock=clock)

    yt = FakePublisher(PublishPlatform.YOUTUBE)
    run(uow, clock, item.id, {PublishPlatform.YOUTUBE: yt})

    assert yt.calls[0].description.startswith("Nguồn: Vendor GmbH")


# ---------------- Một nền tảng lỗi không làm đổ nền tảng khác ----------------


def test_facebook_loi_thi_youtube_van_dang_va_item_van_sang_published(uow, clock):
    item = build_approved_item(uow)
    review_item.approve_item(item.id, actor="q", uow=uow, clock=clock)

    yt = FakePublisher(PublishPlatform.YOUTUBE)
    fb = FakePublisher(PublishPlatform.FACEBOOK, fail_with=RuntimeError("App Review chưa xong"))
    outcomes = run(
        uow, clock, item.id, {PublishPlatform.YOUTUBE: yt, PublishPlatform.FACEBOOK: fb}
    )

    by_platform = {o.platform: o.status for o in outcomes}
    assert by_platform[PublishPlatform.YOUTUBE] is PublishStatus.PUBLISHED
    assert by_platform[PublishPlatform.FACEBOOK] is PublishStatus.FAILED
    assert uow.items.get(item.id).stage is ItemStage.PUBLISHED


def test_loi_nen_tang_duoc_ghi_nguyen_van_khong_nuot(uow, clock):
    item = build_approved_item(uow)
    review_item.approve_item(item.id, actor="q", uow=uow, clock=clock)
    fb = FakePublisher(PublishPlatform.FACEBOOK, fail_with=RuntimeError("429 rate limit"))
    run(uow, clock, item.id, {PublishPlatform.FACEBOOK: fb})

    pub = uow.publications.get_for(item.id, PublishPlatform.FACEBOOK)
    assert pub.error == "RuntimeError: 429 rate limit"


# ---------------- Không đăng hai lần ----------------


def test_goi_lai_thi_khong_dang_trung(uow, clock):
    item = build_approved_item(uow)
    review_item.approve_item(item.id, actor="q", uow=uow, clock=clock)
    yt = FakePublisher(PublishPlatform.YOUTUBE)

    run(uow, clock, item.id, {PublishPlatform.YOUTUBE: yt})
    outcomes = run(uow, clock, item.id, {PublishPlatform.YOUTUBE: yt})

    assert len(yt.calls) == 1
    assert outcomes[0].reason == "đã đăng"


# ---------------- Hạn mức ----------------


def test_het_han_muc_youtube_thi_bao_loi_retry_duoc(uow, clock, monkeypatch):
    item = build_approved_item(uow)
    review_item.approve_item(item.id, actor="q", uow=uow, clock=clock)
    monkeypatch.setattr(
        uow.publications, "count_published_today", lambda platform: 100, raising=True
    )
    with pytest.raises(QuotaExhausted) as exc:
        run(uow, clock, item.id, {PublishPlatform.YOUTUBE: FakePublisher(PublishPlatform.YOUTUBE)})
    assert exc.value.retryable is True


# ---------------- Hàng đợi duyệt ----------------


def test_hang_doi_duyet_hien_cong_duyet_du_kien_theo_ngon_ngu(uow, clock):
    build_approved_item(uow)
    src = uow.sources.get(1)
    src.audio_lang = Language("zh")
    uow.sources.update(src)

    queue = review_item.list_review_queue(uow=uow)
    assert len(queue) == 1
    assert queue[0].expected_minutes == (35, 55)


def test_nut_xuat_ban_chi_xep_viec_cho_item_da_duyet(uow, clock):
    """Nút “Xuất bản” trên web xếp việc đăng, không tự đăng — và không đi vòng gate."""
    item = build_approved_item(uow)  # còn ở human_review

    with pytest.raises(DomainError):
        review_item.queue_publish(item.id, actor="q", uow=uow, enabled=True)
    assert [j.task for j in uow.jobs.all()] == []

    review_item.approve_item(item.id, actor="q", uow=uow, clock=clock)
    review_item.queue_publish(item.id, actor="quan.nguyen", uow=uow, enabled=True)
    assert JobTask.PUBLISH in [j.task for j in uow.jobs.all()]
    assert "publish_queued" in uow.audit.actions()


def test_xuat_ban_khi_kill_switch_tat_thi_bi_chan(uow, clock):
    """``PUBLISH_ENABLED=false`` chỉ chặn thêm — không có đường nào đăng khi nó tắt."""
    item = build_approved_item(uow)
    review_item.approve_item(item.id, actor="q", uow=uow, clock=clock)
    with pytest.raises(PublishDisabled):
        review_item.queue_publish(item.id, actor="q", uow=uow, enabled=False)


def test_nguoi_duyet_tra_ve_viet_lai(uow, clock):
    item = build_approved_item(uow)
    review_item.send_back_for_rewrite(
        item.id, actor="q", reason="kịch bản dịch sát nguyên văn quá", uow=uow, clock=clock
    )
    assert uow.items.get(item.id).stage is ItemStage.SEGMENT_PICKED
    assert "sent_back_for_rewrite" in uow.audit.actions()

"""Chính sách đăng bài. Không cần token thật vì chính sách không biết HTTP."""

from __future__ import annotations

import pytest

from src.domain.errors import InvalidTransition, InvariantViolation
from src.domain.publishing.entities import Publication
from src.domain.publishing.policy import decide
from src.domain.publishing.value_objects import (
    PublishPlatform,
    PublishStatus,
    VideoMetadata,
)
from src.domain.sourcing.value_objects import (
    Platform,
    SourceUrl,
)
from tests.unit.test_item_lifecycle import item_at_review
from tests.unit.test_license_gate import NOW, approved_source


def approved_item_and_source(**src_kw):
    item, _ = item_at_review()
    item.approve(by="quan.nguyen", at=NOW)
    src = approved_source(**src_kw)
    return item, src


# ---------------- Gate duyệt của người chặn trước mọi thứ khác ----------------


def test_chua_duyet_thi_khong_dang_bat_ke_nen_tang_nao():
    item, src = item_at_review()  # đang ở human_review
    src = approved_source()
    for platform in PublishPlatform:
        d = decide(item=item, platform=platform, clearance=src.clear_for_publish(NOW))
        assert d.allowed is False
        assert "gate duyệt" in (d.reason or "")


def test_da_duyet_va_co_file_thi_dang_duoc_youtube():
    item, src = approved_item_and_source()
    assert decide(
        item=item, platform=PublishPlatform.YOUTUBE, clearance=src.clear_for_publish(NOW)
    ).allowed


def test_thieu_file_thanh_pham_thi_khong_dang():
    item, src = approved_item_and_source()
    item.path_output = None
    d = decide(item=item, platform=PublishPlatform.YOUTUBE, clearance=src.clear_for_publish(NOW))
    assert d.allowed is False
    assert "thành phẩm" in (d.reason or "")


# ---------------- Watermark dán cứng: không đăng TikTok ----------------


def test_nguon_watermark_dan_cung_khong_dang_tiktok():
    item, src = approved_item_and_source(
        platform=Platform.DOUYIN, url=SourceUrl("https://www.douyin.com/user/abc")
    )
    d = decide(item=item, platform=PublishPlatform.TIKTOK, clearance=src.clear_for_publish(NOW))
    assert d.allowed is False
    assert "watermark dán cứng" in (d.reason or "")


def test_nguon_watermark_dan_cung_van_dang_duoc_youtube_va_facebook():
    """Chỉ TikTok chặn. YouTube/Facebook không có luật tương đương."""
    item, src = approved_item_and_source(
        platform=Platform.DOUYIN, url=SourceUrl("https://www.douyin.com/user/abc")
    )
    for platform in (PublishPlatform.YOUTUBE, PublishPlatform.FACEBOOK):
        assert decide(
            item=item, platform=platform, clearance=src.clear_for_publish(NOW)
        ).allowed


def test_clearance_cua_nguon_khac_bi_tu_choi():
    item, _ = approved_item_and_source()
    khac = approved_source(id=99, url=SourceUrl("https://vimeo.com/other"))
    d = decide(item=item, platform=PublishPlatform.YOUTUBE, clearance=khac.clear_for_publish(NOW))
    assert d.allowed is False


# ---------------- Hạn mức đã xác minh ----------------


def test_han_muc_youtube_la_100_moi_ngay():
    assert PublishPlatform.YOUTUBE.daily_upload_quota == 100
    assert PublishPlatform.FACEBOOK.daily_upload_quota is None  # chưa xác minh — không bịa số


# ---------------- Metadata và ghi nguồn ----------------


def test_ghi_nguon_duoc_chen_vao_dau_mo_ta():
    meta = VideoMetadata(title="Cpk nói gì", description="Phân tích của NMI.")
    withattr = meta.with_attribution("Nguồn: Vendor GmbH (CC BY 4.0)")
    assert withattr.description.startswith("Nguồn: Vendor GmbH")
    assert "Phân tích của NMI." in withattr.description


def test_ghi_nguon_khong_bi_chen_hai_lan():
    meta = VideoMetadata(title="x", description="Nguồn: A\n\nnội dung")
    assert meta.with_attribution("Nguồn: A").description.count("Nguồn: A") == 1


def test_tieu_de_qua_100_ky_tu_bi_tu_choi():
    with pytest.raises(InvariantViolation):
        VideoMetadata(title="x" * 101, description="y")


def test_tieu_de_rong_bi_tu_choi():
    with pytest.raises(InvariantViolation):
        VideoMetadata(title="   ", description="y")


# ---------------- Publication ----------------


def test_vong_doi_publication_thanh_cong():
    p = Publication(item_id=1, platform=PublishPlatform.YOUTUBE, id=1)
    p.start_upload()
    p.mark_published(remote_id="dQw4", remote_url="https://youtu.be/dQw4", at=NOW)
    assert p.status is PublishStatus.PUBLISHED
    assert p.published_at == NOW


def test_bo_qua_co_chu_y_luu_lai_ly_do():
    """Bỏ qua khác thất bại: để sau này không ai tưởng hệ thống hỏng."""
    p = Publication(item_id=1, platform=PublishPlatform.TIKTOK, id=2)
    p.skip("nguồn có watermark dán cứng")
    assert p.status is PublishStatus.SKIPPED
    assert p.skipped_reason == "nguồn có watermark dán cứng"


def test_that_bai_thi_xep_lai_duoc_nhung_da_dang_thi_khong():
    p = Publication(item_id=1, platform=PublishPlatform.YOUTUBE, id=3)
    p.start_upload()
    p.fail("429 rate limit")
    p.requeue()
    assert p.status is PublishStatus.QUEUED

    q = Publication(item_id=1, platform=PublishPlatform.YOUTUBE, id=4)
    q.start_upload()
    q.mark_published(remote_id="a", remote_url=None, at=NOW)
    with pytest.raises(InvalidTransition):
        q.fail("thử đổi sau khi đã đăng")


def test_khong_xac_nhan_da_dang_ma_thieu_remote_id():
    p = Publication(item_id=1, platform=PublishPlatform.YOUTUBE, id=5)
    p.start_upload()
    with pytest.raises(InvariantViolation):
        p.mark_published(remote_id="  ", remote_url=None, at=NOW)

"""Máy trạng thái của ``Item`` và các quyết định pipeline gắn với nó."""

from __future__ import annotations

from datetime import UTC

import pytest

from src.domain.errors import HumanReviewRequired, InvalidTransition, InvariantViolation
from src.domain.production.entities import Item
from src.domain.production.value_objects import (
    PORTRAIT_9_16,
    AspectRatio,
    ItemStage,
    MediaAsset,
    ReframeMode,
    Segment,
    SpeechRate,
    SyllableBudget,
)
from src.domain.sourcing.value_objects import SourceUrl
from tests.unit.test_license_gate import NOW, approved_source

ITEM_URL = SourceUrl("https://www.youtube.com/watch?v=abc123")
OUTPUT = MediaAsset("output/item-00000001/final.mp4")


def fresh_item() -> Item:
    src = approved_source()
    item = Item.accept(url=ITEM_URL, clearance=src.clear_for_download(NOW))
    item.id = 1
    return item


def item_at_review() -> tuple[Item, Item]:
    """Đưa item đi hết pipeline tới gate duyệt của người."""
    src = approved_source()
    item = fresh_item()
    item.mark_downloaded(path=MediaAsset("source/a.mp4"), duration_sec=600,
                         aspect_ratio=AspectRatio(16, 9))
    item.mark_separated()
    item.mark_transcribed()
    item.send_transcript_to_review()
    item.approve_transcript()
    item.pick_segment(Segment(120.0, 180.0, rationale="có số liệu Cpk kiểm chứng được"))
    item.attach_script(script_vi="Cpk chỉ nói về độ lệch trong nhóm mẫu.",
                       clearance=src.clear_for_dubbing(NOW))
    item.mark_voiced()
    item.mark_aligned()
    item.mark_mixed()
    item.mark_rendered(path=OUTPUT)
    item.send_to_human_review()
    return item, src


# ---------------- Khởi tạo chỉ có hai đường ----------------


def test_accept_doi_clearance_nen_khong_tao_duoc_item_lam_viec_ma_khong_qua_gate():
    item = fresh_item()
    assert item.stage is ItemStage.INBOX
    assert item.source_id == 1


def test_item_bi_chan_license_thi_dung_han_khong_di_tiep_duoc():
    item = Item.blocked(url=ITEM_URL, source_id=7, reason="nguồn chưa được duyệt")
    item.id = 2
    assert item.stage is ItemStage.LICENSE_BLOCKED
    # license_blocked không có đường ra — phải đi duyệt nguồn, không đi tắt
    with pytest.raises(InvalidTransition):
        item.mark_downloaded(path=MediaAsset("source/a.mp4"))


def test_duyet_transcript_co_trang_thai_rieng_khong_con_nam_trong_hang_cho():
    item = fresh_item()
    item.mark_downloaded(path=MediaAsset("source/a.mp4"))
    item.mark_separated()
    item.mark_transcribed()
    item.send_transcript_to_review()

    item.approve_transcript()

    assert item.stage is ItemStage.TRANSCRIPT_APPROVED
    item.pick_segment(Segment(10.0, 70.0))
    assert item.stage is ItemStage.SEGMENT_PICKED


# ---------------- Gate duyệt của người ----------------


def test_khong_publish_duoc_khi_chua_qua_nguoi_duyet():
    item, _ = item_at_review()
    assert item.stage is ItemStage.HUMAN_REVIEW
    with pytest.raises(HumanReviewRequired):
        item.mark_published()


def test_duyet_roi_moi_publish_duoc():
    item, _ = item_at_review()
    item.approve(by="quan.nguyen", at=NOW)
    assert item.is_ready_to_publish
    item.mark_published()
    assert item.stage is ItemStage.PUBLISHED


def test_duyet_phai_ghi_ten_nguoi_duyet():
    item, _ = item_at_review()
    with pytest.raises(InvariantViolation):
        item.approve(by="", at=NOW)


def test_published_la_trang_thai_cuoi():
    item, _ = item_at_review()
    item.approve(by="quan.nguyen", at=NOW)
    item.mark_published()
    with pytest.raises(InvalidTransition):
        item.fail("thử đổi sau khi đã đăng")


# ---------------- Clearance phải thuộc đúng nguồn ----------------


def test_khong_dung_clearance_cua_nguon_khac():
    item = fresh_item()
    item.mark_downloaded(path=MediaAsset("source/a.mp4"), duration_sec=600)
    item.mark_separated()
    item.mark_transcribed()
    item.send_transcript_to_review()
    item.approve_transcript()
    item.pick_segment(Segment(10.0, 70.0))

    nguon_khac = approved_source(id=99, url=SourceUrl("https://vimeo.com/other"))
    with pytest.raises(InvariantViolation) as exc:
        item.attach_script(script_vi="abc", clearance=nguon_khac.clear_for_dubbing(NOW))
    assert "#99" in str(exc.value)


# ---------------- Nhảy bước là lỗi, không phải cảnh báo ----------------


def test_khong_nhay_tu_inbox_sang_rendered():
    with pytest.raises(InvalidTransition):
        fresh_item().mark_rendered(path=OUTPUT)


def test_that_bai_cho_chay_lai_tu_dau():
    item = fresh_item()
    item.fail("yt-dlp trả 403")
    assert item.stage_error == "yt-dlp trả 403"
    item.retry()
    assert item.stage is ItemStage.INBOX


# ---------------- Đoạn được chọn ----------------


def test_doan_khong_duoc_vuot_do_dai_video():
    item = fresh_item()
    item.mark_downloaded(path=MediaAsset("source/a.mp4"), duration_sec=100)
    item.mark_separated()
    item.mark_transcribed()
    item.send_transcript_to_review()
    item.approve_transcript()
    with pytest.raises(InvariantViolation):
        item.pick_segment(Segment(60.0, 150.0))


@pytest.mark.parametrize(
    "start,end",
    [(10.0, 10.0), (50.0, 40.0), (-1.0, 50.0)],
)
def test_doan_khong_hop_le_bi_tu_choi(start, end):
    with pytest.raises(InvariantViolation):
        Segment(start, end)


def test_cua_so_45_75s_la_khuyen_nghi_khong_phai_bien_cung():
    assert Segment(0.0, 60.0).is_recommended_length is True
    ngan = Segment(0.0, 20.0)
    assert ngan.is_recommended_length is False  # vẫn dựng được, chỉ là ngoài khuyến nghị
    assert Segment(0.0, 5.0).is_recommended_length is False
    assert Segment(0.0, 300.0).is_recommended_length is False


# ---------------- Reframe có điều kiện ----------------


def test_nguon_da_9_16_thi_khong_reframe():
    item = fresh_item()
    item.mark_downloaded(path=MediaAsset("source/a.mp4"), aspect_ratio=AspectRatio(1080, 1920))
    assert item.needs_reframe is False
    assert item.reframe_mode is None


def test_nguon_16_9_thi_reframe_bang_blur_khong_phai_crop():
    """Video công nghiệp: toàn khung hình mang thông tin, cắt là mất thông tin."""
    item = fresh_item()
    item.mark_downloaded(path=MediaAsset("source/a.mp4"), aspect_ratio=AspectRatio(16, 9))
    assert item.needs_reframe is True
    assert item.reframe_mode is ReframeMode.BLUR


def test_chua_biet_ty_le_thi_coi_nhu_can_reframe():
    assert fresh_item().needs_reframe is True


def test_aspect_ratio_rut_gon_tu_kich_thuoc_thuc():
    assert str(AspectRatio.from_size(1920, 1080)) == "16:9"
    assert AspectRatio.from_size(1080, 1920) == PORTRAIT_9_16
    assert str(AspectRatio.parse("9:16")) == "9:16"


@pytest.mark.parametrize("bad", ["16-9", "16:", "abc", "0:9"])
def test_ty_le_sai_dinh_dang_bi_tu_choi(bad):
    with pytest.raises(InvariantViolation):
        AspectRatio.parse(bad)


# ---------------- Ngân sách âm tiết ----------------


def test_kich_ban_tran_ngan_sach_thi_viet_lai_khong_tang_toc_doc():
    """F2.3: quá 5% thì trả kịch bản về cho LLM, không nhồi bằng tốc độ."""
    budget = SyllableBudget(window_sec=60.0, rate=SpeechRate(5.5))
    assert budget.max_syllables == 330
    assert budget.overruns(62.0) is False  # trong ngưỡng 5%
    assert budget.overruns(64.0) is True

    item, _ = item_at_review()
    item.approve(by="q", at=NOW)


def test_kich_ban_tran_thi_item_quay_ve_buoc_viet_lai():
    src = approved_source()
    item = fresh_item()
    item.mark_downloaded(path=MediaAsset("source/a.mp4"), duration_sec=600)
    item.mark_separated()
    item.mark_transcribed()
    item.send_transcript_to_review()
    item.approve_transcript()
    item.pick_segment(Segment(0.0, 60.0))
    item.attach_script(script_vi="bản quá dài", clearance=src.clear_for_dubbing(NOW))
    item.rewrite_script("TTS dài 68s, khung 60s — vượt 13%")
    assert item.stage is ItemStage.SEGMENT_PICKED
    assert "vượt 13%" in (item.stage_error or "")


def test_toc_do_doc_khong_co_gia_tri_mac_dinh_va_tu_choi_so_vo_ly():
    with pytest.raises(TypeError):
        SpeechRate()  # type: ignore[call-arg]
    with pytest.raises(InvariantViolation):
        SpeechRate(0.5)
    with pytest.raises(InvariantViolation):
        SpeechRate(50.0)


# ---------------- Đường dẫn media ----------------


@pytest.mark.parametrize(
    "bad",
    ["/abs/path.mp4", "C:/x.mp4", "work/../../etc/passwd", "", "\\win\\path.mp4"],
)
def test_media_asset_tu_choi_duong_dan_khong_an_toan(bad):
    with pytest.raises(InvariantViolation):
        MediaAsset(bad)


def test_datetime_dung_utc():
    assert NOW.tzinfo is UTC

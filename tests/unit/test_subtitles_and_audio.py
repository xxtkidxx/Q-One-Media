"""Phần thuần tính toán của tầng media: dựng ASS và mức âm lượng.

Không cần ffmpeg — đây đúng là loại lỗi mắt không thấy: một centisecond
lệch, hoặc nền tiếng máy đặt sai mức vài dB.
"""

from __future__ import annotations

import pytest

from src.infrastructure.media.ffmpeg import (
    BACKGROUND_DB,
    DUCK_ATTACK_MS,
    DUCK_RELEASE_MS,
    VIETNAMESE_GLYPH_PROBE,
    _ass_timestamp,
    build_ass,
)

# ---------------- Timestamp ASS ----------------


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (0.0, "0:00:00.00"),
        (1.5, "0:00:01.50"),
        (59.99, "0:00:59.99"),
        (60.0, "0:01:00.00"),
        (3599.999, "1:00:00.00"),  # làm tròn lên đúng giờ
        (3661.23, "1:01:01.23"),
        (-5.0, "0:00:00.00"),  # âm thì kẹp về 0, không sinh timestamp vô nghĩa
    ],
)
def test_timestamp_ass_dung_centisecond(seconds, expected):
    assert _ass_timestamp(seconds) == expected


# ---------------- Sinh ASS ----------------


def test_ass_co_playres_va_style():
    out = build_ass([(0.0, 2.0, "Cpk nói gì")], font_name="Be Vietnam Pro")
    assert "PlayResX: 1080" in out
    assert "PlayResY: 1920" in out
    assert "Be Vietnam Pro" in out
    assert "Dialogue: 0,0:00:00.00,0:00:02.00,Default" in out


def test_ass_giu_le_duoi_du_lon_cho_giao_dien_nen_tang():
    """TikTok/Reels/Shorts che ~15–20% đáy màn hình. Phụ đề sát đáy bị app che."""
    out = build_ass([(0.0, 1.0, "x")])
    style = next(ln for ln in out.splitlines() if ln.startswith("Style: Default"))
    margin_v = int(style.split(",")[-2])
    assert margin_v >= 1920 * 0.12


def test_ass_giu_nguyen_dau_tieng_viet():
    out = build_ass([(0.0, 3.0, VIETNAMESE_GLYPH_PROBE)])
    assert "ộ" in out and "ỹ" in out and "Ặ" in out


def test_ass_doi_newline_thanh_ma_ngat_dong():
    out = build_ass([(0.0, 1.0, "dòng một\ndòng hai")])
    assert r"dòng một\Ndòng hai" in out
    # Không được để newline thật lọt vào dòng Dialogue — file ASS sẽ hỏng
    dialogue = [ln for ln in out.splitlines() if ln.startswith("Dialogue")]
    assert len(dialogue) == 1


def test_ass_vo_hieu_hoa_dau_ngoac_nhon():
    """``{...}`` trong ASS là mã override. Chữ người viết không được thành mã."""
    out = build_ass([(0.0, 1.0, "giá trị {b1} tăng")])
    assert "{" not in out.split("[Events]")[1]


def test_ass_bo_cue_rong():
    out = build_ass([(0.0, 1.0, "   "), (1.0, 2.0, "có chữ")])
    assert len([ln for ln in out.splitlines() if ln.startswith("Dialogue")]) == 1


# ---------------- Mức âm lượng và ducking ----------------


def test_nen_mac_dinh_nam_trong_khoang_dac_ta_yeu_cau():
    """F2.4: nền tiếng máy ở −18…−22 dB — đủ nghe là máy thật, không át giọng."""
    assert -22.0 <= BACKGROUND_DB <= -18.0


def test_ducking_nha_cham_hon_bat_nhieu_lan():
    """`release` phải dài hơn `attack` nhiều lần.

    Nền dâng lại ngay sau mỗi khoảng ngắt giữa câu thì nghe như đang "thở" — đó là
    lỗi ai cũng nghe ra nhưng không ai chỉ được tên, nên chốt bằng test.
    """
    assert DUCK_RELEASE_MS >= DUCK_ATTACK_MS * 5

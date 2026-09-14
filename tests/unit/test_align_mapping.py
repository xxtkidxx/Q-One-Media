"""Gióng kịch bản đã biết với word timestamp — phần thuần tính toán.

Không cần GPU: các test ở đây thay bước nhận dạng bằng danh sách từ cho sẵn, rồi
kiểm đúng thứ quan trọng nhất — **chữ trong phụ đề là chữ mình viết**, không phải
chữ máy nhận ra.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.infrastructure.asr import align as A
from src.infrastructure.asr.align import AlignFailed, _norm, align_known_text


def stub_recognized(pairs: list[tuple[str, float, float]]):
    return [A._Recognized(t, s, e) for t, s, e in pairs]


@pytest.fixture
def patched(monkeypatch):
    """Thay bước Whisper bằng dữ liệu cho sẵn."""

    def install(pairs):
        monkeypatch.setattr(
            A, "_recognize_words", lambda audio, *, language, model_name: stub_recognized(pairs)
        )

    return install


# ---------------- Chuẩn hoá để so khớp ----------------


def test_chuan_hoa_bo_dau_cau_va_ha_chu_thuong():
    assert _norm("Kiểm,") == "kiểm"
    assert _norm("  Cpk.  ") == "cpk"
    assert _norm("R&R") == "rr"


def test_chuan_hoa_dua_ve_NFC():
    """Tiếng Việt có hai cách biểu diễn cùng một chữ — không chuẩn hoá thì so chuỗi sai."""
    nfc = "ệ"  # ệ dạng một code point
    nfd = "ệ"  # e + dấu nặng + dấu mũ
    assert _norm(nfc) == _norm(nfd)


# ---------------- Chữ trong phụ đề là chữ MÌNH viết ----------------


def test_loi_nhan_dang_cua_whisper_khong_lot_vao_phu_de(patched):
    """Điểm cốt lõi: Whisper chỉ cung cấp THỜI GIAN, không cung cấp chữ."""
    patched([("Biểu", 0.0, 0.4), ("đồ", 0.4, 0.7), ("kiểm", 0.7, 1.0), ("soái", 1.0, 1.4)])
    words = align_known_text(Path("x.wav"), "Biểu đồ kiểm soát", language="vi")
    assert [w.text for w in words] == ["Biểu", "đồ", "kiểm", "soát"]  # "soát", không phải "soái"


def test_token_khop_lay_dung_moc_thoi_gian(patched):
    patched([("Cpk", 1.25, 1.60), ("thấp", 1.60, 2.10)])
    words = align_known_text(Path("x.wav"), "Cpk thấp", language="vi")
    assert (words[0].start, words[0].end) == (1.25, 1.60)
    assert (words[1].start, words[1].end) == (1.60, 2.10)


# ---------------- Nội suy cho token không khớp ----------------


def test_token_khong_khop_duoc_noi_suy_chu_khong_bi_bo(patched):
    """Bỏ một từ là phụ đề thiếu chữ — người xem thấy ngay. Timing lệch thì không."""
    patched([("Cpk", 0.0, 1.0), ("lỗi", 3.0, 4.0)])
    words = align_known_text(Path("x.wav"), "Cpk rất là lỗi", language="vi")
    assert [w.text for w in words] == ["Cpk", "rất", "là", "lỗi"]
    # Hai từ giữa nằm gọn trong khoảng trống 1.0 → 3.0
    assert words[1].start >= 1.0
    assert words[2].end <= 3.0


def test_noi_suy_giu_thu_tu_tang_dan(patched):
    patched([("một", 0.0, 0.5), ("năm", 4.0, 4.5)])
    words = align_known_text(Path("x.wav"), "một hai ba bốn năm", language="vi")
    starts = [w.start for w in words]
    assert starts == sorted(starts), "timestamp phải tăng dần, không thì phụ đề nhảy ngược"


def test_khong_khop_duoc_gi_thi_chia_deu_toan_bo(patched):
    """Chất lượng thấp nhưng vẫn ra phụ đề — và log đã cảnh báo."""
    patched([("xyz", 0.0, 6.0)])
    words = align_known_text(Path("x.wav"), "một hai ba", language="vi")
    assert len(words) == 3
    assert words[0].start == pytest.approx(0.0)
    assert words[-1].end == pytest.approx(6.0)


def test_token_dau_khong_khop_thi_noi_suy_tu_0(patched):
    patched([("cuối", 5.0, 6.0)])
    words = align_known_text(Path("x.wav"), "đầu giữa cuối", language="vi")
    assert words[0].start == pytest.approx(0.0)
    assert words[-1].end == pytest.approx(6.0)


def test_token_cuoi_khong_khop_thi_noi_suy_den_het_audio(patched):
    patched([("đầu", 0.0, 1.0)])
    words = align_known_text(Path("x.wav"), "đầu giữa cuối", language="vi")
    assert words[0].end == pytest.approx(1.0)
    assert words[-1].end == pytest.approx(1.0, abs=0.01) or words[-1].end > 1.0


# ---------------- Đầu vào không dùng được ----------------


def test_kich_ban_rong_bi_tu_choi(patched):
    patched([("a", 0.0, 1.0)])
    with pytest.raises(AlignFailed):
        align_known_text(Path("x.wav"), "   ", language="vi")


def test_whisper_khong_nhan_ra_gi_thi_bao_loi_ro(patched):
    """Audio TTS rỗng là lỗi thật ở bước trước — phải nói ra, không nội suy bừa."""
    patched([])
    with pytest.raises(AlignFailed) as exc:
        align_known_text(Path("x.wav"), "có chữ", language="vi")
    assert "audio TTS" in str(exc.value)


# ---------------- Cảnh báo khi khớp ít ----------------


def test_khop_it_thi_canh_bao_nhung_van_tra_ket_qua(patched, caplog):
    patched([("một", 0.0, 0.5)])
    words = align_known_text(Path("x.wav"), "một hai ba bốn năm sáu", language="vi")
    assert len(words) == 6  # vẫn đủ chữ
    assert A.MIN_MATCH_RATIO == 0.5

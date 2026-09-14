"""Gộp từ thành dòng phụ đề — phần thuần tính toán của bước alignment.

Không cần GPU: hàm này chỉ nhận danh sách từ kèm timestamp.
"""

from __future__ import annotations

from src.infrastructure.asr.whisper import Word, group_words_into_cues


def w(text: str, start: float, end: float) -> Word:
    return Word(text=text, start=start, end=end)


def test_ngat_o_dau_cau_truoc_khi_ngat_vi_do_dai():
    """Dấu câu là ranh giới ngữ nghĩa thật; hai điều kiện kia chỉ là chặn trên."""
    words = [w("Cpk", 0.0, 0.4), w("thấp.", 0.4, 0.9), w("Nguyên", 1.0, 1.4), w("nhân", 1.4, 1.8)]
    cues = group_words_into_cues(words)
    assert cues[0] == (0.0, 0.9, "Cpk thấp.")
    assert cues[1] == (1.0, 1.8, "Nguyên nhân")


def test_ngat_khi_dong_qua_dai_va_khong_dong_nao_vuot_nguong():
    words = [w("từ", float(i), float(i) + 0.4) for i in range(20)]
    cues = group_words_into_cues(words, max_chars=20, max_sec=999)
    assert len(cues) > 1
    # Chặn trên phải là chặn thật: không dòng nào được vượt
    assert all(len(text) <= 20 for _, _, text in cues)


def test_ngat_khi_dong_keo_qua_lau():
    """Một dòng đứng quá lâu trên màn hình làm người xem tưởng video treo."""
    words = [w("a", 0.0, 3.0), w("b", 3.0, 6.0)]
    cues = group_words_into_cues(words, max_chars=999, max_sec=4.0)
    assert len(cues) == 2
    # Và không dòng nào dài hơn ngưỡng — kiểm sau khi thêm từ thì dòng đầu sẽ 6s
    assert all(end - start <= 4.0 for start, end, _ in cues)


def test_timestamp_lay_dau_tu_dau_va_cuoi_tu_cuoi():
    words = [w("một", 1.25, 1.60), w("hai.", 1.60, 2.10)]
    assert group_words_into_cues(words) == [(1.25, 2.10, "một hai.")]


def test_danh_sach_rong_tra_ve_rong():
    assert group_words_into_cues([]) == []


def test_tu_cuoi_khong_co_dau_cau_van_duoc_xuat_ra():
    """Không được rơi mất phần cuối chỉ vì kịch bản không kết bằng dấu câu."""
    cues = group_words_into_cues([w("chưa", 0.0, 0.5), w("hết", 0.5, 1.0)])
    assert cues == [(0.0, 1.0, "chưa hết")]

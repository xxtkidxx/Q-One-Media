"""Đọc file thuật ngữ đã duyệt.

Quy ước cần test vì nó dễ hiểu sai: **``term_vi`` để trống nghĩa là "giữ nguyên
tiếng Anh"**, không phải "chưa điền, bỏ qua dòng này". Corpus nmi.vn cho thấy NMI
viết "Cpk", "MES", "OPC UA" nguyên dạng trong câu tiếng Việt vì người trong ngành
gọi như vậy — dịch chúng ra làm nội dung khó đọc hơn với đúng nhóm cần đọc.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from load_glossary import _rows


def write_tsv(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "glossary.tsv"
    path.write_text(
        "# chú thích bị bỏ qua\n"
        "term_src\tterm_vi\tdomain\tso_lan\tvi_du\n" + body,
        encoding="utf-8",
    )
    return path


def test_term_vi_trong_nghia_la_giu_nguyen_tieng_anh(tmp_path):
    rows = _rows(write_tsv(tmp_path, "Cpk\t\tspc\t15\tví dụ\n"))
    assert rows == [("Cpk", "Cpk", "spc")]


def test_term_vi_co_gia_tri_thi_dung_gia_tri_do(tmp_path):
    rows = _rows(write_tsv(tmp_path, "control chart\tbiểu đồ kiểm soát\tspc\t9\tvd\n"))
    assert rows == [("control chart", "biểu đồ kiểm soát", "spc")]


def test_bo_qua_dong_chu_thich_va_dong_tieu_de(tmp_path):
    assert _rows(write_tsv(tmp_path, "")) == []


def test_domain_khong_hop_le_thi_de_trong_chu_khong_bo_dong(tmp_path):
    """Domain sai là lỗi phân loại, không phải lý do bỏ mất một thuật ngữ."""
    rows = _rows(write_tsv(tmp_path, "MES\t\tkhong-ton-tai\t63\tvd\n"))
    assert rows == [("MES", "MES", "")]


def test_domain_khong_phan_biet_hoa_thuong(tmp_path):
    rows = _rows(write_tsv(tmp_path, "MSA\t\tMSA_SAI\t1\tvd\nGage R&R\t\tMSA\t22\tvd\n"))
    assert rows[-1] == ("Gage R&R", "Gage R&R", "msa")


def test_dong_thieu_cot_bi_bo_qua_khong_lam_vo_ca_file(tmp_path):
    rows = _rows(write_tsv(tmp_path, "thieu-cot\nOPC UA\t\tconnectivity\t14\tvd\n"))
    assert rows == [("OPC UA", "OPC UA", "connectivity")]


def test_term_src_rong_bi_bo_qua(tmp_path):
    assert _rows(write_tsv(tmp_path, "\tgì đó\tspc\t1\tvd\n")) == []


def test_khoang_trang_hai_dau_bi_cat(tmp_path):
    rows = _rows(write_tsv(tmp_path, "  RS-232  \t  RS-232  \t connectivity \t12\tvd\n"))
    assert rows == [("RS-232", "RS-232", "connectivity")]


@pytest.mark.parametrize("domain", ["spc", "msa", "mes", "historian", "vision", "connectivity"])
def test_moi_domain_hop_le_deu_duoc_nhan(tmp_path, domain):
    rows = _rows(write_tsv(tmp_path, f"X\t\t{domain}\t2\tvd\n"))
    assert rows[0][2] == domain

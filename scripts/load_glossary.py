"""Nạp bảng thuật ngữ từ TSV vào bảng ``glossary``.

    make glossary-load

Đọc ``research/nmi-scan/glossary-candidates.tsv`` (do
``scripts/nmi_corpus.py terms`` sinh ra, người duyệt điền cột ``term_vi``).

Quy ước quan trọng: **``term_vi`` để trống nghĩa là "giữ nguyên tiếng Anh"**, và
đó là một quyết định hợp lệ — thường là quyết định đúng. Corpus nmi.vn cho thấy
NMI viết "Cpk", "MES", "OPC UA", "PLC" nguyên dạng ngay trong câu tiếng Việt, vì
người trong ngành gọi như vậy. Dịch chúng ra tiếng Việt là làm nội dung *khó*
đọc hơn với đúng nhóm khán giả cần đọc nó.

Khi ``term_vi`` trống, script ghi ``term_vi = term_src``. Prompt viết kịch bản
nhận cặp "Cpk → Cpk" và hiểu đúng là giữ nguyên.

Chạy lại được nhiều lần: dòng đã có thì cập nhật, không nhân đôi.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

TSV = Path(__file__).resolve().parents[1] / "research" / "nmi-scan" / "glossary-candidates.tsv"

VALID_DOMAINS = {"spc", "msa", "mes", "historian", "vision", "connectivity", ""}


def _rows(path: Path) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.rstrip("\n")
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if parts[0].strip() == "term_src":  # dòng tiêu đề
            continue
        if len(parts) < 2:
            print(f"  ! dòng {lineno} thiếu cột, bỏ qua: {line[:60]}")
            continue
        term_src = parts[0].strip()
        term_vi = parts[1].strip()
        domain = (parts[2].strip().lower() if len(parts) > 2 else "")
        if not term_src:
            continue
        if domain not in VALID_DOMAINS:
            print(f"  ! dòng {lineno}: domain {domain!r} không hợp lệ, để trống")
            domain = ""
        # Trống = giữ nguyên tiếng Anh. Ghi rõ thành term_vi = term_src để prompt
        # nhận được một cặp tường minh thay vì phải suy ra từ giá trị rỗng.
        out.append((term_src, term_vi or term_src, domain))
    return out


def main() -> int:
    if not TSV.exists():
        print(f"Không thấy {TSV}")
        print("Chạy trước: python scripts/nmi_corpus.py fetch")
        print("           python scripts/nmi_corpus.py terms")
        return 1
    if not os.environ.get("DATABASE_URL"):
        print("Thiếu DATABASE_URL — chạy trong container: make glossary-load")
        return 1

    from sqlalchemy import text

    from src.infrastructure.db.uow import SqlUnitOfWork, make_engine, make_session_factory

    rows = _rows(TSV)
    if not rows:
        print("Không có dòng nào dùng được.")
        return 1

    kept_english = sum(1 for src, vi, _ in rows if src == vi)
    translated = len(rows) - kept_english

    uow = SqlUnitOfWork(make_session_factory(make_engine(os.environ["DATABASE_URL"])))
    with uow:
        for term_src, term_vi, domain in rows:
            uow.session.execute(
                text(
                    "INSERT INTO glossary (src_lang, term_src, term_vi, domain) "
                    "VALUES ('en', :src, :vi, :domain) "
                    "ON CONFLICT (src_lang, term_src) DO UPDATE "
                    "SET term_vi = EXCLUDED.term_vi, domain = EXCLUDED.domain"
                ),
                {"src": term_src, "vi": term_vi, "domain": domain or None},
            )
        total = uow.session.execute(text("SELECT count(*) FROM glossary")).scalar()
        uow.commit()

    print(f"Nạp {len(rows)} thuật ngữ:")
    print(f"  {kept_english} giữ nguyên tiếng Anh (term_vi = term_src)")
    print(f"  {translated} có bản tiếng Việt")
    print(f"Bảng glossary hiện có {total} dòng.")
    print()
    print("Prompt viết kịch bản sẽ nhận bảng này và dùng đúng thuật ngữ.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

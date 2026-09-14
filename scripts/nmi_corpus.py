"""Tải và khai thác corpus song ngữ từ nmi.vn — nguồn cho bảng thuật ngữ (G1.3).

    python scripts/nmi_corpus.py fetch    # tải bundle về research/nmi-scan/
    python scripts/nmi_corpus.py terms    # rút thuật ngữ ứng viên ra TSV

**nmi.vn là website của chính NMI, không phải nguồn nội dung để làm video.** Nó
có mặt ở đây vì hai thứ khác: taxonomy chủ đề, và cách NMI **đã** gọi các thuật
ngữ kỹ thuật bằng tiếng Việt. Cái thứ hai là thứ quý: nó cho biết công ty gọi
"control chart" là "biểu đồ kiểm soát", và giữ nguyên "Cp/Cpk" chứ không dịch.

Vì sao phải tải bundle thay vì đọc HTML: nmi.vn là Vite SPA **không có SSR** —
mọi đường dẫn trả về cùng một shell 3.102 byte với ``<div id="app">`` rỗng. Nội
dung nằm trong các bundle ``/assets/{vi,en}-<hash>.js``. Tên file chứa hash nội
dung nên **đổi mỗi lần build**; script này đọc ``index.html`` để tìm tên hiện tại
thay vì gắn cứng.

Đầu ra của ``terms`` là **ứng viên cần người duyệt**, không phải bảng thuật ngữ
dùng được ngay. Một thuật ngữ dịch sai trong bảng sẽ đi vào **mọi** video sau đó,
nên đây là chỗ không tự động hoá hết được.
"""

from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

SITE = "https://nmi.vn"
DEST = Path(__file__).resolve().parents[1] / "research" / "nmi-scan"
CANDIDATES_FILE = DEST / "glossary-candidates.tsv"

_ASSET_RE = re.compile(r'(?:src|href)="(/assets/(?:vi|en|index|site|faqs)-[^"]+\.js)"')
# Chuỗi trong bundle Vite: dấu nháy kép, nháy đơn, hoặc backtick.
_STRING_RE = re.compile(r'"((?:[^"\\]|\\.){4,400})"|\'((?:[^\'\\]|\\.){4,400})\'')


def _get(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"không tải được {url}: {exc}") from exc


# ---------------- fetch ----------------


def cmd_fetch() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    print(f"Đọc {SITE} để tìm tên bundle hiện tại …")
    index = _get(SITE + "/").decode("utf-8", "replace")
    (DEST / "index.html").write_text(index, encoding="utf-8")

    assets = sorted(set(_ASSET_RE.findall(index)))
    if not assets:
        print("Không tìm thấy bundle nào trong index.html.")
        print("Có thể nmi.vn đã đổi cách build — kiểm tay rồi sửa _ASSET_RE.")
        return 1

    print(f"Thấy {len(assets)} bundle:")
    total = 0
    for path in assets:
        name = path.rsplit("/", 1)[-1]
        try:
            data = _get(SITE + path)
        except RuntimeError as exc:
            print(f"  ✗ {name}: {exc}")
            continue
        (DEST / name).write_bytes(data)
        total += len(data)
        print(f"  ✓ {name} ({len(data) // 1024} KB)")

    readme = DEST / "README.md"
    readme.write_text(
        "# research/nmi-scan/\n\n"
        "Corpus song ngữ tải từ nmi.vn bằng `python scripts/nmi_corpus.py fetch`.\n\n"
        "**Đây KHÔNG phải nguồn nội dung để làm video** — nmi.vn là website của chính\n"
        "NMI. Nó có mặt ở đây vì hai thứ: taxonomy chủ đề, và cách NMI đã gọi các\n"
        "thuật ngữ kỹ thuật bằng tiếng Việt (đầu vào cho bảng `glossary`, G1.3).\n\n"
        "Tên file chứa hash nội dung nên **đổi mỗi lần nmi.vn build lại**. Vì vậy\n"
        "production không bao giờ đọc trực tiếp các đường dẫn này — chạy lại script.\n\n"
        f"Lần tải gần nhất: {len(assets)} bundle, {total // 1024} KB.\n",
        encoding="utf-8",
    )
    print(f"\nXong: {total // 1024} KB vào {DEST}")
    print("Bước tiếp: python scripts/nmi_corpus.py terms")
    return 0


# ---------------- terms ----------------

# Thuật ngữ kỹ thuật ngành: chữ in hoa liền, có gạch/chấm/&, hoặc tên giao thức.
# Lọc thô ở đây, người duyệt lọc tinh ở bước sau.
_TERM_RE = re.compile(
    r"\b("
    r"[A-Z][A-Za-z]*(?:\s?[A-Z][A-Za-z]*){0,2}\s?R&R"      # Gage R&R
    r"|C[pk]{1,2}(?:/[CP][pkm]{1,2})*"                      # Cp/Cpk/Pp/Ppk/Cpm
    r"|[A-Z]{2,6}(?:[\s-][A-Z]{1,4})?(?:-\d{2,4})?"         # SPC, MSA, OPC UA, RS-232
    r"|X̄-[RS]|I-MR"                                          # tên biểu đồ kiểm soát
    r")\b"
)

# Từ viết hoa nhưng KHÔNG phải thuật ngữ — lọc ra để danh sách người duyệt ngắn lại.
_STOP_TERMS = {
    "AND", "OR", "THE", "FOR", "NOT", "ALL", "NEW", "ONE", "QONE", "NMI",
    "PDF", "PNG", "JPG", "SVG", "CSS", "HTML", "JSON", "HTTP", "HTTPS", "URL",
    "API", "ID", "OK", "TRUE", "FALSE", "NULL", "UTF",
}


def _strings_from(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    out = []
    for m in _STRING_RE.finditer(text):
        s = (m.group(1) or m.group(2) or "").strip()
        # Bỏ chuỗi kỹ thuật của bundler: đường dẫn, class CSS, tên hàm
        if not s or s.startswith(("/", "./", "http", "#", "_", "$")):
            continue
        if "\\u" in s or (s.count(" ") == 0 and len(s) < 8):
            continue
        out.append(s.replace("\\n", " ").replace('\\"', '"'))
    return out


def _is_vietnamese(text: str) -> bool:
    """Tiếng Việt nhận ra bằng dấu — đủ tin cậy ở đây vì bundle en gần như không có."""
    return bool(re.search(r"[ăâđêôơưÁÀẢÃẠáàảãạíìỉĩịúùủũụéèẻẽẹóòỏõọýỳỷỹỵ]", text))


def cmd_terms() -> int:
    if not DEST.exists():
        print(f"Chưa có {DEST}. Chạy trước: python scripts/nmi_corpus.py fetch")
        return 1

    vi_files = sorted(DEST.glob("vi-*.js")) + sorted(DEST.glob("index-*.js"))
    en_files = sorted(DEST.glob("en-*.js"))
    if not vi_files and not en_files:
        print(f"Không thấy bundle nào trong {DEST}. Chạy lại: fetch")
        return 1

    vi_strings = [s for f in vi_files for s in _strings_from(f)]
    en_strings = [s for f in en_files for s in _strings_from(f)]
    print(f"Bundle vi: {len(vi_files)} file, {len(vi_strings)} chuỗi")
    print(f"Bundle en: {len(en_files)} file, {len(en_strings)} chuỗi")

    # Tín hiệu quan trọng nhất: thuật ngữ tiếng Anh xuất hiện TRONG câu tiếng Việt.
    # Đó chính là những thuật ngữ NMI cố ý KHÔNG dịch — và prompt viết kịch bản cần
    # biết danh sách đó để không tự dịch chúng.
    kept_english: Counter[str] = Counter()
    examples: dict[str, str] = {}
    for s in vi_strings:
        if not _is_vietnamese(s):
            continue
        for raw_term in _TERM_RE.findall(s):
            term = raw_term.strip()
            if len(term) < 2 or term.upper() in _STOP_TERMS:
                continue
            kept_english[term] += 1
            examples.setdefault(term, s[:160])

    rows = [
        (term, count, examples[term])
        for term, count in kept_english.most_common()
        if count >= 2  # xuất hiện một lần có thể là lỗi chính tả
    ]

    DEST.mkdir(parents=True, exist_ok=True)
    with CANDIDATES_FILE.open("w", encoding="utf-8", newline="") as fh:
        fh.write("# Ứng viên bảng thuật ngữ, rút từ corpus nmi.vn.\n")
        fh.write("# CẦN NGƯỜI DUYỆT: một thuật ngữ dịch sai ở đây đi vào MỌI video sau đó.\n")
        fh.write("#\n")
        fh.write("# term_src: thuật ngữ tiếng Anh xuất hiện trong câu tiếng Việt của nmi.vn\n")
        fh.write("# term_vi:  ĐIỀN TAY. Để trống hoặc ghi lại chính term_src nghĩa là\n")
        fh.write("#           'giữ nguyên tiếng Anh' — cũng là một quyết định hợp lệ và\n")
        fh.write("#           thường là đúng với Cpk, MES, OPC UA.\n")
        fh.write("# domain:   spc | msa | mes | historian | vision | connectivity\n")
        fh.write("#\n")
        fh.write("term_src\tterm_vi\tdomain\tso_lan\tvi_du\n")
        for term, count, example in rows:
            fh.write(f"{term}\t\t\t{count}\t{example}\n")

    print(f"\nGhi {len(rows)} ứng viên vào {CANDIDATES_FILE}")
    print("\n20 thuật ngữ xuất hiện nhiều nhất trong câu tiếng Việt:")
    for term, count, _ in rows[:20]:
        print(f"  {count:4d}×  {term}")
    print("\nBước tiếp: điền cột term_vi và domain, rồi:")
    print("  make glossary-load")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in ("fetch", "terms"):
        print(__doc__)
        return 2
    return cmd_fetch() if argv[0] == "fetch" else cmd_terms()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Tải font tiếng Việt vào ``docker/worker/fonts/`` trước khi build image.

Chạy: ``make fonts``

Vì sao không commit file .ttf vào repo: đây là nhị phân ~200 KB mỗi weight, và
Be Vietnam Pro có license OFL nên tải lại lúc nào cũng được. Vì sao không tải
trong Dockerfile: build sẽ phụ thuộc mạng và không lặp lại được.

**Font là ràng buộc thật, không phải chi tiết thẩm mỹ.** Nhiều font thiếu dải
U+1Exx (ậ ả ằ ầ ấ ể ệ ỉ ồ ớ ộ ủ ự). Khi thiếu, libass **không báo lỗi** — nó chỉ
ghi một dòng ``fontselect`` ở mức info rồi âm thầm thay font khác, ffmpeg trả mã
0, và chữ tiếng Việt sai kiểu trong video đã lên sóng. Xem
``src/infrastructure/media/ffmpeg.py:find_font_problems``.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request
from pathlib import Path

DEST = Path(__file__).resolve().parents[1] / "docker" / "worker" / "fonts"

# Be Vietnam Pro — thiết kế riêng cho tiếng Việt, license OFL (dùng thương mại được).
# Lấy trực tiếp từ repo google/fonts thay vì qua API fonts.googleapis.com: link ổn
# định, không phụ thuộc CSS parsing, và tải đúng file .ttf.
BASE = (
    "https://raw.githubusercontent.com/google/fonts/main/ofl/bevietnampro/"
)
FONTS = [
    "BeVietnamPro-Regular.ttf",
    "BeVietnamPro-SemiBold.ttf",
    "BeVietnamPro-Bold.ttf",
]
LICENSE_FILE = "OFL.txt"


# Ngưỡng tối thiểu khác nhau theo loại file: một file .ttf dưới 10 KB chắc chắn là
# trang lỗi HTML, nhưng bản OFL.txt thật chỉ khoảng 4 KB. Dùng một ngưỡng cho cả
# hai là tự loại bỏ file hợp lệ.
MIN_FONT_BYTES = 10_000
MIN_TEXT_BYTES = 1_000


def _fetch(name: str, dest: Path, *, min_bytes: int = MIN_FONT_BYTES) -> bool:
    url = BASE + name
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = resp.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"  ✗ {name}: {exc}")
        return False
    if len(data) < min_bytes:
        print(f"  ✗ {name}: chỉ {len(data)} byte — chắc là trang lỗi")
        return False
    dest.write_bytes(data)
    print(f"  ✓ {name} ({len(data) // 1024} KB)")
    return True


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    print(f"Tải font vào {DEST}")

    ok = 0
    for name in FONTS:
        target = DEST / name
        if target.exists() and target.stat().st_size > 10_000:
            print(f"  · {name} đã có, bỏ qua")
            ok += 1
            continue
        if _fetch(name, target):
            ok += 1

    # License phải đi kèm font — nghĩa vụ của OFL, và cũng để người sau biết
    # font này được phép dùng thương mại.
    lic = DEST / LICENSE_FILE
    if not lic.exists():
        _fetch(LICENSE_FILE, lic, min_bytes=MIN_TEXT_BYTES)

    if ok == 0:
        print("\nKhông tải được font nào.")
        print("Cách khác: tải tay từ https://fonts.google.com/specimen/Be+Vietnam+Pro")
        print(f"rồi đặt file .ttf vào {DEST}")
        return 1

    print(f"\n{ok}/{len(FONTS)} font sẵn sàng. Build lại worker: make dev-build")
    print("Kiểm glyph sau khi build:")
    print("  make shell")
    print('  python -c "from src.infrastructure.media.ffmpeg import '
          "check_font_covers_vietnamese as c; print(c('Be Vietnam Pro') or 'DAT')\"")
    return 0 if ok == len(FONTS) else 1


if __name__ == "__main__":
    sys.exit(main())

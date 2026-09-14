"""Cấp token OAuth cho YouTube một lần, trên máy có trình duyệt.

Chạy **trên máy của bạn**, không chạy trong container: luồng OAuth của Google cần
mở trình duyệt, và container không có. Sau đó copy file token vào chỗ
``YOUTUBE_TOKEN_FILE`` trỏ tới.

    python scripts/youtube_authorize.py client_secret.json .secrets/youtube_token.json

Token có hai phần: access token hết hạn sau 1 giờ, và refresh token dùng lâu dài.
Adapter tự refresh nên chỉ phải chạy script này một lần — trừ khi bạn thu hồi
quyền hoặc đổi scope.
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

# Chỉ xin quyền upload, không xin quyền đọc/sửa/xoá video. Xin đúng thứ cần là
# cách giảm rủi ro rẻ nhất: token bị lộ cũng không xoá được video nào.
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2

    client_secret = Path(argv[0])
    token_out = Path(argv[1])

    if not client_secret.exists():
        print(f"Không thấy {client_secret}")
        print("Lấy file này ở Google Cloud Console → APIs & Services → Credentials")
        print("→ Create OAuth client ID → loại 'Desktop app' → Download JSON. (G3.1)")
        return 1

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Cần: pip install google-auth-oauthlib")
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
    # Cổng 0 = để OS chọn cổng rảnh. Cố định một cổng thì lần nào cổng đó đang bị
    # chiếm là script chết mà không nói rõ lý do.
    creds = flow.run_local_server(port=0, prompt="consent")

    token_out.parent.mkdir(parents=True, exist_ok=True)
    token_out.write_text(creds.to_json(), encoding="utf-8")
    with contextlib.suppress(OSError):
        token_out.chmod(0o600)  # không có tác dụng trên Windows, vô hại

    print(f"\nĐã ghi token: {token_out}")
    print("Đặt vào .env:")
    print(f"  YOUTUBE_CLIENT_SECRET_FILE={client_secret}")
    print(f"  YOUTUBE_TOKEN_FILE={token_out}")
    print("\nFile này là bí mật — .gitignore đã loại *token*.json, đừng commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

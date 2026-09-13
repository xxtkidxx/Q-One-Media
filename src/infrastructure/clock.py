"""Đồng hồ hệ thống.

Luôn dùng UTC có timezone. Lý do cụ thể, không phải sở thích: so sánh
``expires_at`` của license với một ``datetime`` naive sẽ ném ``TypeError`` giữa
lúc chạy, và chỗ ném ra là đúng trong license gate.
"""

from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

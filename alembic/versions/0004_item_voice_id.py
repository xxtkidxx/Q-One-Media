"""Giọng đọc chọn theo từng video.

Trước đây giọng là một biến môi trường cho cả hệ thống, nên đổi giọng cho một
video là đổi cho mọi video đang chạy. Cột này đưa lựa chọn xuống đúng nơi nó
thuộc về — từng item — và ``NULL`` giữ nguyên hành vi cũ: theo ``TTS_ENGINE``.

Revision ID: 0004_item_voice_id
Revises: 0003_multi_clip_attribution
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_item_voice_id"
down_revision = "0003_multi_clip_attribution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("items")}
    if "voice_id" not in columns:
        op.add_column("items", sa.Column("voice_id", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("items", "voice_id")

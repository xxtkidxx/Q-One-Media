"""Tách tỷ lệ đầu ra khỏi tỷ lệ media nguồn.

Revision ID: 0006_output_aspect_ratio
Revises: 0005_user_accounts
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_output_aspect_ratio"
down_revision = "0005_user_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("items", sa.Column("output_aspect_ratio", sa.Text(), nullable=True))
    # Nội dung cũ giữ đúng hành vi 9:16 trước khi có lựa chọn này.
    op.execute("UPDATE items SET output_aspect_ratio = '9:16'")


def downgrade() -> None:
    op.drop_column("items", "output_aspect_ratio")

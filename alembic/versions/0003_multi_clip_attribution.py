"""Một video nguồn sinh nhiều clip và tùy chọn thẻ ghi nguồn.

Revision ID: 0003_multi_clip_attribution
Revises: 0002_transcript_approved_stage
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_multi_clip_attribution"
down_revision = "0002_transcript_approved_stage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("items", sa.Column("parent_item_id", sa.BigInteger(), nullable=True))
    op.add_column("items", sa.Column("clip_index", sa.Integer(), nullable=False, server_default="1"))
    op.add_column(
        "items", sa.Column("include_attribution", sa.Boolean(), nullable=False, server_default=sa.true())
    )
    op.create_foreign_key(
        "items_parent_item_id_fkey", "items", "items", ["parent_item_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("items_parent_idx", "items", ["parent_item_id"])


def downgrade() -> None:
    op.drop_index("items_parent_idx", table_name="items")
    op.drop_constraint("items_parent_item_id_fkey", "items", type_="foreignkey")
    op.drop_column("items", "include_attribution")
    op.drop_column("items", "clip_index")
    op.drop_column("items", "parent_item_id")

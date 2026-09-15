"""Tài khoản web và phân quyền.

Revision ID: 0005_user_accounts
Revises: 0004_item_voice_id
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_user_accounts"
down_revision = "0004_item_voice_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "user_accounts" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "user_accounts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("username", sa.String(80), nullable=False, unique=True),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('viewer','reviewer','editor','admin')", name="user_role_valid"),
    )
    op.create_index("user_accounts_username_idx", "user_accounts", ["username"], unique=True)


def downgrade() -> None:
    op.drop_table("user_accounts")

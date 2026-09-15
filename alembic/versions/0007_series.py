"""Series ở Studio: khuôn sản xuất cho một loạt video ngắn cùng chuyên đề.

Không có CHECK cho 25–45 giây hay 9:16: quy tắc sống ở entity ``Series`` và mapper
kiểm lại khi đọc, nên một dòng sửa tay sai sẽ nổ lúc đọc chứ không lọt qua (D20).
Viết cùng quy tắc ở hai nơi là mời chúng lệch nhau.

Revision ID: 0007_series
Revises: 0006_output_aspect_ratio
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_series"
down_revision = "0006_output_aspect_ratio"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "series",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("pillar", sa.Text(), nullable=False),
        sa.Column("hook_templates", postgresql.JSONB(), nullable=False),
        sa.Column(
            "kept_terms", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("target_sec", sa.Numeric(6, 2), nullable=False),
        sa.Column("output_aspect_ratio", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False, server_default="vi"),
        sa.Column("voice_id", sa.Text(), nullable=True),
        sa.Column("subtitle_font_size", sa.Integer(), nullable=False),
        sa.Column("subtitle_max_chars", sa.Integer(), nullable=False),
        sa.Column("cadence_weekdays", postgresql.JSONB(), nullable=True),
        sa.Column("cadence_time", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "items",
        sa.Column(
            "series_id",
            sa.BigInteger(),
            sa.ForeignKey("series.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_index("items_series_idx", "items", ["series_id"])


def downgrade() -> None:
    op.drop_index("items_series_idx", table_name="items")
    op.drop_column("items", "series_id")
    op.drop_table("series")

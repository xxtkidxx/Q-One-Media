"""Phân biệt transcript đang chờ soát với transcript đã được duyệt.

Revision ID: 0002_transcript_approved_stage
Revises: 0001_baseline
Create Date: 2026-09-14
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002_transcript_approved_stage"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE item_stage ADD VALUE IF NOT EXISTS 'transcript_approved'")
    # PostgreSQL cấm dùng giá trị ENUM vừa thêm trong chính transaction đã thêm nó.
    op.execute("COMMIT")
    op.execute(
        """
        UPDATE items AS i
        SET stage = 'transcript_approved'
        WHERE i.stage = 'transcript_review'
          AND EXISTS (
              SELECT 1 FROM audit_log AS a
              WHERE a.entity = 'item'
                AND a.entity_id = i.id
                AND a.action = 'transcript_approved'
          )
        """
    )
    op.execute(
        """
        UPDATE items AS i
        SET stage = 'failed', stage_error = j.error
        FROM jobs AS j
        WHERE i.stage = 'transcript_approved'
          AND j.item_id = i.id
          AND j.task = 'pick_segment'
          AND j.status = 'failed'
        """
    )


def downgrade() -> None:
    op.execute(
        "UPDATE items SET stage = 'transcript_review' WHERE stage = 'transcript_approved'"
    )
    # PostgreSQL không hỗ trợ xoá một giá trị ENUM an toàn khi còn dependency.

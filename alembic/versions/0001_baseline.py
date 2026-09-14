"""Baseline — toàn bộ schema Giai đoạn 1.

Viết **idempotent** có chủ ý (``IF NOT EXISTS`` + khối ``DO`` cho ENUM), vì
migration này phải chạy được trên hai loại DB:

- DB trống hoàn toàn (máy mới) — nó tạo mọi thứ;
- DB đã được ``docker/postgres/init/01-schema.sql`` cũ tạo — nó không làm gì và
  chỉ đánh dấu revision.

Nhờ vậy không ai phải chạy ``alembic stamp`` bằng tay rồi nhớ là đã stamp chưa.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-09-13
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ENUMS: dict[str, tuple[str, ...]] = {
    "source_platform": ("youtube", "douyin", "bilibili", "tiktok", "facebook", "vimeo", "web"),
    "source_kind": ("channel", "playlist", "creator-page", "website", "rss", "single-url"),
    "content_type": ("video", "article"),
    "license_type": ("vendor-mediakit", "written-permission", "cc-by", "stock", "own"),
    "approval_status": ("pending", "approved", "rejected", "expired"),
    "item_stage": (
        "inbox",
        "license_blocked",
        "downloaded",
        "separated",
        "transcribed",
        "transcript_review",
        "transcript_approved",
        "segment_picked",
        "scripted",
        "voiced",
        "aligned",
        "mixed",
        "rendered",
        "human_review",
        "approved",
        "published",
        "failed",
        "rejected",
    ),
    "publish_platform": ("youtube", "facebook", "tiktok", "linkedin"),
    "publish_status": ("queued", "uploading", "published", "failed", "skipped"),
    "job_status": ("pending", "running", "done", "failed", "cancelled"),
}


def _create_enums() -> None:
    for name, values in ENUMS.items():
        labels = ", ".join(f"'{v}'" for v in values)
        op.execute(
            f"""
            DO $$ BEGIN
                CREATE TYPE {name} AS ENUM ({labels});
            EXCEPTION
                WHEN duplicate_object THEN NULL;
            END $$;
            """
        )


def upgrade() -> None:
    # n8n dùng schema riêng để workflow không lẫn với bảng app
    op.execute("CREATE SCHEMA IF NOT EXISTS n8n")
    _create_enums()

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sources (
            id              BIGSERIAL PRIMARY KEY,
            platform        source_platform NOT NULL,
            kind            source_kind     NOT NULL,
            content_type    content_type    NOT NULL DEFAULT 'video',
            source_url      TEXT            NOT NULL UNIQUE,
            display_name    TEXT,
            external_owner_id TEXT,
            audio_lang      TEXT            NOT NULL DEFAULT 'en',
            has_baked_watermark BOOLEAN     NOT NULL DEFAULT FALSE,
            license_type    license_type,
            evidence_ref    TEXT,
            attribution_text TEXT,
            may_translate       BOOLEAN NOT NULL DEFAULT FALSE,
            may_modify_audio    BOOLEAN NOT NULL DEFAULT FALSE,
            may_subtitle        BOOLEAN NOT NULL DEFAULT FALSE,
            may_republish       BOOLEAN NOT NULL DEFAULT FALSE,
            may_commercial_use  BOOLEAN NOT NULL DEFAULT FALSE,
            topics          TEXT[] NOT NULL DEFAULT '{}',
            status          approval_status NOT NULL DEFAULT 'pending',
            approved_by     TEXT,
            approved_at     TIMESTAMPTZ,
            expires_at      TIMESTAMPTZ,
            notes           TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    # Cột thêm sau khi 01-schema.sql bản đầu đã chạy trên một số máy dev.
    op.execute("ALTER TABLE sources ADD COLUMN IF NOT EXISTS external_owner_id TEXT")
    op.execute(
        """
        COMMENT ON TABLE sources IS
          'Nguồn đã khai báo. Pipeline TỪ CHỐI tải nếu status<>approved. Không thêm đường tắt bỏ qua.'
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            ALTER TABLE sources ADD CONSTRAINT sources_approved_needs_evidence
              CHECK (status <> 'approved'
                     OR (license_type IS NOT NULL AND evidence_ref IS NOT NULL));
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS sources_status_idx   ON sources(status)")
    op.execute("CREATE INDEX IF NOT EXISTS sources_platform_idx ON sources(platform)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            id              BIGSERIAL PRIMARY KEY,
            source_id       BIGINT NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
            item_url        TEXT   NOT NULL UNIQUE,
            external_id     TEXT,
            title_original  TEXT,
            duration_sec    INTEGER,
            aspect_ratio    TEXT,
            stage           item_stage NOT NULL DEFAULT 'inbox',
            stage_error     TEXT,
            path_source     TEXT,
            path_work       TEXT,
            path_output     TEXT,
            segment_start_sec NUMERIC(10,3),
            segment_end_sec   NUMERIC(10,3),
            script_vi         TEXT,
            script_sources    JSONB,
            review_by       TEXT,
            review_at       TIMESTAMPTZ,
            review_notes    TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS items_stage_idx  ON items(stage)")
    op.execute("CREATE INDEX IF NOT EXISTS items_source_idx ON items(source_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS publications (
            id              BIGSERIAL PRIMARY KEY,
            item_id         BIGINT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
            platform        publish_platform NOT NULL,
            status          publish_status   NOT NULL DEFAULT 'queued',
            remote_id       TEXT,
            remote_url      TEXT,
            error           TEXT,
            skipped_reason  TEXT,
            published_at    TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (item_id, platform)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id            BIGSERIAL PRIMARY KEY,
            item_id       BIGINT REFERENCES items(id) ON DELETE CASCADE,
            task          TEXT   NOT NULL,
            status        job_status NOT NULL DEFAULT 'pending',
            priority      SMALLINT NOT NULL DEFAULT 100,
            attempts      SMALLINT NOT NULL DEFAULT 0,
            max_attempts  SMALLINT NOT NULL DEFAULT 3,
            payload       JSONB NOT NULL DEFAULT '{}',
            error         TEXT,
            locked_by     TEXT,
            locked_at     TIMESTAMPTZ,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at   TIMESTAMPTZ
        )
        """
    )
    # Index một phần: worker chỉ tìm việc pending, nên index chỉ chứa đúng phần đó
    op.execute(
        "CREATE INDEX IF NOT EXISTS jobs_pickup_idx ON jobs(status, priority, created_at) "
        "WHERE status = 'pending'"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS glossary (
            id            BIGSERIAL PRIMARY KEY,
            src_lang      TEXT NOT NULL,
            term_src      TEXT NOT NULL,
            term_vi       TEXT NOT NULL,
            domain        TEXT,
            note          TEXT,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (src_lang, term_src)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id          BIGSERIAL PRIMARY KEY,
            entity      TEXT NOT NULL,
            entity_id   BIGINT NOT NULL,
            action      TEXT NOT NULL,
            actor       TEXT,
            detail      JSONB,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS audit_entity_idx ON audit_log(entity, entity_id)")


def downgrade() -> None:
    """Không hỗ trợ hạ baseline.

    Hạ revision này là xoá toàn bộ bảng nguồn và vết duyệt license — dữ liệu
    không sinh lại được và là bằng chứng tuân thủ. Muốn làm lại từ đầu thì xoá
    ``data/{env}/postgres`` một cách có ý thức.
    """
    raise NotImplementedError(
        "không hạ baseline: sẽ mất bảng sources và audit_log. "
        "Muốn DB trống thì xoá data/<env>/postgres bằng tay."
    )

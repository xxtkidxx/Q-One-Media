"""Bảng SQLAlchemy — **bản sao trung thực** của ``docker/postgres/init/01-schema.sql``.

Lớp ở đây là *dòng dữ liệu*, không phải entity. Chúng cố tình không có hành vi
nghiệp vụ nào: entity nằm ở ``src/domain`` và không biết SQLAlchemy tồn tại. Cái
giá phải trả là lớp mapper ở ``mappers.py``; cái được là tầng domain test được
trong vài chục milligiây và không bao giờ bị ORM kéo theo.

Các kiểu ENUM do file SQL khởi tạo tạo ra, nên ở đây ``create_type=False`` —
SQLAlchemy không được tự tạo lại.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.domain.production.value_objects import ItemStage
from src.domain.publishing.value_objects import PublishPlatform, PublishStatus
from src.domain.scheduling.entities import JobStatus
from src.domain.sourcing.value_objects import (
    ApprovalStatus,
    ContentType,
    LicenseType,
    Platform,
    SourceKind,
)


class Base(DeclarativeBase):
    pass


def _enum(py_enum: type, name: str) -> ENUM:
    """Bind vào ENUM đã có trong DB. ``values_callable`` để lưu *giá trị* chứ
    không phải *tên* thành viên — nếu không, ``CREATOR_PAGE`` sẽ được ghi thay
    cho ``creator-page`` và Postgres từ chối."""
    return ENUM(
        py_enum,
        name=name,
        create_type=False,
        values_callable=lambda e: [m.value for m in e],
    )


_TS = TIMESTAMP(timezone=True)


class SourceRow(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    platform: Mapped[Platform] = mapped_column(_enum(Platform, "source_platform"))
    kind: Mapped[SourceKind] = mapped_column(_enum(SourceKind, "source_kind"))
    content_type: Mapped[ContentType] = mapped_column(
        _enum(ContentType, "content_type"), default=ContentType.VIDEO
    )
    source_url: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str | None] = mapped_column(Text, default=None)
    external_owner_id: Mapped[str | None] = mapped_column(Text, default=None)
    audio_lang: Mapped[str] = mapped_column(Text, default="en")
    has_baked_watermark: Mapped[bool] = mapped_column(Boolean, default=False)

    license_type: Mapped[LicenseType | None] = mapped_column(
        _enum(LicenseType, "license_type"), default=None
    )
    evidence_ref: Mapped[str | None] = mapped_column(Text, default=None)
    attribution_text: Mapped[str | None] = mapped_column(Text, default=None)

    may_translate: Mapped[bool] = mapped_column(Boolean, default=False)
    may_modify_audio: Mapped[bool] = mapped_column(Boolean, default=False)
    may_subtitle: Mapped[bool] = mapped_column(Boolean, default=False)
    may_republish: Mapped[bool] = mapped_column(Boolean, default=False)
    may_commercial_use: Mapped[bool] = mapped_column(Boolean, default=False)

    topics: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    status: Mapped[ApprovalStatus] = mapped_column(
        _enum(ApprovalStatus, "approval_status"), default=ApprovalStatus.PENDING
    )
    approved_by: Mapped[str | None] = mapped_column(Text, default=None)
    approved_at: Mapped[datetime | None] = mapped_column(_TS, default=None)
    expires_at: Mapped[datetime | None] = mapped_column(_TS, default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        _TS, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        # Bất biến này được thi hành ở ba nơi cùng lúc — có chủ ý, vì nó là
        # kiểm soát pháp lý: __post_init__ của Source, CHECK trong file SQL, và
        # ở đây để ai đọc ORM cũng thấy.
        CheckConstraint(
            "status <> 'approved' OR (license_type IS NOT NULL AND evidence_ref IS NOT NULL)",
            name="sources_approved_needs_evidence",
        ),
        Index("sources_status_idx", "status"),
        Index("sources_platform_idx", "platform"),
    )


class SeriesRow(Base):
    __tablename__ = "series"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    pillar: Mapped[str] = mapped_column(Text)
    hook_templates: Mapped[Any] = mapped_column(JSONB)
    kept_terms: Mapped[Any] = mapped_column(JSONB, default=list)
    target_sec: Mapped[float] = mapped_column(Numeric(6, 2))
    output_aspect_ratio: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(Text, default="vi")
    voice_id: Mapped[str | None] = mapped_column(Text, default=None)
    subtitle_font_size: Mapped[int] = mapped_column(Integer)
    subtitle_max_chars: Mapped[int] = mapped_column(Integer)
    cadence_weekdays: Mapped[Any | None] = mapped_column(JSONB, default=None)
    cadence_time: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        _TS, server_default=func.now(), onupdate=func.now()
    )


class ItemRow(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sources.id", ondelete="RESTRICT")
    )
    parent_item_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("items.id", ondelete="CASCADE"), default=None
    )
    clip_index: Mapped[int] = mapped_column(Integer, default=1)
    include_attribution: Mapped[bool] = mapped_column(Boolean, default=True)
    voice_id: Mapped[str | None] = mapped_column(Text, default=None)
    series_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("series.id", ondelete="RESTRICT"), default=None
    )
    item_url: Mapped[str] = mapped_column(Text, unique=True)
    external_id: Mapped[str | None] = mapped_column(Text, default=None)
    title_original: Mapped[str | None] = mapped_column(Text, default=None)
    duration_sec: Mapped[int | None] = mapped_column(Integer, default=None)
    aspect_ratio: Mapped[str | None] = mapped_column(Text, default=None)
    output_aspect_ratio: Mapped[str | None] = mapped_column(Text, default=None)

    stage: Mapped[ItemStage] = mapped_column(
        _enum(ItemStage, "item_stage"), default=ItemStage.INBOX
    )
    stage_error: Mapped[str | None] = mapped_column(Text, default=None)

    path_source: Mapped[str | None] = mapped_column(Text, default=None)
    path_work: Mapped[str | None] = mapped_column(Text, default=None)
    path_output: Mapped[str | None] = mapped_column(Text, default=None)

    segment_start_sec: Mapped[float | None] = mapped_column(Numeric(10, 3), default=None)
    segment_end_sec: Mapped[float | None] = mapped_column(Numeric(10, 3), default=None)
    script_vi: Mapped[str | None] = mapped_column(Text, default=None)
    script_sources: Mapped[Any | None] = mapped_column(JSONB, default=None)

    review_by: Mapped[str | None] = mapped_column(Text, default=None)
    review_at: Mapped[datetime | None] = mapped_column(_TS, default=None)
    review_notes: Mapped[str | None] = mapped_column(Text, default=None)

    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        _TS, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("items_stage_idx", "stage"),
        Index("items_source_idx", "source_id"),
        Index("items_series_idx", "series_id"),
    )


class PublicationRow(Base):
    __tablename__ = "publications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("items.id", ondelete="CASCADE"))
    platform: Mapped[PublishPlatform] = mapped_column(_enum(PublishPlatform, "publish_platform"))
    status: Mapped[PublishStatus] = mapped_column(
        _enum(PublishStatus, "publish_status"), default=PublishStatus.QUEUED
    )
    remote_id: Mapped[str | None] = mapped_column(Text, default=None)
    remote_url: Mapped[str | None] = mapped_column(Text, default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    skipped_reason: Mapped[str | None] = mapped_column(Text, default=None)
    published_at: Mapped[datetime | None] = mapped_column(_TS, default=None)
    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now())

    __table_args__ = (UniqueConstraint("item_id", "platform", name="publications_item_platform"),)


class JobRow(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    item_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("items.id", ondelete="CASCADE"), default=None
    )
    task: Mapped[str] = mapped_column(Text)
    status: Mapped[JobStatus] = mapped_column(
        _enum(JobStatus, "job_status"), default=JobStatus.PENDING
    )
    priority: Mapped[int] = mapped_column(SmallInteger, default=100)
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    max_attempts: Mapped[int] = mapped_column(SmallInteger, default=3)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    locked_by: Mapped[str | None] = mapped_column(Text, default=None)
    locked_at: Mapped[datetime | None] = mapped_column(_TS, default=None)
    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(_TS, default=None)


class GlossaryRow(Base):
    __tablename__ = "glossary"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    src_lang: Mapped[str] = mapped_column(Text)
    term_src: Mapped[str] = mapped_column(Text)
    term_vi: Mapped[str] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(Text, default=None)
    note: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now())

    __table_args__ = (UniqueConstraint("src_lang", "term_src", name="glossary_lang_term"),)


class AuditLogRow(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entity: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(Text)
    actor: Mapped[str | None] = mapped_column(Text, default=None)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now())

    __table_args__ = (Index("audit_entity_idx", "entity", "entity_id"),)


class UserAccountRow(Base):
    __tablename__ = "user_accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        _TS, server_default=func.now(), onupdate=func.now()
    )


# Dùng cho test tích hợp trên SQLite: ở đó không có ENUM gốc nên phải map sang
# VARCHAR. Chỉ ảnh hưởng test, không ảnh hưởng production.
STRING_ENUM_FALLBACK = String(64)

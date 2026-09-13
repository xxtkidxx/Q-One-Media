"""DTO của HTTP. Tách khỏi entity domain có chủ ý.

Nếu dùng entity làm schema thì hình dạng API bị khoá vào hình dạng model nghiệp
vụ, và mỗi lần đổi nội bộ là một lần đổi hợp đồng với n8n và người dùng.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.domain.production.entities import Item
from src.domain.sourcing.entities import Source
from src.domain.sourcing.value_objects import ContentType, LicenseType, Platform, SourceKind


class DeclareSourceIn(BaseModel):
    url: str
    platform: Platform
    kind: SourceKind
    content_type: ContentType = ContentType.VIDEO
    display_name: str | None = None
    audio_lang: str = "en"
    external_owner_id: str | None = Field(
        default=None,
        description=(
            "Id chủ sở hữu phía nền tảng (channel id YouTube, sec_uid Douyin, page id "
            "Facebook). Bắt buộc với nguồn dạng bao: duyệt một kênh không mở quyền cho "
            "cả nền tảng."
        ),
    )
    has_baked_watermark: bool = False
    topics: list[str] = Field(default_factory=list)
    notes: str | None = None


class ApproveSourceIn(BaseModel):
    actor: str = Field(description="Ai duyệt — vào audit_log, không để trống")
    license_type: LicenseType
    evidence_ref: str = Field(
        description="Link điều khoản media kit, file email đồng ý, hoặc số hợp đồng"
    )
    attribution_text: str | None = None
    may_translate: bool = False
    may_modify_audio: bool = Field(
        default=False, description="Bắt buộc TRUE để lồng tiếng. Quyền dùng lại không suy ra quyền này"
    )
    may_subtitle: bool = False
    may_republish: bool = False
    may_commercial_use: bool = False
    expires_at: datetime | None = None


class RejectIn(BaseModel):
    actor: str
    reason: str


class ReviewDecisionIn(BaseModel):
    actor: str
    notes: str | None = None


class LicenseScopeOut(BaseModel):
    may_translate: bool
    may_modify_audio: bool
    may_subtitle: bool
    may_republish: bool
    may_commercial_use: bool


class SourceOut(BaseModel):
    id: int
    url: str
    platform: Platform
    kind: SourceKind
    content_type: ContentType
    display_name: str | None
    audio_lang: str
    external_owner_id: str | None
    has_baked_watermark: bool
    status: str
    license_type: LicenseType | None
    evidence_ref: str | None
    attribution_text: str | None
    scope: LicenseScopeOut
    approved_by: str | None
    approved_at: datetime | None
    expires_at: datetime | None
    topics: list[str]
    ownership_is_verifiable: bool
    expected_review_minutes: tuple[int, int]

    @classmethod
    def of(cls, s: Source) -> SourceOut:
        return cls(
            id=s.id or 0,
            url=s.url.value,
            platform=s.platform,
            kind=s.kind,
            content_type=s.content_type,
            display_name=s.display_name,
            audio_lang=s.audio_lang.code,
            external_owner_id=s.external_owner_id,
            has_baked_watermark=s.has_baked_watermark,
            status=str(s.status),
            license_type=s.evidence.license_type if s.evidence else None,
            evidence_ref=s.evidence.evidence_ref if s.evidence else None,
            attribution_text=s.evidence.attribution_text if s.evidence else None,
            scope=LicenseScopeOut(
                may_translate=s.scope.may_translate,
                may_modify_audio=s.scope.may_modify_audio,
                may_subtitle=s.scope.may_subtitle,
                may_republish=s.scope.may_republish,
                may_commercial_use=s.scope.may_commercial_use,
            ),
            approved_by=s.approved_by,
            approved_at=s.approved_at,
            expires_at=s.expires_at,
            topics=list(s.topics),
            ownership_is_verifiable=s.ownership_is_verifiable,
            expected_review_minutes=s.expected_review_minutes,
        )


class SubmitUrlIn(BaseModel):
    url: str
    actor: str = "api"


class ItemOut(BaseModel):
    id: int
    source_id: int
    url: str
    stage: str
    stage_error: str | None
    title_original: str | None
    duration_sec: int | None
    aspect_ratio: str | None
    needs_reframe: bool
    reframe_mode: str | None
    segment_start_sec: float | None
    segment_end_sec: float | None
    review_by: str | None
    review_at: datetime | None

    @classmethod
    def of(cls, i: Item) -> ItemOut:
        return cls(
            id=i.id or 0,
            source_id=i.source_id,
            url=i.url.value,
            stage=str(i.stage),
            stage_error=i.stage_error,
            title_original=i.title_original,
            duration_sec=i.duration_sec,
            aspect_ratio=str(i.aspect_ratio) if i.aspect_ratio else None,
            needs_reframe=i.needs_reframe,
            reframe_mode=str(i.reframe_mode) if i.reframe_mode else None,
            segment_start_sec=i.segment.start_sec if i.segment else None,
            segment_end_sec=i.segment.end_sec if i.segment else None,
            review_by=i.review_by,
            review_at=i.review_at,
        )


class SubmitUrlOut(BaseModel):
    item: ItemOut
    accepted: bool
    job_id: int | None
    reason: str | None = None


class ReviewQueueItemOut(BaseModel):
    item: ItemOut
    expected_review_minutes: tuple[int, int]


class ErrorOut(BaseModel):
    error: str
    kind: str
    retryable: bool = False

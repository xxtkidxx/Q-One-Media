"""Chuyển đổi hai chiều giữa dòng dữ liệu và entity.

Đây là chỗ duy nhất biết cả hai thế giới. Viết tay thay vì để ORM map thẳng vào
entity, vì entity có value object (``SourceUrl``, ``LicenseScope``,
``LicenseEvidence``) tự kiểm bất biến trong ``__post_init__`` — và bất biến đó
phải chạy **cả khi** dữ liệu đến từ DB, không chỉ khi đến từ API.

Nhờ vậy một dòng hỏng trong DB (ví dụ ai đó ``UPDATE`` tay đặt status approved
mà không có evidence) sẽ nổ ngay lúc đọc, chứ không lẳng lặng đi qua gate.
"""

from __future__ import annotations

from src.domain.production.entities import Item
from src.domain.production.value_objects import (
    AspectRatio,
    ItemStage,
    MediaAsset,
    Segment,
)
from src.domain.publishing.entities import Publication
from src.domain.scheduling.entities import Job, JobTask
from src.domain.sourcing.entities import Source
from src.domain.sourcing.value_objects import (
    Language,
    LicenseEvidence,
    LicenseScope,
    SourceUrl,
)
from src.infrastructure.db.orm import ItemRow, JobRow, PublicationRow, SourceRow

# ---------------- Source ----------------


def source_to_domain(row: SourceRow) -> Source:
    evidence = (
        LicenseEvidence(
            license_type=row.license_type,
            evidence_ref=row.evidence_ref,
            attribution_text=row.attribution_text,
        )
        if row.license_type is not None and row.evidence_ref is not None
        else None
    )
    return Source(
        id=row.id,
        platform=row.platform,
        kind=row.kind,
        url=SourceUrl(row.source_url),
        content_type=row.content_type,
        display_name=row.display_name,
        audio_lang=Language(row.audio_lang),
        external_owner_id=row.external_owner_id,
        has_baked_watermark=row.has_baked_watermark,
        status=row.status,
        evidence=evidence,
        scope=LicenseScope(
            may_translate=row.may_translate,
            may_modify_audio=row.may_modify_audio,
            may_subtitle=row.may_subtitle,
            may_republish=row.may_republish,
            may_commercial_use=row.may_commercial_use,
        ),
        approved_by=row.approved_by,
        approved_at=row.approved_at,
        expires_at=row.expires_at,
        topics=tuple(row.topics or ()),
        notes=row.notes,
    )


def source_apply(row: SourceRow, source: Source) -> SourceRow:
    row.platform = source.platform
    row.kind = source.kind
    row.source_url = source.url.value
    row.content_type = source.content_type
    row.display_name = source.display_name
    row.audio_lang = source.audio_lang.code
    row.external_owner_id = source.external_owner_id
    row.has_baked_watermark = source.has_baked_watermark
    row.license_type = source.evidence.license_type if source.evidence else None
    row.evidence_ref = source.evidence.evidence_ref if source.evidence else None
    row.attribution_text = source.evidence.attribution_text if source.evidence else None
    row.may_translate = source.scope.may_translate
    row.may_modify_audio = source.scope.may_modify_audio
    row.may_subtitle = source.scope.may_subtitle
    row.may_republish = source.scope.may_republish
    row.may_commercial_use = source.scope.may_commercial_use
    row.topics = list(source.topics)
    row.status = source.status
    row.approved_by = source.approved_by
    row.approved_at = source.approved_at
    row.expires_at = source.expires_at
    row.notes = source.notes
    return row


def source_to_row(source: Source) -> SourceRow:
    return source_apply(SourceRow(), source)


# ---------------- Item ----------------


def item_to_domain(row: ItemRow) -> Item:
    segment = (
        Segment(float(row.segment_start_sec), float(row.segment_end_sec))
        if row.segment_start_sec is not None and row.segment_end_sec is not None
        else None
    )
    item = Item(
        id=row.id,
        source_id=row.source_id,
        url=SourceUrl(row.item_url),
        external_id=row.external_id,
        title_original=row.title_original,
        duration_sec=row.duration_sec,
        aspect_ratio=AspectRatio.parse(row.aspect_ratio) if row.aspect_ratio else None,
        stage=row.stage,
        stage_error=row.stage_error,
        path_source=MediaAsset(row.path_source) if row.path_source else None,
        path_work=MediaAsset(row.path_work) if row.path_work else None,
        path_output=MediaAsset(row.path_output) if row.path_output else None,
        segment=segment,
        script_vi=row.script_vi,
        script_sources=tuple(row.script_sources or ()),
        parent_item_id=row.parent_item_id,
        clip_index=row.clip_index,
        include_attribution=row.include_attribution,
        voice_id=row.voice_id,
        review_by=row.review_by,
        review_at=row.review_at,
        review_notes=row.review_notes,
    )
    # Item đã qua bước viết kịch bản thì clearance lồng tiếng từng được cấp;
    # khôi phục cờ để việc chạy lại từ giữa pipeline không bị chặn oan.
    if row.script_vi and row.stage not in (ItemStage.INBOX, ItemStage.LICENSE_BLOCKED):
        item._dubbing_cleared = True
    return item


def item_apply(row: ItemRow, item: Item) -> ItemRow:
    row.source_id = item.source_id
    row.item_url = item.url.value
    row.external_id = item.external_id
    row.title_original = item.title_original
    row.duration_sec = item.duration_sec
    row.aspect_ratio = str(item.aspect_ratio) if item.aspect_ratio else None
    row.stage = item.stage
    row.stage_error = item.stage_error
    row.path_source = item.path_source.relative_path if item.path_source else None
    row.path_work = item.path_work.relative_path if item.path_work else None
    row.path_output = item.path_output.relative_path if item.path_output else None
    row.segment_start_sec = item.segment.start_sec if item.segment else None
    row.segment_end_sec = item.segment.end_sec if item.segment else None
    row.script_vi = item.script_vi
    row.script_sources = list(item.script_sources) or None
    row.parent_item_id = item.parent_item_id
    row.clip_index = item.clip_index
    row.include_attribution = item.include_attribution
    row.voice_id = item.voice_id
    row.review_by = item.review_by
    row.review_at = item.review_at
    row.review_notes = item.review_notes
    return row


def item_to_row(item: Item) -> ItemRow:
    return item_apply(ItemRow(), item)


# ---------------- Publication ----------------


def publication_to_domain(row: PublicationRow) -> Publication:
    return Publication(
        id=row.id,
        item_id=row.item_id,
        platform=row.platform,
        status=row.status,
        remote_id=row.remote_id,
        remote_url=row.remote_url,
        error=row.error,
        skipped_reason=row.skipped_reason,
        published_at=row.published_at,
    )


def publication_apply(row: PublicationRow, pub: Publication) -> PublicationRow:
    row.item_id = pub.item_id
    row.platform = pub.platform
    row.status = pub.status
    row.remote_id = pub.remote_id
    row.remote_url = pub.remote_url
    row.error = pub.error
    row.skipped_reason = pub.skipped_reason
    row.published_at = pub.published_at
    return row


def publication_to_row(pub: Publication) -> PublicationRow:
    return publication_apply(PublicationRow(), pub)


# ---------------- Job ----------------


def job_to_domain(row: JobRow) -> Job:
    return Job(
        id=row.id,
        item_id=row.item_id,
        task=JobTask(row.task),
        status=row.status,
        priority=row.priority,
        attempts=row.attempts,
        max_attempts=row.max_attempts,
        payload=dict(row.payload or {}),
        error=row.error,
        locked_by=row.locked_by,
        locked_at=row.locked_at,
        finished_at=row.finished_at,
    )


def job_apply(row: JobRow, job: Job) -> JobRow:
    row.item_id = job.item_id
    row.task = str(job.task)
    row.status = job.status
    row.priority = job.priority
    row.attempts = job.attempts
    row.max_attempts = job.max_attempts
    row.payload = dict(job.payload)
    row.error = job.error
    row.locked_by = job.locked_by
    row.locked_at = job.locked_at
    row.finished_at = job.finished_at
    return row


def job_to_row(job: Job) -> JobRow:
    return job_apply(JobRow(), job)

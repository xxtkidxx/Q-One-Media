"""Series ở Studio — tạo một khuôn sản xuất rồi sinh hàng loạt bản nháp kịch bản từ nó.

Bản nháp dừng ở ``scripted`` và **chưa** xếp việc lồng tiếng: kênh kỹ thuật sống bằng
độ đúng thuật ngữ, nên kỹ sư đọc kịch bản trước khi tốn công lồng tiếng và dựng.
``start_series_video`` là bước do người bấm.

Mọi ràng buộc của Series (pillar, 25–45 giây, 9:16, mẫu hook) nằm trong entity; use
case chỉ điều phối và ghi audit.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.application.ports import Clock, PromptScriptWriter, UnitOfWork
from src.application.use_cases.author_video import ItemNotFound, create_video_from_prompt
from src.domain.authoring.series import PostingCadence, Series, SubtitlePreset
from src.domain.errors import DomainError, InvariantViolation
from src.domain.production.entities import Item
from src.domain.production.value_objects import AspectRatio, ItemStage
from src.domain.scheduling.entities import Job, JobTask

# Mỗi đề tài là một lần gọi model chạy ngay trong request web — trần này giữ request
# trong thời gian chờ được.
MAX_TOPICS_PER_BATCH = 10


class SeriesNotFound(DomainError):
    pass


@dataclass(frozen=True, slots=True)
class SeriesDraftOutcome:
    created: tuple[Item, ...]
    failed: tuple[tuple[str, str], ...]  # (đề tài, lỗi)


def create_series(
    *,
    name: str,
    pillar: str,
    hook_templates: list[str],
    target_sec: float,
    kept_terms: list[str],
    output_aspect_ratio: AspectRatio,
    voice_id: str | None,
    subtitle: SubtitlePreset,
    cadence: PostingCadence | None,
    uow: UnitOfWork,
    actor: str,
) -> Series:
    series = Series(
        name=name,
        pillar=pillar,
        hook_templates=tuple(hook_templates),
        target_sec=target_sec,
        kept_terms=tuple(kept_terms),
        output_aspect_ratio=output_aspect_ratio,
        voice_id=voice_id,
        subtitle=subtitle,
        cadence=cadence,
    )
    with uow:
        uow.series.add(series)
        assert series.id is not None
        uow.audit.record(
            entity="series",
            entity_id=series.id,
            action="series_created",
            actor=actor,
            detail={
                "name": series.name,
                "pillar": series.pillar,
                "hooks": len(series.hook_templates),
                "target_sec": series.target_sec,
            },
        )
        uow.commit()
    return series


def draft_from_series(
    series_id: int,
    *,
    topics: list[str],
    author: str,
    writer: PromptScriptWriter,
    speech_rate: float | None,
    glossary: dict[str, str],
    media_root: Path,
    uow: UnitOfWork,
    clock: Clock,
) -> SeriesDraftOutcome:
    """Mỗi đề tài → một bản nháp kế thừa pillar, hook, thuật ngữ, độ dài, khung, giọng."""
    from src.application.use_cases.synthesize_voice import SpeechRateUnknown

    clean_topics = list(dict.fromkeys(topic.strip() for topic in topics if topic.strip()))
    if not clean_topics:
        raise InvariantViolation("phải nhập ít nhất một đề tài")
    if len(clean_topics) > MAX_TOPICS_PER_BATCH:
        raise InvariantViolation(
            f"mỗi lần sinh tối đa {MAX_TOPICS_PER_BATCH} đề tài, nhận được {len(clean_topics)}"
        )
    if speech_rate is None:
        raise SpeechRateUnknown(
            "chưa đo tốc độ đọc — không lập được ngân sách âm tiết (G0.7). "
            "Đặt TTS_SYLLABLES_PER_SEC."
        )

    with uow:
        series = uow.series.get(series_id)
        if series is None:
            raise SeriesNotFound(f"không có series #{series_id}")
        # Hook xoay vòng tiếp từ video con cuối, không quay lại hook đầu mỗi lần sinh.
        position = len(uow.items.list_by_series(series_id))

    created: list[Item] = []
    failed: list[tuple[str, str]] = []
    for topic in clean_topics:
        hook = series.hook_for(position)
        try:
            result = create_video_from_prompt(
                brief=series.brief_for(topic, position=position, speech_rate=speech_rate),
                title=topic,
                target_sec=series.target_sec,
                author=author,
                writer=writer,
                speech_rate=speech_rate,
                glossary=series.glossary_over(glossary),
                media_root=media_root,
                uow=uow,
                clock=clock,
                voice_id=series.voice_id,
                output_aspect_ratio=series.output_aspect_ratio,
                series_id=series_id,
                start_production=False,
            )
        except (DomainError, RuntimeError) as exc:
            # Model quá tải ở một đề tài không được kéo đổ các đề tài còn lại.
            failed.append((topic, str(exc)))
            continue
        assert result.item.id is not None
        with uow:
            uow.audit.record(
                entity="item",
                entity_id=result.item.id,
                action="series_draft_created",
                actor=author,
                detail={
                    "series_id": series_id,
                    "position": position,
                    "pillar": series.pillar,
                    "hook": hook,
                },
            )
            uow.commit()
        created.append(result.item)
        position += 1
    return SeriesDraftOutcome(created=tuple(created), failed=tuple(failed))


def start_series_video(item_id: int, *, series_id: int, uow: UnitOfWork, actor: str) -> Item:
    """Người đã đọc bản nháp → xếp việc lồng tiếng; phần sau đi đúng đường Studio."""
    with uow:
        item = uow.items.get(item_id)
        if item is None or item.series_id != series_id:
            raise ItemNotFound(f"series #{series_id} không có video #{item_id}")
        if item.stage is not ItemStage.SCRIPTED:
            raise InvariantViolation(
                f"video #{item_id} đang ở {item.stage} — chỉ bản nháp kịch bản mới đưa vào "
                "sản xuất được"
            )
        uow.jobs.enqueue(Job(task=JobTask.SYNTHESIZE, item_id=item_id))
        uow.audit.record(
            entity="item",
            entity_id=item_id,
            action="series_production_started",
            actor=actor,
            detail={"series_id": series_id},
        )
        uow.commit()
    return item

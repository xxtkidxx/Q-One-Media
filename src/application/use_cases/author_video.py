"""Giai đoạn 2 — video dựng từ đề bài nhập vào, không dùng thước phim của ai.

Đầu vào là một đề bài do người dùng nhập ("làm video 60 giây giải thích Cpk cho
quản lý nhà máy"), không phải một bài của người khác. LLM viết kịch bản tiếng
Việt trong ngân sách âm tiết, rồi phần sau của pipeline dùng lại **nguyên vẹn**
đường đã có ở Giai đoạn 1: lồng tiếng → gióng phụ đề → dựng → người duyệt →
publish. Chỗ duy nhất khác là bước dựng: không có video nguồn để cắt, nên hình
đến từ ảnh/video người dùng đưa vào, biểu đồ từ số liệu thật, hoặc AI cho bối cảnh.

Vì sao không có license gate ở đây: gate của Giai đoạn 1 tồn tại vì ta dùng lại
tác phẩm của người khác. Ở đây tác giả là NMI. Thứ thay thế là **trách nhiệm có
tên** — ``author`` bắt buộc và đi vào audit, y như gate duyệt luôn đòi tên người
duyệt.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.application.ports import Clock, PromptScriptWriter, UnitOfWork
from src.domain.authoring.visuals import Shot, ShotKind, VisualPlan, default_plan
from src.domain.errors import DomainError, InvariantViolation
from src.domain.production.entities import Item
from src.domain.production.value_objects import (
    HARD_SEGMENT_MAX_SEC,
    HARD_SEGMENT_MIN_SEC,
    SpeechRate,
    SyllableBudget,
)
from src.domain.scheduling.entities import Job, JobTask
from src.domain.sourcing.entities import Source
from src.domain.sourcing.value_objects import (
    ContentType,
    Language,
    LicenseEvidence,
    LicenseScope,
    LicenseType,
    Platform,
    SourceKind,
    SourceUrl,
)
from src.shared.paths import MediaPaths

VISUAL_PLAN_FILE = "visual_plan.json"
STUDIO_SOURCE_URL = "https://nmi.vn/qone/studio"


class ItemNotFound(DomainError):
    pass


@dataclass(frozen=True, slots=True)
class AuthoredVideo:
    item: Item
    plan: VisualPlan
    max_syllables: int


def ensure_studio_source(*, uow: UnitOfWork, clock: Clock, actor: str) -> Source:
    """Nguồn nội bộ cho nội dung tạo tại Studio.

    Item nào cũng trỏ về một ``source`` — đó là nơi giữ hồ sơ quyền. Nội dung tạo
    ở đây vẫn cần một hồ sơ như vậy, ghi đúng sự thật: license ``own``,
    bằng chứng là tên người tạo. Tạo một lần rồi dùng lại.
    """
    url = SourceUrl(STUDIO_SOURCE_URL)
    with uow:
        existing = uow.sources.get_by_url(url)
        if existing is not None:
            return existing
        source = uow.sources.add(
            Source(
                platform=Platform.WEB,
                kind=SourceKind.WEBSITE,
                url=url,
                content_type=ContentType.ARTICLE,
                display_name="Q One Studio",
                audio_lang=Language("vi"),
                external_owner_id="nmi.vn",
            )
        )
        source.approve(
            by=actor,
            evidence=LicenseEvidence(
                license_type=LicenseType.OWN,
                evidence_ref=f"Nội dung tạo tại Q One Studio bởi {actor}",
            ),
            scope=LicenseScope(
                may_translate=True,
                may_modify_audio=True,
                may_subtitle=True,
                may_republish=True,
                may_commercial_use=True,
            ),
            at=clock.now(),
        )
        uow.sources.update(source)
        assert source.id is not None
        uow.audit.record(
            entity="source", entity_id=source.id, action="studio_source_created", actor=actor
        )
        uow.commit()
    return source


def create_video_from_prompt(
    *,
    brief: str,
    title: str,
    target_sec: float,
    author: str,
    writer: PromptScriptWriter,
    speech_rate: float | None,
    glossary: dict[str, str],
    media_root: Path,
    uow: UnitOfWork,
    clock: Clock,
    plan: VisualPlan | None = None,
) -> AuthoredVideo:
    """Đề bài của người dùng → kịch bản tiếng Việt → item sẵn sàng lồng tiếng."""
    from src.application.use_cases.synthesize_voice import SpeechRateUnknown

    clean_author = author.strip()
    if not clean_author:
        raise InvariantViolation("phải ghi tên người tạo nội dung")
    if not brief.strip():
        raise InvariantViolation("đề bài rỗng — không có gì để viết")
    if not HARD_SEGMENT_MIN_SEC <= target_sec <= HARD_SEGMENT_MAX_SEC:
        raise InvariantViolation(
            f"thời lượng {target_sec}s ngoài biên "
            f"{HARD_SEGMENT_MIN_SEC}–{HARD_SEGMENT_MAX_SEC}s"
        )
    if speech_rate is None:
        raise SpeechRateUnknown(
            "chưa đo tốc độ đọc — không lập được ngân sách âm tiết (G0.7). "
            "Đặt TTS_SYLLABLES_PER_SEC."
        )

    source = ensure_studio_source(uow=uow, clock=clock, actor=clean_author)
    budget = SyllableBudget(window_sec=target_sec, rate=SpeechRate(speech_rate))
    script = writer.write_from_prompt(
        brief=brief.strip(),
        title=title.strip(),
        max_syllables=budget.max_syllables,
        glossary=glossary,
    )

    with uow:
        assert source.id is not None
        item = Item.from_prompt(
            url=SourceUrl(f"{STUDIO_SOURCE_URL}#{clock.now().timestamp():.0f}"),
            source_id=source.id,
            script_vi=script,
            title=title.strip() or brief.strip()[:80],
            target_sec=target_sec,
            author=clean_author,
        )
        uow.items.add(item)
        assert item.id is not None
        uow.jobs.enqueue(Job(task=JobTask.SYNTHESIZE, item_id=item.id))
        uow.audit.record(
            entity="item",
            entity_id=item.id,
            action="authored_from_prompt",
            actor=clean_author,
            detail={"brief": brief.strip()[:500], "target_sec": target_sec},
        )
        uow.commit()

    final_plan = (plan or default_plan(title=title.strip() or "Q One", target_sec=target_sec))
    save_visual_plan(media_root, item.id or 0, final_plan)
    return AuthoredVideo(item=item, plan=final_plan, max_syllables=budget.max_syllables)


# ---------------- Kịch bản hình ----------------


def plan_dir(media_root: Path, item_id: int) -> Path:
    return MediaPaths(media_root).item_work_dir(item_id)


def save_visual_plan(media_root: Path, item_id: int, plan: VisualPlan) -> Path:
    directory = plan_dir(media_root, item_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / VISUAL_PLAN_FILE
    path.write_text(
        json.dumps(
            [
                {
                    "kind": shot.kind.value,
                    "seconds": shot.seconds,
                    "caption": shot.caption,
                    "asset": shot.asset,
                    "prompt": shot.prompt,
                    "data": [list(pair) for pair in shot.data],
                }
                for shot in plan.shots
            ],
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    return path


def load_visual_plan(media_root: Path, item_id: int) -> VisualPlan | None:
    path = plan_dir(media_root, item_id) / VISUAL_PLAN_FILE
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return VisualPlan(
        tuple(
            Shot(
                kind=ShotKind(entry["kind"]),
                seconds=float(entry["seconds"]),
                caption=entry.get("caption", ""),
                asset=entry.get("asset"),
                prompt=entry.get("prompt", ""),
                data=tuple((str(k), float(v)) for k, v in entry.get("data", [])),
            )
            for entry in raw
        )
    )


def add_shot(
    item_id: int,
    *,
    shot: Shot,
    media_root: Path,
    uow: UnitOfWork,
    actor: str,
    clock: Clock | None = None,
) -> VisualPlan:
    """Thêm một cảnh (ảnh/video đã upload, biểu đồ, hoặc prompt cho AI)."""
    with uow:
        item = uow.items.get(item_id)
        if item is None:
            raise ItemNotFound(f"không có item #{item_id}")
    existing = load_visual_plan(media_root, item_id)
    shots = list(existing.shots) if existing else []
    # Kịch bản mặc định chỉ là thẻ thương hiệu giữ chỗ; cảnh thật đầu tiên thay nó.
    if shots and all(s.kind is ShotKind.BRAND_CARD for s in shots):
        shots = []
    shots.append(shot)
    plan = VisualPlan(tuple(shots))
    save_visual_plan(media_root, item_id, plan)
    with uow:
        uow.audit.record(
            entity="item",
            entity_id=item_id,
            action="visual_shot_added",
            actor=actor,
            detail={"kind": shot.kind.value, "seconds": shot.seconds},
        )
        uow.commit()
    return plan


def remove_shot(
    item_id: int, *, index: int, media_root: Path, uow: UnitOfWork, actor: str
) -> VisualPlan:
    plan = load_visual_plan(media_root, item_id)
    if plan is None or not 0 <= index < len(plan.shots):
        raise InvariantViolation(f"không có cảnh số {index + 1}")
    shots = [shot for position, shot in enumerate(plan.shots) if position != index]
    new_plan = VisualPlan(tuple(shots)) if shots else default_plan(title="Q One", target_sec=30)
    save_visual_plan(media_root, item_id, new_plan)
    with uow:
        uow.audit.record(
            entity="item", entity_id=item_id, action="visual_shot_removed", actor=actor,
            detail={"index": index},
        )
        uow.commit()
    return new_plan


def resolve_generated_shots(
    item_id: int,
    *,
    generator,
    media_root: Path,
    uow: UnitOfWork,
    actor: str = "worker",
) -> VisualPlan:
    """Sinh ảnh cho các cảnh AI còn thiếu file.

    Nhà cung cấp chưa cấu hình thì **không** phải lỗi: cảnh đó rơi về thẻ thương
    hiệu mang đúng caption. Một video thiếu ảnh minh hoạ vẫn dùng được; một video
    dừng giữa chừng vì thiếu API key thì không.
    """
    plan = load_visual_plan(media_root, item_id)
    if plan is None:
        return default_plan(title="Q One", target_sec=30)
    resolved: list[Shot] = []
    fallbacks = 0
    for index, shot in enumerate(plan.shots):
        if shot.kind is not ShotKind.GENERATED or shot.asset:
            resolved.append(shot)
            continue
        try:
            asset = generator.generate(
                prompt=shot.prompt, out_dir=plan_dir(media_root, item_id), name=f"shot-{index}"
            )
        except Exception:
            asset = None
        if asset:
            resolved.append(shot.with_asset(asset))
        else:
            fallbacks += 1
            resolved.append(
                Shot(
                    kind=ShotKind.BRAND_CARD,
                    seconds=shot.seconds,
                    caption=shot.caption or shot.prompt,
                )
            )
    plan = VisualPlan(tuple(resolved))
    save_visual_plan(media_root, item_id, plan)
    if fallbacks:
        with uow:
            uow.audit.record(
                entity="item", entity_id=item_id, action="visual_generation_fallback",
                actor=actor, detail={"shots": fallbacks},
            )
            uow.commit()
    return plan


def timestamped_name(prefix: str, when: datetime) -> str:
    return f"{prefix}-{when.strftime('%Y%m%d-%H%M%S')}"

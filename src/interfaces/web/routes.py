"""Mặt tiền web nội bộ — server-rendered, không SPA.

Vì sao tồn tại: gate duyệt của người là **bắt buộc** ở Giai đoạn 1 và tốn 20–35
phút/video (nguồn en) hoặc 35–55 phút (nguồn zh). Người duyệt là quản lý nội
dung, không phải dev — không thể bắt họ bấm ``POST /items/12/approve`` trong
Swagger. Mọi video đều đi qua đúng cửa đó, nên cửa đó phải dùng được.

Vì sao Jinja2 server-rendered chứ không React (D21): 2–5 người dùng nội bộ; SPA
đòi npm + một Dockerfile + một container nữa mà không mua được gì; phần khó nhất
là phát video, và HTML thuần làm việc đó tốt nhất.

Kế hoạch ban đầu ghi "Jinja2 + HTMX", nhưng khi viết thì form POST + redirect đủ
cho mọi tương tác ở đây, nên **không có JavaScript nào**. Hệ quả có giá trị thật
cho một công cụ on-prem: trang chạy được khi nhà máy không có internet ra ngoài.

**Tầng này không chứa quy tắc nghiệp vụ nào.** Nó gọi đúng use case mà API đã
gọi. Đó là lý do thêm một mặt tiền không thêm một chỗ nào để license gate bị đi
vòng.
"""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, or_, select

from src.application.use_cases.author_series import (
    MAX_TOPICS_PER_BATCH,
    create_series,
    draft_from_series,
    start_series_video,
)
from src.application.use_cases.author_video import (
    STUDIO_SOURCE_URL,
    add_shot,
    create_video_from_prompt,
    load_visual_plan,
    queue_studio_recompose,
    remove_shot,
)
from src.application.use_cases.manage_sources import (
    ApproveSourceCommand,
    DeclareSourceCommand,
    SourceAlreadyDeclared,
    approve_source,
    declare_source,
)
from src.application.use_cases.review_item import (
    ItemNotFound,
    approve_item,
    approve_transcript,
    list_review_queue,
    queue_publish,
    reject_item,
    send_back_for_rewrite,
)
from src.application.use_cases.submit_url import (
    ItemAlreadyExists,
    SourceNotDeclared,
    submit_url,
)
from src.application.use_cases.upload_video import register_uploaded_video
from src.application.use_cases.write_script import (
    create_manual_clips,
    edit_transcript,
    load_glossary,
    load_transcript,
)
from src.domain.authoring.series import (
    DEFAULT_SUBTITLE_FONT_SIZE,
    DEFAULT_SUBTITLE_MAX_CHARS,
    MAX_SERIES_SEC,
    MIN_SERIES_SEC,
    WEEKDAY_LABELS,
    PostingCadence,
    SubtitlePreset,
)
from src.domain.authoring.visuals import Shot, ShotKind
from src.domain.errors import DomainError
from src.domain.production.value_objects import (
    RECOMMENDED_SEGMENT_MAX_SEC,
    RECOMMENDED_SEGMENT_MIN_SEC,
    AspectRatio,
    ItemStage,
    MediaAsset,
)
from src.domain.sourcing.value_objects import (
    ApprovalStatus,
    ContentType,
    LicenseType,
    Platform,
    SourceKind,
    SourceUrl,
)
from src.infrastructure.clock import SystemClock
from src.infrastructure.db import mappers
from src.infrastructure.db.orm import AuditLogRow, ItemRow, JobRow
from src.infrastructure.db.uow import SqlUnitOfWork
from src.infrastructure.llm.registry import build_script_writer
from src.infrastructure.media import ffmpeg
from src.infrastructure.tts.catalog import default_voice_id, label_for, list_voices
from src.interfaces.api.deps import get_clock, get_config, get_uow
from src.shared.config import Settings

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# File đính kèm không bắt buộc: một cảnh có thể là prompt AI hoặc số liệu biểu đồ
# thay vì file. Khai một lần ở đây vì gọi ``File()`` trong default là bẫy dùng chung
# giữa các lần gọi.
OPTIONAL_FILE = File()
OPTIONAL_FILES = File()

router = APIRouter(tags=["web"], include_in_schema=False)

Uow = Annotated[SqlUnitOfWork, Depends(get_uow)]
Clock = Annotated[SystemClock, Depends(get_clock)]
Config = Annotated[Settings, Depends(get_config)]


def _actor(request: Request) -> str:
    """Danh tính thao tác luôn đến từ session đã xác thực, không nhận từ form."""
    return request.state.user.username

# Thứ tự các bước để hiện trên dashboard — theo đúng dòng chảy pipeline, không
# theo thứ tự chữ cái, để người xem đọc được nghẽn đang ở đâu.
PIPELINE_ORDER = [
    ItemStage.INBOX,
    ItemStage.DOWNLOADED,
    ItemStage.SEPARATED,
    ItemStage.TRANSCRIBED,
    ItemStage.TRANSCRIPT_REVIEW,
    ItemStage.TRANSCRIPT_APPROVED,
    ItemStage.SEGMENT_PICKED,
    ItemStage.SCRIPTED,
    ItemStage.VOICED,
    ItemStage.ALIGNED,
    ItemStage.MIXED,
    ItemStage.RENDERED,
    ItemStage.HUMAN_REVIEW,
    ItemStage.APPROVED,
    ItemStage.PUBLISHED,
]
BLOCKED_STAGES = [ItemStage.LICENSE_BLOCKED, ItemStage.FAILED, ItemStage.REJECTED]
PIPELINE_PROGRESS = {
    ItemStage.INBOX: 5,
    ItemStage.DOWNLOADED: 15,
    ItemStage.SEPARATED: 25,
    ItemStage.TRANSCRIBED: 35,
    ItemStage.TRANSCRIPT_REVIEW: 40,
    ItemStage.TRANSCRIPT_APPROVED: 45,
    ItemStage.SEGMENT_PICKED: 52,
    ItemStage.SCRIPTED: 62,
    ItemStage.VOICED: 72,
    ItemStage.ALIGNED: 80,
    ItemStage.MIXED: 86,
    ItemStage.RENDERED: 92,
    ItemStage.HUMAN_REVIEW: 95,
    ItemStage.APPROVED: 98,
    ItemStage.PUBLISHED: 100,
}
PIPELINE_LABELS = {
    ItemStage.INBOX: "Đang tải video",
    ItemStage.DOWNLOADED: "Đã tải video",
    ItemStage.SEPARATED: "Đã tách audio",
    ItemStage.TRANSCRIBED: "Đã nhận dạng lời nói",
    ItemStage.TRANSCRIPT_REVIEW: "Soát transcript",
    ItemStage.TRANSCRIPT_APPROVED: "Chọn đoạn",
    ItemStage.SEGMENT_PICKED: "Đã chọn đoạn",
    ItemStage.SCRIPTED: "Đã viết kịch bản",
    ItemStage.VOICED: "Đã tạo giọng Việt",
    ItemStage.ALIGNED: "Đã căn phụ đề",
    ItemStage.MIXED: "Đã trộn âm thanh",
    ItemStage.RENDERED: "Đã dựng video",
    ItemStage.HUMAN_REVIEW: "Duyệt thành phẩm",
    ItemStage.APPROVED: "Đã duyệt",
    ItemStage.PUBLISHED: "Đã xuất bản",
}
JOB_LABELS = {
    "download": "Tải video", "separate": "Tách audio",
    "transcribe": "Nhận dạng lời nói", "pick_segment": "Chọn đoạn",
    "write_script": "Viết kịch bản", "synthesize": "Tạo giọng Việt",
    "align": "Căn phụ đề", "render": "Dựng video",
    "compose": "Dựng video Studio", "publish": "Xuất bản",
}
JOB_TARGET_STAGE = {
    "download": ItemStage.INBOX, "separate": ItemStage.DOWNLOADED,
    "transcribe": ItemStage.SEPARATED, "pick_segment": ItemStage.TRANSCRIPT_APPROVED,
    "write_script": ItemStage.SCRIPTED, "synthesize": ItemStage.VOICED,
    "align": ItemStage.ALIGNED, "render": ItemStage.RENDERED,
    "publish": ItemStage.PUBLISHED,
}


# Nhãn hiển thị của **mọi** trạng thái, gồm cả ba trạng thái ngoài dòng chảy.
# Người duyệt là quản lý nội dung: `transcript_approved` không nói gì với họ, và
# một cái badge ghi mã trong DB làm người đọc phải tự dịch trong đầu mỗi lần.
STAGE_LABELS = dict(PIPELINE_LABELS) | {
    ItemStage.LICENSE_BLOCKED: "Bị chặn vì giấy phép",
    ItemStage.FAILED: "Lỗi — cần xử lý",
    ItemStage.REJECTED: "Đã từ chối",
}
# Việc kế tiếp mà **người** phải làm ở trạng thái đó. Trạng thái không có ở đây
# nghĩa là đang chờ worker, không phải chờ người.
NEXT_HUMAN_ACTION = {
    ItemStage.TRANSCRIPT_REVIEW: ("Soát transcript", "transcript"),
    ItemStage.TRANSCRIPT_APPROVED: ("Chọn đoạn tạo clip", "clip"),
    ItemStage.HUMAN_REVIEW: ("Duyệt thành phẩm", "duyet"),
    ItemStage.APPROVED: ("Xuất bản", "publish"),
}


def _stage_label(stage: ItemStage) -> str:
    return STAGE_LABELS.get(stage, stage.value)


def _progress_detail(stage: ItemStage) -> tuple[int, int, int, str]:
    total = len(PIPELINE_ORDER)
    try:
        step = PIPELINE_ORDER.index(stage) + 1
    except ValueError:
        step = 0
    return step, total, PIPELINE_PROGRESS.get(stage, 0), PIPELINE_LABELS.get(stage, stage.value)


def _workflow(stage: ItemStage) -> list[dict]:
    """Sơ đồ 15 bước, tô theo tiến trình của đúng video hoặc clip đang mở."""
    current_index = PIPELINE_ORDER.index(stage) if stage in PIPELINE_ORDER else -1
    return [
        {
            "index": index + 1,
            "label": PIPELINE_LABELS[step],
            "percent": PIPELINE_PROGRESS[step],
            "state": (
                "done" if index < current_index
                else "current" if index == current_index
                else "pending"
            ),
        }
        for index, step in enumerate(PIPELINE_ORDER)
    ]


def _default_review_tab(item, *, has_clips: bool, created: bool) -> str:
    """Mở sẵn đúng tab của việc đang cần làm, thay vì bắt người dùng đi tìm."""
    if created:
        return "clips"
    if item.stage is ItemStage.TRANSCRIPT_APPROVED and not item.parent_item_id:
        return "clip"
    if has_clips:
        return "clips"
    return "transcript"


def _clip_view(item, source_id: int, settings: Settings) -> dict:
    """Một dòng trong tab “Clip đã tạo” — đủ để mở popup mà không cần gọi lại server."""
    step, total, percent, step_label = _progress_detail(item.stage)
    action = NEXT_HUMAN_ACTION.get(item.stage)
    return {
        "item": item,
        "code": f"#{source_id}-{item.clip_index}" if item.parent_item_id else f"#{source_id}-gốc",
        "stage_label": _stage_label(item.stage),
        "stage_value": item.stage.value,
        "step": step,
        "total": total,
        "percent": percent,
        "step_label": step_label,
        "action_label": action[0] if action else None,
        "action_kind": action[1] if action else None,
        "voice_label": label_for(item.voice_id, settings),
        "video_url": (
            "/media/" + item.path_output.relative_path if item.path_output else None
        ),
    }


def _effective_attribution(text: str, license_type: LicenseType, source) -> str | None:
    """Chuỗi ghi nguồn: người duyệt nhập, hoặc tự sinh khi license bắt buộc.

    Dùng chung cho form duyệt nguồn và form nạp video tạo nguồn mới — hai chỗ sinh
    chuỗi ghi nguồn khác nhau là hai cách tuân thủ license khác nhau.
    """
    clean = text.strip() or None
    if clean or not license_type.requires_attribution:
        return clean
    return f"Nguồn: {source.display_name or source.url.host} · {source.url.value}"


def _review_error(item_id: int, message: str) -> RedirectResponse:
    """Lỗi của một thao tác trên trang review thì ở lại **đúng trang đó**.

    Trang lỗi riêng đẩy người dùng sang URL của POST (``/items/8/clips``) —
    một trang cụt, mất hết ngữ cảnh video và phải bấm back mới làm tiếp được.
    Lỗi ở đây là kết quả nghiệp vụ hợp lệ (đoạn quá dài, thiếu tên người duyệt),
    nên nó thuộc về form vừa bấm, không phải một trang khác.
    """
    return RedirectResponse(
        url=f"/review/{item_id}?error={quote(message)}", status_code=303
    )


def _render(request: Request, template: str, **ctx) -> HTMLResponse:
    """Chữ ký mới của Starlette: request là tham số ĐẦU TIÊN.

    Chữ ký cũ ``TemplateResponse(name, {"request": ...})`` đã deprecated và sẽ bị
    bỏ — gom vào một hàm để lần sau đổi chỉ sửa một chỗ.
    """
    ctx.setdefault("current_user", getattr(request.state, "user", None))
    return TEMPLATES.TemplateResponse(request, template, ctx)


# ---------------- Dashboard ----------------


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, uow: Uow):
    with uow:
        counts = uow.items.count_by_stage()
        pending_sources = len(uow.sources.list_by_status(ApprovalStatus.PENDING, limit=500))
        approved_sources = len(uow.sources.list_by_status(ApprovalStatus.APPROVED, limit=500))
        recent_items = [
            mappers.item_to_domain(row)
            for row in uow.session.scalars(
                select(ItemRow).order_by(ItemRow.updated_at.desc()).limit(8)
            )
        ]
    queue = list_review_queue(uow=uow, limit=200)

    # Tổng công duyệt đang chờ: đây là ràng buộc thật của hệ thống này — không
    # phải tiền mà là thời gian người.
    review_minutes = sum(e.expected_minutes[1] for e in queue)

    return _render(
        request,
        "dashboard.html",
        title="Bảng điều khiển",
        pipeline=[(s, _stage_label(s), counts.get(s, 0)) for s in PIPELINE_ORDER],
        blocked=[(s, _stage_label(s), counts.get(s, 0)) for s in BLOCKED_STAGES],
        stage_labels={s.value: _stage_label(s) for s in ItemStage},
        pending_sources=pending_sources,
        approved_sources=approved_sources,
        review_count=len(queue),
        review_minutes=review_minutes,
        total_items=sum(counts.values()),
        active_items=sum(
            counts.get(s, 0) for s in PIPELINE_ORDER
            if s not in (ItemStage.HUMAN_REVIEW, ItemStage.APPROVED, ItemStage.PUBLISHED)
        ),
        failed_items=counts.get(ItemStage.FAILED, 0),
        editorial_count=counts.get(ItemStage.TRANSCRIPT_REVIEW, 0)
        + counts.get(ItemStage.TRANSCRIPT_APPROVED, 0),
        recent_items=recent_items,
    )


# ---------------- Nguồn ----------------


# ---------------- Studio: video dựng từ đề bài nhập vào ----------------


@router.get("/studio", response_class=HTMLResponse)
def studio_page(request: Request, uow: Uow, config: Config):
    """Danh sách video Studio + form tạo mới.

    Tách khỏi trang Nguồn vì bản chất khác: ở đó là nội dung của người khác cần
    giấy phép, ở đây là nội dung của NMI cần một người chịu trách nhiệm.
    """
    with uow:
        studio = uow.sources.get_by_url(SourceUrl(STUDIO_SOURCE_URL))
        items = (
            [
                mappers.item_to_domain(row)
                for row in uow.session.scalars(
                    select(ItemRow)
                    .where(ItemRow.source_id == studio.id)
                    .order_by(ItemRow.id.desc())
                    .limit(50)
                )
            ]
            if studio
            else []
        )
        series_rows = [
            {"series": series, "children": len(uow.items.list_by_series(series.id or 0))}
            for series in uow.series.list_all()
        ]
    rows = []
    for item in items:
        plan = load_visual_plan(config.media_root, item.id or 0)
        step, total, percent, label = _progress_detail(item.stage)
        rows.append({
            "item": item,
            "stage_label": _stage_label(item.stage),
            "step": step, "total": total, "percent": percent, "step_label": label,
            "shots": plan.shots if plan else (),
            "voice_label": label_for(item.voice_id, config),
            "video_url": (
                "/media/" + item.path_output.relative_path if item.path_output else None
            ),
        })
    return _render(
        request,
        "studio.html",
        title="Studio",
        rows=rows,
        series_rows=series_rows,
        seg_best_min=RECOMMENDED_SEGMENT_MIN_SEC,
        seg_best_max=RECOMMENDED_SEGMENT_MAX_SEC,
        image_provider=config.visuals.provider if config.visuals.enabled else None,
        voices=list_voices(config),
        preview_voice_ids={
            voice.id
            for voice in list_voices(config)
            if voice.preview_path is not None and voice.preview_path.is_file()
        },
        default_voice=default_voice_id(config),
    )


@router.get("/studio/series/new", response_class=HTMLResponse)
def studio_series_new(request: Request, config: Config):
    return _render(
        request,
        "studio_series.html",
        title="Series mới",
        series=None,
        voices=list_voices(config),
        default_voice=default_voice_id(config),
        weekday_labels=WEEKDAY_LABELS,
        min_sec=MIN_SERIES_SEC,
        max_sec=MAX_SERIES_SEC,
        default_font_size=DEFAULT_SUBTITLE_FONT_SIZE,
        default_max_chars=DEFAULT_SUBTITLE_MAX_CHARS,
    )


@router.post("/studio/series", response_class=HTMLResponse)
def studio_series_create(
    request: Request,
    uow: Uow,
    name: Annotated[str, Form()] = "",
    pillar: Annotated[str, Form()] = "",
    hooks: Annotated[str, Form()] = "",
    target_sec: Annotated[float, Form()] = 35.0,
    kept_terms: Annotated[str, Form()] = "",
    output_ratio: Annotated[str, Form()] = "9:16",
    voice_id: Annotated[str, Form()] = "",
    subtitle_font_size: Annotated[int, Form()] = DEFAULT_SUBTITLE_FONT_SIZE,
    subtitle_max_chars: Annotated[int, Form()] = DEFAULT_SUBTITLE_MAX_CHARS,
    weekday: Annotated[list[int] | None, Form()] = None,
    post_time: Annotated[str, Form()] = "",
):
    """Mọi kiểm tra cấu hình nằm trong ``Series``; route chỉ tách chuỗi form."""
    try:
        cadence = (
            PostingCadence(weekdays=tuple(weekday or ()), time_of_day=post_time.strip())
            if weekday or post_time.strip()
            else None
        )
        series = create_series(
            name=name,
            pillar=pillar,
            hook_templates=hooks.splitlines(),
            target_sec=target_sec,
            kept_terms=kept_terms.replace("\n", ",").split(","),
            output_aspect_ratio=AspectRatio.parse(output_ratio),
            voice_id=voice_id or None,
            subtitle=SubtitlePreset(
                font_size=subtitle_font_size, max_chars_per_line=subtitle_max_chars
            ),
            cadence=cadence,
            uow=uow,
            actor=_actor(request),
        )
    except DomainError as exc:
        return _error_page(request, "Không tạo được Series", str(exc))
    return RedirectResponse(url=f"/studio/series/{series.id}?created=1", status_code=303)


@router.get("/studio/series/{series_id}", response_class=HTMLResponse)
def studio_series_detail(request: Request, series_id: int, uow: Uow, config: Config):
    with uow:
        series = uow.series.get(series_id)
        if series is None:
            raise HTTPException(status_code=404, detail=f"không có series #{series_id}")
        children = uow.items.list_by_series(series_id)
        child_ids = [item.id for item in children if item.id is not None]
        events = (
            list(
                uow.session.scalars(
                    select(AuditLogRow).where(
                        AuditLogRow.entity == "item",
                        AuditLogRow.entity_id.in_(child_ids),
                        AuditLogRow.action.in_(
                            ("series_draft_created", "series_production_started")
                        ),
                    )
                )
            )
            if child_ids
            else []
        )
    hooks = {
        event.entity_id: (event.detail or {}).get("hook")
        for event in events
        if event.action == "series_draft_created"
    }
    started = {event.entity_id for event in events if event.action == "series_production_started"}
    rows = []
    for item in children:
        _, _, percent, step_label = _progress_detail(item.stage)
        rows.append({
            "item": item,
            "hook": hooks.get(item.id),
            "stage_label": _stage_label(item.stage),
            "percent": percent,
            "step_label": step_label,
            "started": item.id in started,
            "can_start": item.stage is ItemStage.SCRIPTED and item.id not in started,
        })
    return _render(
        request,
        "studio_series.html",
        title=series.name,
        series=series,
        rows=rows,
        voice_label=label_for(series.voice_id, config),
        max_topics=MAX_TOPICS_PER_BATCH,
    )


@router.post("/studio/series/{series_id}/drafts", response_class=HTMLResponse)
def studio_series_drafts(
    request: Request,
    series_id: int,
    uow: Uow,
    clock: Clock,
    config: Config,
    topics: Annotated[str, Form()] = "",
):
    try:
        with uow:
            glossary = load_glossary(uow, "en")
        outcome = draft_from_series(
            series_id,
            topics=topics.splitlines(),
            author=_actor(request),
            writer=build_script_writer(config.llm),
            speech_rate=config.tts.measured_rate,
            glossary=glossary,
            media_root=config.media_root,
            uow=uow,
            clock=clock,
        )
    except (DomainError, RuntimeError, ValueError) as exc:
        return _error_page(request, "Không sinh được bản nháp", str(exc))
    if outcome.failed:
        return _error_page(
            request,
            f"Đã tạo {len(outcome.created)} bản nháp, {len(outcome.failed)} đề tài lỗi",
            "; ".join(f"“{topic}”: {error}" for topic, error in outcome.failed),
            hint=f"Các bản nháp đã tạo nằm ở /studio/series/{series_id}. "
            "Nhập lại riêng các đề tài lỗi.",
        )
    return RedirectResponse(
        url=f"/studio/series/{series_id}?drafted={len(outcome.created)}", status_code=303
    )


@router.post("/studio/series/{series_id}/items/{item_id}/start", response_class=HTMLResponse)
def studio_series_start(request: Request, series_id: int, item_id: int, uow: Uow):
    try:
        start_series_video(item_id, series_id=series_id, uow=uow, actor=_actor(request))
    except DomainError as exc:
        return _error_page(request, "Không đưa được bản nháp vào sản xuất", str(exc))
    return RedirectResponse(url=f"/studio/series/{series_id}?started={item_id}", status_code=303)


@router.get("/studio/{item_id}", response_class=HTMLResponse)
def studio_detail(request: Request, item_id: int, uow: Uow, config: Config):
    with uow:
        item = uow.items.get(item_id)
        studio = uow.sources.get_by_url(SourceUrl(STUDIO_SOURCE_URL))
        if item is None or studio is None or item.source_id != studio.id:
            raise HTTPException(status_code=404, detail=f"không có video Studio #{item_id}")
        events = list(
            uow.session.scalars(
                select(AuditLogRow)
                .where(AuditLogRow.entity == "item", AuditLogRow.entity_id == item_id)
                .order_by(AuditLogRow.id.desc())
                .limit(50)
            )
        )
    plan = load_visual_plan(config.media_root, item_id)
    cues_path = config.paths.item_work_dir(item_id) / "cues.json"
    cues = []
    if cues_path.exists():
        import json

        cues = json.loads(cues_path.read_text("utf-8"))
    step, total, percent, label = _progress_detail(item.stage)
    return _render(
        request,
        "studio_detail.html",
        title=item.title_original or f"Video Studio #{item_id}",
        item=item,
        shots=plan.shots if plan else (),
        events=events,
        stage_label=_stage_label(item.stage),
        step=step,
        total=total,
        percent=percent,
        step_label=label,
        voice_label=label_for(item.voice_id, config),
        video_url=("/media/" + item.path_output.relative_path if item.path_output else None),
        image_provider=config.visuals.provider if config.visuals.enabled else None,
        cues=cues,
        can_recompose=item.stage is ItemStage.HUMAN_REVIEW,
        is_published=item.stage is ItemStage.PUBLISHED,
    )


@router.get("/studio/{item_id}/voice", response_class=FileResponse)
def studio_voice(item_id: int, uow: Uow, config: Config):
    with uow:
        item = uow.items.get(item_id)
        studio = uow.sources.get_by_url(SourceUrl(STUDIO_SOURCE_URL))
    if item is None or studio is None or item.source_id != studio.id or item.path_work is None:
        raise HTTPException(status_code=404, detail="audio giọng đọc chưa tồn tại")
    path = config.paths.absolute(item.path_work.relative_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="file audio giọng đọc chưa tồn tại")
    return FileResponse(path)


@router.post("/studio/{item_id}/recompose", response_class=HTMLResponse)
def studio_recompose(
    request: Request,
    item_id: int,
    uow: Uow,
    config: Config,
    start: Annotated[list[float] | None, Form()] = None,
    end: Annotated[list[float] | None, Form()] = None,
    text_line: Annotated[list[str] | None, Form()] = None,
):
    import json

    try:
        with uow:
            item = uow.items.get(item_id)
        if item is None or item.stage is not ItemStage.HUMAN_REVIEW:
            raise ValueError("chỉ sửa timing khi bản dựng đang chờ duyệt")
        start, end, text_line = start or [], end or [], text_line or []
        if not (len(start) == len(end) == len(text_line)):
            raise ValueError("số mốc thời gian và dòng phụ đề không khớp")
        cues = []
        previous_end = 0.0
        for index, (cue_start, cue_end, cue_text) in enumerate(
            zip(start, end, text_line, strict=True), start=1
        ):
            if cue_start < 0 or cue_end <= cue_start or cue_start < previous_end:
                raise ValueError(f"timing dòng {index} không hợp lệ hoặc bị chồng nhau")
            cues.append({"start": cue_start, "end": cue_end, "text": cue_text.strip()})
            previous_end = cue_end
        cues_path = config.paths.item_work_dir(item_id) / "cues.json"
        cues_path.parent.mkdir(parents=True, exist_ok=True)
        cues_path.write_text(json.dumps(cues, ensure_ascii=False, indent=1), encoding="utf-8")
        queue_studio_recompose(item_id, uow=uow, actor=_actor(request))
    except (DomainError, ValueError) as exc:
        return _error_page(request, "Không dựng lại được video", str(exc))
    return RedirectResponse(url=f"/studio/{item_id}?recomposing=1", status_code=303)


@router.post("/studio", response_class=HTMLResponse)
async def studio_create(
    request: Request,
    uow: Uow,
    clock: Clock,
    config: Config,
    brief: Annotated[str, Form()],
    title: Annotated[str, Form()] = "",
    target_sec: Annotated[float, Form()] = 60.0,
    voice_id: Annotated[str, Form()] = "",
    output_ratio: Annotated[str, Form()] = "9:16",
    media: Annotated[list[UploadFile] | None, OPTIONAL_FILES] = None,
):
    actor = _actor(request)
    try:
        with uow:
            glossary = load_glossary(uow, "en")
        result = create_video_from_prompt(
            brief=brief,
            title=title,
            target_sec=target_sec,
            author=actor,
            writer=build_script_writer(config.llm),
            speech_rate=config.tts.measured_rate,
            glossary=glossary,
            media_root=config.media_root,
            uow=uow,
            clock=clock,
            voice_id=voice_id.strip() or None,
            output_aspect_ratio=(
                None if output_ratio == "original" else AspectRatio.parse(output_ratio)
            ),
        )
        for upload in media or []:
            if not upload.filename:
                continue
            suffix = Path(upload.filename).suffix.lower()
            if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".webm"}:
                raise ValueError("chỉ nhận ảnh PNG/JPG/WEBP hoặc video MP4/MOV/WEBM")
            destination = config.paths.source / "studio" / f"{uuid4().hex}{suffix}"
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as output:
                while chunk := await upload.read(1024 * 1024):
                    output.write(chunk)
            add_shot(
                result.item.id or 0,
                shot=Shot(
                    kind=ShotKind.UPLOAD,
                    seconds=6.0,
                    caption=Path(upload.filename).stem,
                    asset=config.paths.relative(destination),
                ),
                media_root=config.media_root,
                uow=uow,
                actor=actor,
            )
    except (DomainError, RuntimeError, ValueError) as exc:
        return _error_page(request, "Không tạo được video", str(exc))
    finally:
        for upload in media or []:
            await upload.close()
    return RedirectResponse(url=f"/studio/{result.item.id}?created=1", status_code=303)


@router.post("/studio/{item_id}/shots", response_class=HTMLResponse)
async def studio_add_shot(
    request: Request,
    item_id: int,
    uow: Uow,
    config: Config,
    kind: Annotated[str, Form()],
    seconds: Annotated[float, Form()] = 6.0,
    caption: Annotated[str, Form()] = "",
    prompt: Annotated[str, Form()] = "",
    chart_data: Annotated[str, Form()] = "",
    media: Annotated[UploadFile | None, OPTIONAL_FILE] = None,
):
    """Thêm một cảnh: file người dùng đưa vào, prompt cho AI, hoặc số liệu biểu đồ."""
    try:
        shot_kind = ShotKind(kind)
        asset: str | None = None
        if shot_kind in (ShotKind.UPLOAD, ShotKind.STOCK):
            if media is None or not media.filename:
                raise ValueError("chọn một file ảnh hoặc video")
            suffix = Path(media.filename).suffix.lower()
            if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".webm"}:
                raise ValueError("chỉ nhận PNG, JPG, WEBP, MP4, MOV hoặc WEBM")
            destination = config.paths.source / "studio" / f"{uuid4().hex}{suffix}"
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as output:
                while chunk := await media.read(1024 * 1024):
                    output.write(chunk)
            asset = config.paths.relative(destination)
        data: tuple[tuple[str, float], ...] = ()
        if shot_kind is ShotKind.CHART:
            data = _parse_chart_data(chart_data)
        add_shot(
            item_id,
            shot=Shot(
                kind=shot_kind,
                seconds=seconds,
                caption=caption.strip(),
                asset=asset,
                prompt=prompt.strip(),
                data=data,
            ),
            media_root=config.media_root,
            uow=uow,
            actor=_actor(request),
        )
    except (DomainError, ValueError) as exc:
        return _error_page(request, "Không thêm được cảnh", str(exc))
    finally:
        if media is not None:
            await media.close()
    return RedirectResponse(url=f"/studio?shot_added={item_id}", status_code=303)


@router.post("/studio/{item_id}/shots/{index}/delete", response_class=HTMLResponse)
def studio_remove_shot(
    request: Request,
    item_id: int,
    index: int,
    uow: Uow,
    config: Config,
):
    try:
        remove_shot(
            item_id, index=index, media_root=config.media_root, uow=uow,
            actor=_actor(request),
        )
    except DomainError as exc:
        return _error_page(request, "Không xoá được cảnh", str(exc))
    return RedirectResponse(url=f"/studio/{item_id}?shot_removed=1", status_code=303)


def _parse_chart_data(raw: str) -> tuple[tuple[str, float], ...]:
    """Đọc số liệu dạng ``Nhãn = giá trị`` mỗi dòng.

    Không đoán định dạng và không nhận số liệu từ model: mỗi cột trong biểu đồ
    phải truy được về một con số người dùng gõ vào.
    """
    pairs: list[tuple[str, float]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        if "=" not in line:
            raise ValueError(f"dòng '{line.strip()}' phải có dạng: Nhãn = số")
        label, _, value = line.partition("=")
        try:
            pairs.append((label.strip(), float(value.strip().replace(",", "."))))
        except ValueError as exc:
            raise ValueError(f"'{value.strip()}' không phải số") from exc
    if not pairs:
        raise ValueError("biểu đồ phải có ít nhất một số liệu")
    return tuple(pairs)


@router.get("/item-status")
def item_status(uow: Uow):
    """Snapshot nhỏ cho UI polling; không tải lại transcript hay lịch sử audit."""
    with uow:
        rows = uow.session.execute(
            select(
                ItemRow.id,
                ItemRow.stage,
                ItemRow.stage_error,
                ItemRow.updated_at,
                ItemRow.parent_item_id,
                ItemRow.clip_index,
            )
        ).all()
        jobs = uow.session.execute(
            select(JobRow).order_by(JobRow.item_id, JobRow.id.desc())
        ).scalars().all()
    latest_jobs = {}
    for job in jobs:
        if job.item_id is not None and job.item_id not in latest_jobs:
            latest_jobs[job.item_id] = job

    def live_detail(row):
        step, total, progress, label = _progress_detail(row.stage)
        job = latest_jobs.get(row.id)
        if job is None or job.status.value not in {"pending", "running", "failed"}:
            return step, total, progress, label, None, row.stage_error
        target = JOB_TARGET_STAGE.get(job.task)
        if target in PIPELINE_ORDER:
            step = PIPELINE_ORDER.index(target) + 1
        prefix = {
            "pending": "Chờ xử lý", "running": "Đang xử lý", "failed": "Xử lý lỗi",
        }[job.status.value]
        label = f"{prefix}: {JOB_LABELS.get(job.task, job.task)}"
        return step, total, progress, label, job.status.value, row.stage_error or job.error
    return {
        "items": [
            {
                "id": row.id,
                "stage": row.stage.value,
                # Badge hiện nhãn tiếng Việt; giá trị enum chỉ còn dùng làm class CSS.
                "stage_label": _stage_label(row.stage),
                # Trang nguồn gộp clip con thành thống kê trên dòng video gốc — để
                # gộp được ở phía trình duyệt thì snapshot phải nói clip thuộc về ai.
                "parent_item_id": row.parent_item_id,
                "clip_index": row.clip_index,
                "progress": live_detail(row)[2],
                "step": live_detail(row)[0],
                "total_steps": live_detail(row)[1],
                "label": live_detail(row)[3],
                "job_status": live_detail(row)[4],
                "error": live_detail(row)[5],
                "updated_at": row.updated_at.isoformat(),
            }
            for row in rows
        ]
    }


@router.get("/sources", response_class=HTMLResponse)
def sources_page(
    request: Request, uow: Uow, status: str = "all",
    q: str = "", page: int = 1, per_page: int = 10,
):
    if status != "all":
        try:
            ApprovalStatus(status)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail=f"trạng thái không hợp lệ: {status}"
            ) from exc
    page = max(1, page)
    per_page = per_page if per_page in (10, 25, 50, 100) else 10
    with uow:
        all_sources = [
            source for source_status in ApprovalStatus
            for source in uow.sources.list_by_status(source_status, limit=1000)
        ]
        needle = q.strip().lower()
        filtered = [
            source
            for source in all_sources
            if status in ("all", source.status.value)
            and (
                not needle
                or needle
                in " ".join(
                    (
                        source.display_name or "",
                        source.url.value,
                        source.external_owner_id or "",
                        " ".join(source.topics),
                        source.notes or "",
                    )
                ).lower()
            )
        ]
        filtered.sort(key=lambda source: source.id or 0, reverse=True)
        total = len(filtered)
        sources = filtered[(page - 1) * per_page:page * per_page]
        rows = []
        for source in sources:
            db_items = uow.session.scalars(
                select(ItemRow).where(ItemRow.source_id == source.id).order_by(ItemRow.id.desc())
            ).all()
            items = [mappers.item_to_domain(row) for row in db_items]
            ids = [item.id for item in items if item.id is not None]
            audit_filter = and_(
                AuditLogRow.entity == "source", AuditLogRow.entity_id == source.id
            )
            if ids:
                audit_filter = or_(
                    and_(AuditLogRow.entity == "source", AuditLogRow.entity_id == source.id),
                    and_(AuditLogRow.entity == "item", AuditLogRow.entity_id.in_(ids)),
                )
            audits = uow.session.scalars(
                select(AuditLogRow).where(audit_filter).order_by(AuditLogRow.created_at.desc()).limit(200)
            ).all()
            by_entity: dict[tuple[str, int], list] = {}
            for audit_row in audits:
                by_entity.setdefault((audit_row.entity, audit_row.entity_id), []).append(audit_row)
            # Chỉ liệt kê video gốc. Clip con gộp thành thống kê trên chính dòng
            # của nó: hai dòng cho cùng một video làm người xem tưởng có hai video,
            # và hai thanh tiến trình cạnh nhau thì không thanh nào đọc ra nghĩa.
            children: dict[int, list] = {}
            for item in items:
                if item.parent_item_id is not None:
                    children.setdefault(item.parent_item_id, []).append(item)
            item_views = []
            for item in items:
                if item.parent_item_id is not None:
                    continue
                clips = sorted(children.get(item.id or 0, []), key=lambda c: c.clip_index or 0)
                stage_counts: dict[ItemStage, int] = {}
                for clip in clips:
                    stage_counts[clip.stage] = stage_counts.get(clip.stage, 0) + 1
                # Transcript, video thành phẩm và form thao tác nay nằm ở
                # /review/{id}. Trang này chỉ liệt kê, nên không đọc file
                # transcript của từng item nữa — mỗi dòng tốn một lần đọc đĩa chỉ
                # để quyết định hiện một cái link.
                item_views.append({
                    "item": item,
                    "display_id": f"{source.id}-gốc" if clips else f"{source.id}-1",
                    "progress": _progress_detail(item.stage),
                    "stage_label": _stage_label(item.stage),
                    # Video gốc dừng ở bước "Chọn đoạn" rồi giao việc cho clip con,
                    # nên % của nó không mô tả tiến độ thật của bất cứ thứ gì.
                    "show_percent": not clips,
                    "clip_count": len(clips),
                    "clip_stages": [
                        (stage.value, PIPELINE_LABELS.get(stage, stage.value), count)
                        for stage, count in sorted(
                            stage_counts.items(),
                            key=lambda pair: PIPELINE_PROGRESS.get(pair[0], 0),
                        )
                    ],
                })
            # Lịch sử rẽ nhánh như trang review: nguồn → từng video gốc → từng clip.
            history = [{
                "code": f"Nguồn #{source.id}",
                "title": source.display_name or source.url.host,
                "events": by_entity.get(("source", source.id or 0), []),
                "level": 0,
            }]
            for view in item_views:
                history.append({
                    "code": f"#{view['display_id']}",
                    "title": "Video gốc" if view["clip_count"] else "Video",
                    "events": by_entity.get(("item", view["item"].id or 0), []),
                    "level": 1,
                })
                for clip in sorted(
                    children.get(view["item"].id or 0, []), key=lambda c: c.clip_index or 0
                ):
                    history.append({
                        "code": f"#{source.id}-{clip.clip_index}",
                        "title": f"Clip {clip.clip_index} · {_stage_label(clip.stage)}",
                        "events": by_entity.get(("item", clip.id or 0), []),
                        "level": 2,
                    })
            rows.append(
                SimpleNamespace(
                    source=source,
                    items=item_views,
                    history=history,
                    clip_total=sum(len(group) for group in children.values()),
                )
            )
    return _render(
        request,
        "sources.html",
        title="Nguồn đã khai báo",
        rows=rows,
        status=status,
        q=q,
        page=page,
        per_page=per_page,
        total=total,
        pages=max(1, (total + per_page - 1) // per_page),
        statuses=list(ApprovalStatus),
        platforms=list(Platform),
        kinds=list(SourceKind),
        content_types=list(ContentType),
        license_types=list(LicenseType),
    )


@router.post("/items/{item_id}/clips", response_class=HTMLResponse)
def create_clips_form(
    request: Request, item_id: int, uow: Uow, clock: Clock, config: Config,
    start_sec: Annotated[list[float], Form()],
    end_sec: Annotated[list[float], Form()],
    include_attribution: Annotated[bool, Form()] = False,
    voice_id: Annotated[str, Form()] = "",
    output_ratio: Annotated[str, Form()] = "original",
):
    try:
        if len(start_sec) != len(end_sec):
            raise ValueError("số mốc bắt đầu và kết thúc không khớp")
        created = create_manual_clips(
            item_id,
            ranges=list(zip(start_sec, end_sec, strict=True)),
            include_attribution=include_attribution,
            media_root=config.media_root,
            uow=uow,
            clock=clock,
            actor=_actor(request),
            voice_id=voice_id.strip() or None,
            output_aspect_ratio=(
                None if output_ratio == "original" else AspectRatio.parse(output_ratio)
            ),
        )
    except (DomainError, ValueError) as exc:
        return _review_error(item_id, f"Không tạo được clip: {exc}")
    return RedirectResponse(
        url=f"/review/{item_id}?created={len(created)}", status_code=303
    )


@router.get("/items/{item_id}/source-video", response_class=FileResponse)
def source_video(item_id: int, uow: Uow, config: Config):
    with uow:
        item = uow.items.get(item_id)
    if item is None or item.path_source is None:
        raise HTTPException(status_code=404, detail="video nguồn không tồn tại")
    path = config.paths.absolute(item.path_source.relative_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="file video nguồn không tồn tại")
    return FileResponse(path)


@router.get("/voices/{engine}/{name}/preview", response_class=FileResponse)
def voice_preview(engine: str, name: str, config: Config):
    """Phát đúng file mẫu đã khai trong catalog; không mở cả cây media ra HTTP."""
    voice = next(
        (option for option in list_voices(config) if option.id == f"{engine}:{name}"),
        None,
    )
    if voice is None or voice.preview_path is None or not voice.preview_path.is_file():
        raise HTTPException(status_code=404, detail="giọng này chưa có file nghe thử")
    return FileResponse(voice.preview_path)


@router.post("/items/{item_id}/transcript", response_class=HTMLResponse)
def save_transcript_form(
    request: Request,
    item_id: int,
    uow: Uow,
    config: Config,
    start: Annotated[list[float], Form()],
    end: Annotated[list[float], Form()],
    text_line: Annotated[list[str], Form()],
    decision: Annotated[str, Form()] = "save",
):
    clean_actor = _actor(request)
    try:
        edit_transcript(
            item_id,
            starts=start,
            ends=end,
            texts=text_line,
            media_root=config.media_root,
            uow=uow,
            actor=clean_actor,
        )
        if decision == "approve":
            approve_transcript(item_id, actor=clean_actor, uow=uow)
    except DomainError as exc:
        return _review_error(item_id, f"Không lưu được transcript: {exc}")
    flag = "approved" if decision == "approve" else "saved"
    return RedirectResponse(url=f"/review/{item_id}?{flag}=1", status_code=303)


@router.post("/sources", response_class=HTMLResponse)
def declare(
    request: Request,
    uow: Uow,
    url: Annotated[str, Form()],
    platform: Annotated[Platform, Form()],
    kind: Annotated[SourceKind, Form()],
    audio_lang: Annotated[str, Form()] = "en",
    external_owner_id: Annotated[str, Form()] = "",
    display_name: Annotated[str, Form()] = "",
    topics: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
):
    try:
        clean_actor = _actor(request)
        declare_source(
            DeclareSourceCommand(
                url=url.strip(),
                platform=platform,
                kind=kind,
                display_name=display_name.strip() or None,
                audio_lang=audio_lang.strip() or "en",
                external_owner_id=external_owner_id.strip() or None,
                topics=tuple(t.strip() for t in topics.split(",") if t.strip()),
                notes=notes.strip() or None,
            ),
            uow=uow,
            actor=clean_actor,
        )
    except (SourceAlreadyDeclared, DomainError) as exc:
        return _error_page(request, "Không khai báo được nguồn", str(exc))
    return RedirectResponse(url="/sources", status_code=303)


@router.post("/sources/{source_id}/approve", response_class=HTMLResponse)
def approve_source_form(
    request: Request,
    source_id: int,
    uow: Uow,
    clock: Clock,
    license_type: Annotated[LicenseType, Form()],
    evidence_ref: Annotated[str, Form()] = "",
    attribution_text: Annotated[str, Form()] = "",
    may_translate: Annotated[bool, Form()] = False,
    may_modify_audio: Annotated[bool, Form()] = False,
    may_subtitle: Annotated[bool, Form()] = False,
    may_republish: Annotated[bool, Form()] = False,
    may_commercial_use: Annotated[bool, Form()] = False,
):
    try:
        clean_actor = _actor(request)
        with uow:
            source = uow.sources.get(source_id)
        if source is None:
            raise DomainError(f"không có nguồn #{source_id}")
        effective_evidence = evidence_ref.strip() or (
            f"Xác nhận giấy phép có sẵn bởi {clean_actor or 'web'}"
        )
        effective_attribution = _effective_attribution(attribution_text, license_type, source)
        approve_source(
            ApproveSourceCommand(
                source_id=source_id,
                actor=clean_actor,
                license_type=license_type,
                evidence_ref=effective_evidence,
                attribution_text=effective_attribution,
                may_translate=may_translate,
                may_modify_audio=may_modify_audio,
                may_subtitle=may_subtitle,
                may_republish=may_republish,
                may_commercial_use=may_commercial_use,
            ),
            uow=uow,
            clock=clock,
        )
    except DomainError as exc:
        return _error_page(request, "Không duyệt được nguồn", str(exc))
    return RedirectResponse(url="/sources", status_code=303)


@router.post("/sources/{source_id}/start", response_class=HTMLResponse)
def start_single_source(request: Request, source_id: int, uow: Uow, clock: Clock):
    try:
        with uow:
            source = uow.sources.get(source_id)
        if source is None:
            raise DomainError(f"không có nguồn #{source_id}")
        if source.kind is not SourceKind.SINGLE_URL:
            raise DomainError("chỉ nguồn loại một video mới có thể tự tải URL nguồn")
        result = submit_url(source.url.value, uow=uow, clock=clock, actor=_actor(request))
    except (DomainError, ItemAlreadyExists) as exc:
        return _error_page(request, "Không bắt đầu được pipeline", str(exc))
    return RedirectResponse(
        url=f"/sources?auto_started={result.item.id}", status_code=303
    )


# ---------------- Hộp thư URL ----------------


async def _store_upload(video: UploadFile, config: Settings) -> tuple[str, Path]:
    """Ghi file lên đĩa và kiểm bằng ffprobe. Trả ``upload_id`` và đường dẫn."""
    suffix = Path(video.filename or "").suffix.lower()
    if suffix not in {".mp4", ".mov", ".mkv", ".webm"}:
        raise ValueError("chỉ hỗ trợ MP4, MOV, MKV hoặc WebM")
    upload_id = uuid4().hex
    destination = config.paths.source / "uploads" / f"{upload_id}{suffix}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as output:
        while chunk := await video.read(1024 * 1024):
            output.write(chunk)
    return upload_id, destination


def _register_upload(
    *, source_id: int, upload_id: str, path: Path, filename: str,
    uow: SqlUnitOfWork, clock: SystemClock, config: Settings, actor: str,
):
    info = ffmpeg.probe(path)
    if not info.has_video or not info.has_audio or not info.width or not info.height:
        raise ValueError("file phải có cả hình ảnh và âm thanh")
    return register_uploaded_video(
        source_id=source_id,
        upload_id=upload_id,
        original_filename=Path(filename or "video").name,
        asset=MediaAsset(config.paths.relative(path)),
        duration_sec=max(1, round(info.duration_sec)),
        aspect_ratio=AspectRatio.from_size(info.width, info.height),
        uow=uow,
        clock=clock,
        actor=actor,
    )


@router.post("/uploads", response_class=HTMLResponse)
async def upload_new_source_video(
    request: Request,
    uow: Uow,
    clock: Clock,
    config: Config,
    video: Annotated[UploadFile, File()],
    url: Annotated[str, Form()],
    license_type: Annotated[LicenseType, Form()],
    platform: Annotated[Platform, Form()] = Platform.YOUTUBE,
    display_name: Annotated[str, Form()] = "",
    audio_lang: Annotated[str, Form()] = "en",
    external_owner_id: Annotated[str, Form()] = "",
    evidence_ref: Annotated[str, Form()] = "",
    attribution_text: Annotated[str, Form()] = "",
    may_translate: Annotated[bool, Form()] = False,
    may_modify_audio: Annotated[bool, Form()] = False,
    may_subtitle: Annotated[bool, Form()] = False,
    may_republish: Annotated[bool, Form()] = False,
    may_commercial_use: Annotated[bool, Form()] = False,
):
    """Nạp video = **khai báo một nguồn mới rồi nạp file vào nó**.

    Nút này trước đây bắt chọn một nguồn có sẵn, trùng đúng việc mà nút “Upload
    file” trên từng dòng nguồn đã làm — hai lối vào cho một việc. Nay mỗi nút một
    việc: ở đây là nguồn mới, ở dòng nguồn là nạp thêm video vào nguồn đó.

    License gate **không** được nới: nguồn mới vẫn phải khai giấy phép và phạm vi
    quyền ngay trong form này, và vẫn đi qua ``declare_source`` → ``approve_source``
    như mọi nguồn khác. Form này chỉ gộp ba bước thành một màn hình, không bỏ bước nào.
    """
    clean_actor = _actor(request)
    destination: Path | None = None
    try:
        upload_id, destination = await _store_upload(video, config)
        source = declare_source(
            DeclareSourceCommand(
                url=url.strip(),
                platform=platform,
                kind=SourceKind.SINGLE_URL,
                display_name=display_name.strip() or None,
                audio_lang=audio_lang.strip() or "en",
                external_owner_id=external_owner_id.strip() or None,
            ),
            uow=uow,
            actor=clean_actor,
        )
        assert source.id is not None
        approve_source(
            ApproveSourceCommand(
                source_id=source.id,
                actor=clean_actor,
                license_type=license_type,
                evidence_ref=evidence_ref.strip()
                or f"Xác nhận giấy phép có sẵn bởi {clean_actor}",
                attribution_text=_effective_attribution(
                    attribution_text, license_type, source
                ),
                may_translate=may_translate,
                may_modify_audio=may_modify_audio,
                may_subtitle=may_subtitle,
                may_republish=may_republish,
                may_commercial_use=may_commercial_use,
            ),
            uow=uow,
            clock=clock,
        )
        item = _register_upload(
            source_id=source.id,
            upload_id=upload_id,
            path=destination,
            filename=video.filename or "video",
            uow=uow,
            clock=clock,
            config=config,
            actor=clean_actor,
        )
    except (SourceAlreadyDeclared, DomainError, RuntimeError, ValueError) as exc:
        if destination is not None:
            destination.unlink(missing_ok=True)
        return _error_page(request, "Không nạp được video", str(exc))
    finally:
        await video.close()
    return RedirectResponse(url=f"/sources?uploaded={item.id}", status_code=303)


@router.post("/sources/{source_id}/uploads", response_class=HTMLResponse)
async def upload_into_source(
    request: Request,
    source_id: int,
    uow: Uow,
    clock: Clock,
    config: Config,
    video: Annotated[UploadFile, File()],
):
    """Nạp thêm một video vào **nguồn đã duyệt** — nút trên từng dòng nguồn."""
    destination: Path | None = None
    try:
        upload_id, destination = await _store_upload(video, config)
        item = _register_upload(
            source_id=source_id,
            upload_id=upload_id,
            path=destination,
            filename=video.filename or "video",
            uow=uow,
            clock=clock,
            config=config,
            actor=_actor(request),
        )
    except (DomainError, RuntimeError, ValueError) as exc:
        if destination is not None:
            destination.unlink(missing_ok=True)
        return _error_page(request, "Không nạp được video", str(exc))
    finally:
        await video.close()
    return RedirectResponse(url=f"/sources?uploaded={item.id}", status_code=303)


@router.post("/items", response_class=HTMLResponse)
def submit(
    request: Request,
    uow: Uow,
    clock: Clock,
    url: Annotated[str, Form()],
):
    try:
        result = submit_url(url.strip(), uow=uow, clock=clock, actor=_actor(request))
    except (SourceNotDeclared, ItemAlreadyExists) as exc:
        return _error_page(request, "Không nạp được URL", str(exc))
    except DomainError as exc:
        return _error_page(request, "Không nạp được URL", str(exc))

    if not result.accepted:
        return _error_page(
            request,
            "URL bị license gate chặn",
            result.reason or "",
            hint="Item vẫn được lưu lại để thấy nhu cầu thật. Duyệt nguồn rồi nạp lại.",
        )
    return RedirectResponse(url="/sources", status_code=303)


# ---------------- Soát transcript (gate người thứ nhất) ----------------


@router.get("/transcripts", response_class=HTMLResponse)
def transcript_queue(request: Request, uow: Uow, config: Config):
    """Hàng đợi soát transcript ngoại ngữ.

    Gate này tồn tại vì ASR có tỷ lệ sai thật: tiếng Anh sạch ~93–95% đúng, tiếng
    Trung khoảng 1/8 ký tự sai. Bỏ gate thì sai sót của máy đi thẳng vào kịch bản.
    """
    with uow:
        items = uow.items.list_by_stage(ItemStage.TRANSCRIPT_REVIEW, limit=50)
        rows = []
        for item in items:
            source = uow.sources.get(item.source_id)
            try:
                text, _ = load_transcript(config.media_root, item.id or 0)
            except Exception:
                text = ""
            rows.append(
                {
                    "item": item,
                    "source": source,
                    "lang": source.audio_lang.code if source else "?",
                    "needs_extra": source.audio_lang.needs_extra_review if source else False,
                    "text": text,
                }
            )
    return _render(
        request,
        "transcripts.html",
        title="Soát transcript",
        rows=rows,
        approved=request.query_params.get("approved"),
    )


@router.post("/transcripts/{item_id}/approve", response_class=HTMLResponse)
def transcript_approve(
    request: Request, item_id: int, uow: Uow
):
    who = _actor(request)
    try:
        approve_transcript(item_id, actor=who, uow=uow)
    except DomainError as exc:
        return _error_page(request, "Không ghi được", str(exc))
    # Về thẳng trang review: việc kế tiếp sau khi soát transcript là **chọn đoạn**,
    # và form đó nằm ở đúng trang này.
    return RedirectResponse(url=f"/review/{item_id}?approved=1", status_code=303)


# ---------------- Hàng đợi duyệt ----------------


@router.get("/review", response_class=HTMLResponse)
def review_queue(request: Request, uow: Uow):
    entries = list_review_queue(uow=uow, limit=100)
    return _render(request, "review_queue.html", title="Chờ duyệt", entries=entries)


@router.get("/review/{item_id}", response_class=HTMLResponse)
def review_detail(request: Request, item_id: int, uow: Uow, config: Config):
    with uow:
        item = uow.items.get(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"không có item #{item_id}")
        source = uow.sources.get(item.source_id)
        parent = uow.items.get(item.parent_item_id) if item.parent_item_id else None
        # Quan hệ là **một video gốc → nhiều clip con**. Trang của video gốc liệt kê
        # các clip của nó; trang của một clip liệt kê các clip anh em để đi lại được.
        root = parent or item
        clips = [
            mappers.item_to_domain(row)
            for row in uow.session.scalars(
                select(ItemRow)
                .where(ItemRow.parent_item_id == root.id)
                .order_by(ItemRow.clip_index)
            )
        ]
        # Lịch sử gom theo từng nhánh (nguồn · video gốc · từng clip) thay vì trộn
        # một dòng chảy: trộn lại thì không đọc được sự kiện nào thuộc về clip nào.
        history_ids = [i for i in ([root.id] + [c.id for c in clips]) if i is not None]
        audits = uow.session.scalars(
            select(AuditLogRow)
            .where(
                or_(
                    and_(AuditLogRow.entity == "item", AuditLogRow.entity_id.in_(history_ids)),
                    and_(
                        AuditLogRow.entity == "source",
                        AuditLogRow.entity_id == item.source_id,
                    ),
                )
            )
            .order_by(AuditLogRow.created_at.desc())
            .limit(200)
        ).all()
    transcript_segments: list[dict] = []
    with suppress(FileNotFoundError, ValueError):
        _, transcript_segments = load_transcript(config.media_root, item.id or 0)

    source_id = item.source_id
    clip_rows = [_clip_view(clip, source_id, config) for clip in clips]
    if not clips and item.path_output:
        # Item chạy thẳng hết pipeline (không cắt clip) vẫn phải có cửa duyệt —
        # nó xuất hiện như một dòng thành phẩm của chính nó.
        clip_rows = [_clip_view(item, source_id, config)]

    by_entity: dict[tuple[str, int], list] = {}
    for row in audits:
        by_entity.setdefault((row.entity, row.entity_id), []).append(row)
    history = []
    if source is not None:
        history.append({
            "code": f"Nguồn #{source_id}",
            "title": source.display_name or source.url.host,
            "events": by_entity.get(("source", source_id), []),
        })
    history.append({
        "code": f"#{source_id}-gốc" if clips else f"#{source_id}-1",
        "title": "Video gốc" if clips else "Video",
        "events": by_entity.get(("item", root.id or 0), []),
    })
    for clip in clips:
        history.append({
            "code": f"#{source_id}-{clip.clip_index}",
            "title": f"Clip {clip.clip_index} · {_stage_label(clip.stage)}",
            "events": by_entity.get(("item", clip.id or 0), []),
        })

    return _render(
        request,
        "review_item.html",
        title=f"Duyệt item #{item_id}",
        item=item,
        source=source,
        root=root,
        is_root=item.parent_item_id is None,
        stage_label=_stage_label(item.stage),
        history=history,
        clips=clip_rows,
        clip_count=len(clips),
        publish_enabled=config.publish.enabled,
        workflow=_workflow(item.stage),
        off_pipeline=item.stage in BLOCKED_STAGES,
        default_tab=_default_review_tab(
            item,
            has_clips=bool(clip_rows),
            created=bool(request.query_params.get("created")),
        ),
        seg_best_min=RECOMMENDED_SEGMENT_MIN_SEC,
        seg_best_max=RECOMMENDED_SEGMENT_MAX_SEC,
        voices=list_voices(config),
        preview_voice_ids={
            voice.id
            for voice in list_voices(config)
            if voice.preview_path is not None and voice.preview_path.is_file()
        },
        default_voice=default_voice_id(config),
        transcript_segments=transcript_segments,
        source_video_url=(
            f"/items/{item.id}/source-video" if item.path_source else None
        ),
        # Đường dẫn tương đối trong DB → URL phục vụ file. Chỉ item đã render
        # mới có, nên template phải chịu được None.
        # path_output đã là "output/item-xxx/final.mp4", còn mount là
        # /media/output → ghép "/media/" là ra đúng, không thêm "output" lần nữa
        video_url=("/media/" + item.path_output.relative_path if item.path_output else None),
        expected=source.expected_review_minutes if source else (20, 35),
    )


@router.post("/review/{item_id}/{decision}", response_class=HTMLResponse)
def review_decide(
    request: Request,
    item_id: int,
    decision: str,
    uow: Uow,
    clock: Clock,
    config: Config,
    notes: Annotated[str, Form()] = "",
    return_to: Annotated[int, Form()] = 0,
):
    # Quyết định thường được bấm trong popup của một clip, trên trang video gốc —
    # trả người dùng về đúng trang họ đang đứng, không nhảy sang trang của clip.
    back = return_to or item_id
    who = _actor(request)
    try:
        if decision == "approve":
            approve_item(
                item_id,
                actor=who,
                notes=notes.strip() or None,
                uow=uow,
                clock=clock,
                queue_publish=config.publish.enabled,
            )
        elif decision == "reject":
            if not notes.strip():
                return _review_error(back, "Thiếu lý do: từ chối thì phải ghi lý do.")
            reject_item(item_id, actor=who, reason=notes.strip(), uow=uow, clock=clock)
        elif decision == "publish":
            queue_publish(item_id, actor=who, uow=uow, enabled=config.publish.enabled)
        elif decision == "rewrite":
            if not notes.strip():
                return _review_error(
                    back,
                    "Thiếu lý do: lý do trả về được đưa vào prompt viết lại, "
                    "không để trống.",
                )
            send_back_for_rewrite(
                item_id, actor=who, reason=notes.strip(), uow=uow, clock=clock
            )
        else:
            raise HTTPException(status_code=400, detail=f"quyết định không hợp lệ: {decision}")
    except ItemNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DomainError as exc:
        return _review_error(back, f"Không ghi được quyết định: {exc}")
    return RedirectResponse(
        url=f"/review/{back}?decided={decision}#clips", status_code=303
    )


# ---------------- Lỗi ----------------


def _error_page(request: Request, title: str, detail: str, *, hint: str = "") -> HTMLResponse:
    """Trang lỗi nói việc gì sai và sửa thế nào.

    Không dùng HTTP 4xx cho những trường hợp này vì đây là kết quả nghiệp vụ hợp
    lệ (nguồn chưa duyệt, URL trùng) mà người dùng cần đọc, không phải lỗi giao thức.
    """
    return _render(request, "error.html", title=title, detail=detail, hint=hint)

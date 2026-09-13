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

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

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
    reject_item,
    send_back_for_rewrite,
)
from src.application.use_cases.write_script import load_transcript
from src.application.use_cases.submit_url import (
    ItemAlreadyExists,
    SourceNotDeclared,
    submit_url,
)
from src.domain.errors import DomainError
from src.domain.production.value_objects import ItemStage
from src.domain.sourcing.value_objects import (
    ApprovalStatus,
    ContentType,
    LicenseType,
    Platform,
    SourceKind,
)
from src.infrastructure.clock import SystemClock
from src.infrastructure.db.uow import SqlUnitOfWork
from src.interfaces.api.deps import get_clock, get_config, get_uow
from src.shared.config import Settings

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

router = APIRouter(prefix="/web", tags=["web"], include_in_schema=False)

Uow = Annotated[SqlUnitOfWork, Depends(get_uow)]
Clock = Annotated[SystemClock, Depends(get_clock)]
Config = Annotated[Settings, Depends(get_config)]

# Thứ tự các bước để hiện trên dashboard — theo đúng dòng chảy pipeline, không
# theo thứ tự chữ cái, để người xem đọc được nghẽn đang ở đâu.
PIPELINE_ORDER = [
    ItemStage.INBOX,
    ItemStage.DOWNLOADED,
    ItemStage.SEPARATED,
    ItemStage.TRANSCRIBED,
    ItemStage.TRANSCRIPT_REVIEW,
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


def _render(request: Request, template: str, **ctx) -> HTMLResponse:
    """Chữ ký mới của Starlette: request là tham số ĐẦU TIÊN.

    Chữ ký cũ ``TemplateResponse(name, {"request": ...})`` đã deprecated và sẽ bị
    bỏ — gom vào một hàm để lần sau đổi chỉ sửa một chỗ.
    """
    return TEMPLATES.TemplateResponse(request, template, ctx)


# ---------------- Dashboard ----------------


@router.get("", response_class=HTMLResponse)
def dashboard(request: Request, uow: Uow):
    with uow:
        counts = uow.items.count_by_stage()
        pending_sources = len(uow.sources.list_by_status(ApprovalStatus.PENDING, limit=500))
        approved_sources = len(uow.sources.list_by_status(ApprovalStatus.APPROVED, limit=500))
    queue = list_review_queue(uow=uow, limit=200)

    # Tổng công duyệt đang chờ: đây là ràng buộc thật của hệ thống này — không
    # phải tiền mà là thời gian người.
    review_minutes = sum(e.expected_minutes[1] for e in queue)

    return _render(
        request,
        "dashboard.html",
        title="Bảng điều khiển",
        pipeline=[(s, counts.get(s, 0)) for s in PIPELINE_ORDER],
        blocked=[(s, counts.get(s, 0)) for s in BLOCKED_STAGES],
        pending_sources=pending_sources,
        approved_sources=approved_sources,
        review_count=len(queue),
        review_minutes=review_minutes,
    )


# ---------------- Nguồn ----------------


@router.get("/sources", response_class=HTMLResponse)
def sources_page(request: Request, uow: Uow, status: str = "pending"):
    try:
        wanted = ApprovalStatus(status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"trạng thái không hợp lệ: {status}") from exc
    with uow:
        sources = uow.sources.list_by_status(wanted, limit=200)
    return _render(
        request,
        "sources.html",
        title="Nguồn đã khai báo",
        sources=sources,
        status=wanted,
        statuses=list(ApprovalStatus),
        platforms=list(Platform),
        kinds=list(SourceKind),
        content_types=list(ContentType),
        license_types=list(LicenseType),
    )


@router.post("/sources", response_class=HTMLResponse)
def declare(
    request: Request,
    uow: Uow,
    url: Annotated[str, Form()],
    platform: Annotated[Platform, Form()],
    kind: Annotated[SourceKind, Form()],
    actor: Annotated[str, Form()],
    audio_lang: Annotated[str, Form()] = "en",
    external_owner_id: Annotated[str, Form()] = "",
    display_name: Annotated[str, Form()] = "",
    topics: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
):
    try:
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
            actor=actor.strip() or "web",
        )
    except (SourceAlreadyDeclared, DomainError) as exc:
        return _error_page(request, "Không khai báo được nguồn", str(exc))
    return RedirectResponse(url="/web/sources?status=pending", status_code=303)


@router.post("/sources/{source_id}/approve", response_class=HTMLResponse)
def approve_source_form(
    request: Request,
    source_id: int,
    uow: Uow,
    clock: Clock,
    actor: Annotated[str, Form()],
    license_type: Annotated[LicenseType, Form()],
    evidence_ref: Annotated[str, Form()],
    attribution_text: Annotated[str, Form()] = "",
    may_translate: Annotated[bool, Form()] = False,
    may_modify_audio: Annotated[bool, Form()] = False,
    may_subtitle: Annotated[bool, Form()] = False,
    may_republish: Annotated[bool, Form()] = False,
    may_commercial_use: Annotated[bool, Form()] = False,
):
    try:
        approve_source(
            ApproveSourceCommand(
                source_id=source_id,
                actor=actor.strip(),
                license_type=license_type,
                evidence_ref=evidence_ref.strip(),
                attribution_text=attribution_text.strip() or None,
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
    return RedirectResponse(url="/web/sources?status=approved", status_code=303)


# ---------------- Hộp thư URL ----------------


@router.post("/items", response_class=HTMLResponse)
def submit(
    request: Request,
    uow: Uow,
    clock: Clock,
    url: Annotated[str, Form()],
    actor: Annotated[str, Form()] = "web",
):
    try:
        result = submit_url(url.strip(), uow=uow, clock=clock, actor=actor.strip() or "web")
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
    return RedirectResponse(url="/web", status_code=303)


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
            except Exception:  # noqa: BLE001 — thiếu file là trạng thái hợp lệ để hiện
                text = ""
            rows.append(
                {
                    "item": item,
                    "lang": source.audio_lang.code if source else "?",
                    "needs_extra": source.audio_lang.needs_extra_review if source else False,
                    "text": text,
                }
            )
    return _render(request, "transcripts.html", title="Soát transcript", rows=rows)


@router.post("/transcripts/{item_id}/approve", response_class=HTMLResponse)
def transcript_approve(
    request: Request, item_id: int, uow: Uow, actor: Annotated[str, Form()]
):
    who = actor.strip()
    if not who:
        return _error_page(request, "Thiếu tên người soát", "Ai soát phải được ghi lại.")
    try:
        approve_transcript(item_id, actor=who, uow=uow)
    except DomainError as exc:
        return _error_page(request, "Không ghi được", str(exc))
    return RedirectResponse(url="/web/transcripts", status_code=303)


# ---------------- Hàng đợi duyệt ----------------


@router.get("/review", response_class=HTMLResponse)
def review_queue(request: Request, uow: Uow):
    entries = list_review_queue(uow=uow, limit=100)
    return _render(request, "review_queue.html", title="Chờ duyệt", entries=entries)


@router.get("/review/{item_id}", response_class=HTMLResponse)
def review_detail(request: Request, item_id: int, uow: Uow):
    with uow:
        item = uow.items.get(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"không có item #{item_id}")
        source = uow.sources.get(item.source_id)
    return _render(
        request,
        "review_item.html",
        title=f"Duyệt item #{item_id}",
        item=item,
        source=source,
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
    actor: Annotated[str, Form()],
    notes: Annotated[str, Form()] = "",
):
    who = actor.strip()
    if not who:
        return _error_page(request, "Thiếu tên người duyệt", "Ai duyệt phải được ghi lại.")
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
                return _error_page(request, "Thiếu lý do", "Từ chối thì phải ghi lý do.")
            reject_item(item_id, actor=who, reason=notes.strip(), uow=uow, clock=clock)
        elif decision == "rewrite":
            if not notes.strip():
                return _error_page(
                    request,
                    "Thiếu lý do",
                    "Lý do trả về được đưa vào prompt viết lại — không để trống.",
                )
            send_back_for_rewrite(
                item_id, actor=who, reason=notes.strip(), uow=uow, clock=clock
            )
        else:
            raise HTTPException(status_code=400, detail=f"quyết định không hợp lệ: {decision}")
    except ItemNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DomainError as exc:
        return _error_page(request, "Không ghi được quyết định", str(exc))
    return RedirectResponse(url="/web/review", status_code=303)


# ---------------- Lỗi ----------------


def _error_page(request: Request, title: str, detail: str, *, hint: str = "") -> HTMLResponse:
    """Trang lỗi nói việc gì sai và sửa thế nào.

    Không dùng HTTP 4xx cho những trường hợp này vì đây là kết quả nghiệp vụ hợp
    lệ (nguồn chưa duyệt, URL trùng) mà người dùng cần đọc, không phải lỗi giao thức.
    """
    return _render(request, "error.html", title=title, detail=detail, hint=hint)

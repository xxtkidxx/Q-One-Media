"""Đăng nhập bằng session, quản lý tài khoản và RBAC cho web nội bộ."""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from starlette.middleware.sessions import SessionMiddleware

from src.domain.access import Role
from src.infrastructure.db.orm import AuditLogRow, UserAccountRow
from src.interfaces.api.deps import get_uow
from src.shared.config import Settings

router = APIRouter(tags=["authentication"], include_in_schema=False)

DEV_ACCOUNTS = (
    ("admin", "Quản trị viên", Role.ADMIN),
    ("editor", "Biên tập viên", Role.EDITOR),
    ("reviewer", "Người duyệt", Role.REVIEWER),
    ("viewer", "Người xem", Role.VIEWER),
)


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"pbkdf2_sha256$310000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_hex, expected_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds)
        )
        return hmac.compare_digest(actual.hex(), expected_hex)
    except (ValueError, TypeError):
        return False


def seed_accounts(settings: Settings) -> None:
    """Tạo bộ tài khoản mẫu ở dev hoặc admin bootstrap lần đầu ở production."""
    uow = get_uow()
    with uow:
        if uow.session.scalar(select(UserAccountRow.id).limit(1)) is not None:
            return
        accounts = DEV_ACCOUNTS if settings.app_env == "dev" else ()
        if settings.app_env == "prod" and settings.web.enabled:
            accounts = ((settings.web.user, "Quản trị viên", Role.ADMIN),)
        for username, display_name, role in accounts:
            uow.session.add(
                UserAccountRow(
                    username=username,
                    display_name=display_name,
                    password_hash=hash_password(
                        username if settings.app_env == "dev" else settings.web.password
                    ),
                    role=role.value,
                )
            )
        uow.commit()


def install_auth(app, settings: Settings) -> None:
    """Bảo vệ toàn bộ UI/API; health và trang đăng nhập luôn mở."""

    @app.middleware("http")
    async def require_session(request: Request, call_next):
        path = request.url.path
        if path in ("/healthz", "/readyz", "/login") or path.startswith("/static/"):
            return await call_next(request)

        user_id = request.session.get("user_id")
        user = None
        if user_id:
            uow = get_uow()
            with uow:
                user = uow.session.get(UserAccountRow, user_id)
                if user and not user.active:
                    user = None
        if user is None:
            request.session.clear()
            if path.startswith("/api/"):
                return JSONResponse({"error": "Cần đăng nhập"}, status_code=401)
            return RedirectResponse(f"/login?next={path}", status_code=303)

        request.state.user = user
        required = _required_role(request.method, path)
        if required and not Role(user.role).permits(required):
            if path.startswith("/api/"):
                return JSONResponse({"error": "Không đủ quyền"}, status_code=403)
            return HTMLResponse("Bạn không có quyền thực hiện thao tác này.", status_code=403)
        return await call_next(request)

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.web.session_secret,
        session_cookie="qone_session",
        same_site="lax",
        https_only=settings.is_prod,
        max_age=8 * 60 * 60,
    )


def _required_role(method: str, path: str) -> Role | None:
    if method == "GET":
        return Role.ADMIN if path in ("/accounts", "/audit") else Role.VIEWER
    if path == "/logout":
        return Role.VIEWER
    if path.startswith("/accounts"):
        return Role.ADMIN
    if "/approve" in path or path.startswith("/review/") or path.startswith("/transcripts/"):
        return Role.REVIEWER
    return Role.EDITOR


def _audit(action: str, user: UserAccountRow, detail: dict | None = None) -> None:
    uow = get_uow()
    with uow:
        uow.session.add(
            AuditLogRow(
                entity="user",
                entity_id=user.id,
                action=action,
                actor=user.username,
                detail=detail,
                created_at=datetime.now(UTC),
            )
        )
        uow.commit()


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/"):
    from src.interfaces.web.routes import TEMPLATES

    return TEMPLATES.TemplateResponse(
        request,
        "login.html",
        {
            "title": "Đăng nhập",
            "next": next if next.startswith("/") and not next.startswith("//") else "/",
            "error": request.query_params.get("error"),
            "dev_accounts": (
                DEV_ACCOUNTS if request.app.state.settings.app_env == "dev" else ()
            ),
        },
    )


@router.post("/login")
def login(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next: Annotated[str, Form()] = "/",
):
    uow = get_uow()
    with uow:
        user = uow.session.scalar(
            select(UserAccountRow).where(UserAccountRow.username == username.strip().lower())
        )
    if user is None or not user.active or not verify_password(password, user.password_hash):
        return RedirectResponse("/login?error=1", status_code=303)
    request.session["user_id"] = user.id
    _audit("login", user)
    target = next if next.startswith("/") and not next.startswith("//") else "/"
    return RedirectResponse(target, status_code=303)


@router.post("/logout")
def logout(request: Request):
    user = request.state.user
    _audit("logout", user)
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/accounts", response_class=HTMLResponse)
def accounts(request: Request):
    from src.interfaces.web.routes import TEMPLATES

    uow = get_uow()
    with uow:
        users = list(uow.session.scalars(select(UserAccountRow).order_by(UserAccountRow.id)))
    return TEMPLATES.TemplateResponse(
        request, "accounts.html", {"title": "Tài khoản", "users": users, "roles": list(Role)}
    )


@router.post("/accounts")
def create_account(
    request: Request,
    username: Annotated[str, Form()],
    display_name: Annotated[str, Form()],
    password: Annotated[str, Form()],
    role: Annotated[str, Form()],
):
    clean = username.strip().lower()
    if not clean or len(password) < 8:
        raise HTTPException(422, "Tên đăng nhập không được trống; mật khẩu ít nhất 8 ký tự")
    parsed_role = Role(role)
    uow = get_uow()
    with uow:
        if uow.session.scalar(select(UserAccountRow.id).where(UserAccountRow.username == clean)):
            raise HTTPException(409, "Tên đăng nhập đã tồn tại")
        user = UserAccountRow(
            username=clean,
            display_name=display_name.strip() or clean,
            password_hash=hash_password(password),
            role=parsed_role.value,
        )
        uow.session.add(user)
        uow.session.flush()
        user_id = user.id
        uow.commit()
    _audit("account_created", request.state.user, {"user_id": user_id, "role": role})
    return RedirectResponse("/accounts?created=1", status_code=303)


@router.post("/accounts/{user_id}")
def update_account(
    request: Request,
    user_id: int,
    display_name: Annotated[str, Form()],
    role: Annotated[str, Form()],
    active: Annotated[str | None, Form()] = None,
    password: Annotated[str, Form()] = "",
):
    if request.state.user.id == user_id and active is None:
        raise HTTPException(422, "Không thể tự khóa tài khoản đang đăng nhập")
    uow = get_uow()
    with uow:
        user = uow.session.get(UserAccountRow, user_id)
        if user is None:
            raise HTTPException(404, "Không tìm thấy tài khoản")
        user.display_name = display_name.strip() or user.username
        user.role = Role(role).value
        user.active = active is not None
        if password:
            if len(password) < 8:
                raise HTTPException(422, "Mật khẩu ít nhất 8 ký tự")
            user.password_hash = hash_password(password)
        uow.commit()
    _audit("account_updated", request.state.user, {"user_id": user_id, "role": role})
    return RedirectResponse("/accounts?updated=1", status_code=303)


@router.get("/audit", response_class=HTMLResponse)
def audit_page(request: Request, page: int = 1):
    from src.interfaces.web.routes import TEMPLATES

    page = max(page, 1)
    uow = get_uow()
    with uow:
        rows = list(
            uow.session.scalars(
                select(AuditLogRow)
                .order_by(AuditLogRow.created_at.desc(), AuditLogRow.id.desc())
                .offset((page - 1) * 50)
                .limit(50)
            )
        )
    return TEMPLATES.TemplateResponse(
        request, "audit.html", {"title": "Nhật ký audit", "rows": rows, "page": page}
    )

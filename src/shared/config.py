"""Config đọc một lần từ biến môi trường. Không ``os.getenv`` rải rác trong code.

Chú ý về guardrail: ở đây **không có** cờ bật/tắt license gate hay gate duyệt
của người. Hai thứ đó là bất biến của tầng domain (xem
``domain/sourcing/clearance.py``), không phải cấu hình — một cờ có thể đặt
``false`` chính là đường tắt mà quy tắc nghiệp vụ cấm.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from src.shared.paths import MediaPaths


def _env(name: str, default: str | None = None) -> str:
    v = os.environ.get(name, default)
    if v is None:
        raise ConfigError(f"thiếu biến môi trường bắt buộc: {name}")
    return v


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} phải là số nguyên, nhận {raw!r}") from exc


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class ConfigError(RuntimeError):
    """Cấu hình sai hoặc thiếu — không retry được, phải sửa môi trường."""


@dataclass(frozen=True)
class LLMSettings:
    api_key: str
    model: str = "claude-sonnet-5"
    model_hard: str = "claude-opus-5"


@dataclass(frozen=True)
class TTSSettings:
    engine: str = "voxcpm"
    voice_ref: str | None = None
    fptai_api_key: str | None = None


@dataclass(frozen=True)
class PublishSettings:
    """``enabled=False`` là kill-switch an toàn: chỉ chặn thêm, không mở thêm."""

    enabled: bool = False
    youtube_client_secret_file: str | None = None
    youtube_token_file: str | None = None
    fb_page_id: str | None = None
    fb_page_access_token: str | None = None


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_url: str
    media_root: Path
    model_cache: Path
    log_level: str
    worker_concurrency: int
    gpu_count: int
    llm: LLMSettings
    tts: TTSSettings
    publish: PublishSettings
    paths: MediaPaths = field(init=False)

    def __post_init__(self) -> None:
        if self.app_env not in ("dev", "prod", "test"):
            raise ConfigError(f"APP_ENV phải là dev|prod|test, nhận {self.app_env!r}")
        object.__setattr__(self, "paths", MediaPaths(self.media_root))

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"


def load_settings() -> Settings:
    return Settings(
        app_env=_env("APP_ENV", "dev"),
        database_url=_env("DATABASE_URL"),
        media_root=Path(_env("MEDIA_ROOT", "/data/media")),
        model_cache=Path(_env("MODEL_CACHE", "/models")),
        log_level=_env("LOG_LEVEL", "INFO").upper(),
        worker_concurrency=_env_int("WORKER_CONCURRENCY", 1),
        gpu_count=_env_int("GPU_COUNT", 0),
        llm=LLMSettings(
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            model=_env("LLM_MODEL", "claude-sonnet-5"),
            model_hard=_env("LLM_MODEL_HARD", "claude-opus-5"),
        ),
        tts=TTSSettings(
            engine=_env("TTS_ENGINE", "voxcpm"),
            voice_ref=os.environ.get("VOXCPM_VOICE_REF") or None,
            fptai_api_key=os.environ.get("FPTAI_API_KEY") or None,
        ),
        publish=PublishSettings(
            enabled=_env_bool("PUBLISH_ENABLED", False),
            youtube_client_secret_file=os.environ.get("YOUTUBE_CLIENT_SECRET_FILE") or None,
            youtube_token_file=os.environ.get("YOUTUBE_TOKEN_FILE") or None,
            fb_page_id=os.environ.get("FB_PAGE_ID") or None,
            fb_page_access_token=os.environ.get("FB_PAGE_ACCESS_TOKEN") or None,
        ),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Đọc một lần cho cả tiến trình. Test cần đổi thì gọi ``get_settings.cache_clear()``."""
    return load_settings()

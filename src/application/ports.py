"""Port của tầng application — cái mà thế giới bên ngoài phải cung cấp.

Tầng này định nghĩa *hình dạng* của hạ tầng, hạ tầng hiện thực theo. Nhờ vậy
use case test được bằng fake, không cần Postgres, không cần GPU, không cần token.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from src.domain.authoring.repository import SeriesRepository
from src.domain.production.repository import ItemRepository
from src.domain.publishing.repository import PublicationRepository
from src.domain.publishing.value_objects import PublishPlatform, VideoMetadata
from src.domain.scheduling.repository import JobRepository
from src.domain.sourcing.clearance import (
    DownloadClearance,
    DubbingClearance,
    PublishClearance,
)
from src.domain.sourcing.repository import SourceRepository


class Clock(Protocol):
    """Thời gian là phụ thuộc, không phải hàm toàn cục.

    Nhờ đó test hạn license và hạn mức ngày không phải chờ thật.
    """

    def now(self) -> datetime: ...


class AuditLog(Protocol):
    """Vết thao tác trên quyết định license và duyệt nội dung.

    Không chỉ để debug: đây là bằng chứng quy trình nếu có tranh chấp bản quyền.
    """

    def record(
        self,
        *,
        entity: str,
        entity_id: int,
        action: str,
        actor: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None: ...


class UnitOfWork(Protocol):
    """Một transaction, nhiều repository.

    Dùng như context manager. Thoát mà không ``commit()`` thì rollback — mặc
    định an toàn, quên commit thì mất dữ liệu chứ không lưu nửa vời.
    """

    sources: SourceRepository
    items: ItemRepository
    publications: PublicationRepository
    jobs: JobRepository
    series: SeriesRepository
    audit: AuditLog

    def __enter__(self) -> UnitOfWork: ...

    def __exit__(self, *exc: object) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


# ---------------- Gateway ra thế giới bên ngoài ----------------


class DownloadResult(Protocol):
    path: Path
    duration_sec: int | None
    width: int | None
    height: int | None
    external_id: str | None
    title: str | None


class VideoDownloader(Protocol):
    """Tải video về đĩa.

    Chữ ký **bắt buộc có ``clearance``**: không tồn tại đường gọi nào tải được
    video mà chưa qua license gate.
    """

    def download(
        self, *, url: str, clearance: DownloadClearance, dest_dir: Path
    ) -> DownloadResult: ...


class SpeechSynthesizer(Protocol):
    """Sinh giọng tiếng Việt. VoxCPM2 là mặc định; FPT.AI dự phòng cùng interface."""

    def synthesize(
        self, *, text: str, dest: Path, clearance: DubbingClearance, voice_ref: Path | None = None
    ) -> Path: ...

    def measured_rate(self) -> float | None:
        """Tốc độ đọc đo được (âm tiết/giây), ``None`` nếu chưa đo (G0.7)."""
        ...


class PublishResult(Protocol):
    remote_id: str
    remote_url: str | None


class VideoPublisher(Protocol):
    """Một nền tảng đăng bài. Mỗi nền tảng một adapter, cùng interface này."""

    platform: PublishPlatform

    def publish(
        self,
        *,
        video: Path,
        metadata: VideoMetadata,
        clearance: PublishClearance,
    ) -> PublishResult: ...


class SegmentAdvisor(Protocol):
    """LLM đề xuất đoạn nên dùng. **Đề xuất**, người chọn."""

    def propose(
        self, *, transcript: str, duration_sec: int, max_proposals: int = 3
    ) -> list[tuple[float, float, str]]: ...


class ScriptWriter(Protocol):
    """Viết kịch bản tiếng Việt — viết lại, không dịch từng chữ."""

    def write(
        self,
        *,
        transcript: str,
        segment: tuple[float, float],
        max_syllables: int,
        glossary: dict[str, str],
        previous_attempt: str | None = None,
        rewrite_reason: str | None = None,
    ) -> str: ...


class PromptScriptWriter(Protocol):
    """Giai đoạn 2: viết kịch bản từ **đề bài của người dùng**, không từ transcript.

    Tách khỏi ``ScriptWriter`` vì đầu vào khác bản chất: ở đó là lời của người
    khác cần viết lại, ở đây là yêu cầu nội dung của chính NMI.
    """

    def write_from_prompt(
        self,
        *,
        brief: str,
        title: str,
        max_syllables: int,
        glossary: dict[str, str],
    ) -> str: ...


class ImageGenerator(Protocol):
    """Sinh ảnh minh hoạ theo prompt. Trả đường dẫn tương đối, hoặc ``None``.

    ``None`` là câu trả lời hợp lệ: chưa cấu hình nhà cung cấp thì cảnh đó rơi về
    thẻ thương hiệu, pipeline không dừng.
    """

    def generate(self, *, prompt: str, out_dir: Path, name: str) -> str | None: ...

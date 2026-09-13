"""Adapter yt-dlp: đọc metadata và tải video.

**Vì sao tự viết thay vì vendor ``core/_1_ytdlp.py`` của VideoLingo** — đọc code
upstream rồi mới quyết định, và có ba lý do cụ thể:

1. Hàm ``update_ytdlp()`` của họ chạy ``pip install --upgrade yt-dlp`` **mỗi
   lần tải**. Trong container thì đó là phụ thuộc mạng lúc chạy, build không
   lặp lại được, và một lần upstream đổi API là vỡ giữa production.
2. Nó ghi ``input_manifest.json`` vào một thư mục ``output/`` toàn cục và tìm
   file bằng ``glob``, rồi ném lỗi nếu thấy nhiều hơn một video. Hai item chạy
   song song sẽ đè nhau.
3. Nó đọc cấu hình qua ``load_key()`` gắn cứng vào ``config.yaml`` ở thư mục
   làm việc — không ghép được với ``src/shared/config.py``.

Phần thật sự có giá trị ở VideoLingo là các bước ASR, tách nhạc và alignment;
bước tải thì tự viết rẻ hơn là bọc adapter quanh ba vấn đề trên.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.domain.sourcing.clearance import DownloadClearance
from src.shared.logging import get_logger

log = get_logger(__name__)


class DownloadFailed(RuntimeError):
    """Tải thất bại vì lý do kỹ thuật — retry được."""

    retryable = True


class MediaUnavailable(RuntimeError):
    """Video đã bị xoá, riêng tư, hoặc chặn theo vùng — retry vô nghĩa."""

    retryable = False


# Thông báo lỗi của yt-dlp cho biết thất bại là vĩnh viễn, không phải tạm thời.
_PERMANENT_MARKERS = (
    "video unavailable",
    "private video",
    "has been removed",
    "is not available in your country",
    "account associated with this video has been terminated",
    "sign in to confirm your age",
)


def _classify(exc: Exception) -> Exception:
    msg = str(exc).lower()
    if any(m in msg for m in _PERMANENT_MARKERS):
        return MediaUnavailable(str(exc))
    return DownloadFailed(str(exc))


@dataclass(frozen=True, slots=True)
class YtDlpDownloadResult:
    path: Path
    duration_sec: int | None
    width: int | None
    height: int | None
    external_id: str | None
    title: str | None


class YtDlpProbe:
    """Đọc metadata mà không tải media — dùng để xác minh chủ sở hữu.

    Rẻ có chủ ý: xác minh quyền sở hữu phải không tốn băng thông, để không bao
    giờ có lý do kỹ thuật nào biện minh cho việc bỏ qua nó.
    """

    def __init__(self, *, cookies_file: Path | None = None) -> None:
        self._cookies = cookies_file

    def probe(self, url: str) -> dict[str, Any]:
        from yt_dlp import YoutubeDL

        opts: dict[str, Any] = {"quiet": True, "no_warnings": True, "skip_download": True}
        if self._cookies and self._cookies.exists():
            opts["cookiefile"] = str(self._cookies)
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as exc:
            raise _classify(exc) from exc
        return dict(info or {})


class YtDlpDownloader:
    """Tải video. Chữ ký đòi ``DownloadClearance`` nên không gọi được khi chưa qua gate."""

    def __init__(
        self,
        *,
        max_height: int = 1080,
        cookies_file: Path | None = None,
        socket_timeout: int = 30,
    ) -> None:
        self._max_height = max_height
        self._cookies = cookies_file
        self._socket_timeout = socket_timeout

    def download(
        self, *, url: str, clearance: DownloadClearance, dest_dir: Path
    ) -> YtDlpDownloadResult:
        from yt_dlp import YoutubeDL

        dest_dir.mkdir(parents=True, exist_ok=True)

        # Tên file cố định thay vì %(title)s: tiêu đề tiếng Trung/Nhật và emoji
        # làm vỡ đường dẫn trên Windows, và VideoLingo phải tự sanitize chính vì
        # thế. Id item đã nằm trong tên thư mục nên không cần tiêu đề ở tên file.
        opts: dict[str, Any] = {
            "format": (
                f"bestvideo[height<={self._max_height}]+bestaudio/"
                f"best[height<={self._max_height}]/best"
            ),
            "outtmpl": str(dest_dir / "video.%(ext)s"),
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": self._socket_timeout,
            "retries": 3,
            "concurrent_fragment_downloads": 4,
        }
        if self._cookies and self._cookies.exists():
            opts["cookiefile"] = str(self._cookies)

        log.info(
            "ytdlp.download.start",
            platform=clearance.platform,
            source_id=clearance.source_id,
            urgent=clearance.url_expires_fast,
        )
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as exc:
            raise _classify(exc) from exc

        info = dict(info or {})
        path = self._find_output(dest_dir)
        log.info("ytdlp.download.done", path=str(path), bytes=path.stat().st_size)
        return YtDlpDownloadResult(
            path=path,
            duration_sec=int(info["duration"]) if info.get("duration") else None,
            width=info.get("width"),
            height=info.get("height"),
            external_id=str(info.get("id")) if info.get("id") else None,
            title=info.get("title"),
        )

    @staticmethod
    def _find_output(dest_dir: Path) -> Path:
        """Tìm file vừa tải trong **thư mục riêng của item**.

        Mỗi item một thư mục nên ở đây chỉ có một file media — khác với cách
        ``glob`` cả thư mục ``output/`` chung của upstream.
        """
        candidates = sorted(
            (p for p in dest_dir.glob("video.*") if p.suffix.lower() != ".part"),
            key=lambda p: p.stat().st_size,
            reverse=True,
        )
        if not candidates:
            raise DownloadFailed(f"yt-dlp báo thành công nhưng không có file trong {dest_dir}")
        return candidates[0]

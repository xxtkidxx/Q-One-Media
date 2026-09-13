"""Adapter YouTube Data API v3.

Hạn mức đã xác minh (F2.7): ``videos.insert`` có **bucket quota riêng — 1 unit
mỗi lần gọi, tối đa 100 lần/ngày**. Con số "1.600 units mỗi upload" từng phổ biến
đã lạc hậu; nếu ai đó tính lại ngân sách theo số cũ thì sẽ kết luận sai rằng chỉ
đăng được 6 video/ngày.

Upload dùng chế độ resumable: file short video 30–80 MB qua mạng Việt Nam đủ lâu
để một lần đứt kết nối là phải tải lại từ đầu nếu không resumable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.domain.publishing.value_objects import PublishPlatform, VideoMetadata
from src.domain.sourcing.clearance import PublishClearance
from src.shared.logging import get_logger

log = get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB: đủ lớn để nhanh, đủ nhỏ để retry không đau

# YouTube giới hạn 500 ký tự mỗi tag và 5.000 ký tự cho cả danh sách tag.
MAX_DESCRIPTION = 5000


class PublishFailed(RuntimeError):
    retryable = True


class PublishRejected(RuntimeError):
    retryable = False


@dataclass(frozen=True, slots=True)
class YouTubeResult:
    remote_id: str
    remote_url: str | None


class YouTubePublisher:
    """Hiện thực port ``VideoPublisher``."""

    platform = PublishPlatform.YOUTUBE

    def __init__(
        self,
        *,
        client_secret_file: Path,
        token_file: Path,
        privacy_status: str = "private",
        category_id: str = "28",  # Science & Technology
    ) -> None:
        self._client_secret = client_secret_file
        self._token_file = token_file
        # Mặc định ``private`` có chủ ý: mỗi video đã qua người duyệt nội dung,
        # nhưng bước cuối cùng cho công khai nên là một hành động có ý thức của
        # người vận hành, không phải mặc định của code.
        self._privacy = privacy_status
        self._category = category_id

    # ---------------- OAuth ----------------

    def _credentials(self) -> Any:
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
        except ImportError as exc:
            raise PublishRejected("chưa cài google-auth") from exc

        if not self._token_file.exists():
            raise PublishRejected(
                f"chưa có token OAuth tại {self._token_file} — chạy "
                "scripts/youtube_authorize.py một lần trên máy có trình duyệt (G3.1)"
            )
        creds = Credentials.from_authorized_user_file(str(self._token_file), SCOPES)
        if creds.expired and creds.refresh_token:
            # Refresh im lặng là đúng: token Google hết hạn sau 1 giờ, còn refresh
            # token thì lâu dài. Không refresh thì mọi job sau giờ đầu đều lỗi.
            creds.refresh(Request())
            self._token_file.write_text(creds.to_json(), encoding="utf-8")
            log.info("youtube.token.refreshed")
        if not creds.valid:
            raise PublishRejected(
                "token OAuth không dùng được — cấp lại bằng scripts/youtube_authorize.py"
            )
        return creds

    def _service(self) -> Any:
        try:
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise PublishRejected("chưa cài google-api-python-client") from exc
        return build("youtube", "v3", credentials=self._credentials(), cache_discovery=False)

    # ---------------- Upload ----------------

    def publish(
        self,
        *,
        video: Path,
        metadata: VideoMetadata,
        clearance: PublishClearance,
    ) -> YouTubeResult:
        if not video.exists():
            raise PublishRejected(f"không có file {video}")

        try:
            from googleapiclient.errors import HttpError
            from googleapiclient.http import MediaFileUpload
        except ImportError as exc:
            raise PublishRejected("chưa cài google-api-python-client") from exc

        body = {
            "snippet": {
                "title": metadata.title,
                "description": self._build_description(metadata, clearance),
                "tags": list(metadata.tags),
                "categoryId": self._category,
                "defaultLanguage": "vi",
                "defaultAudioLanguage": "vi",
            },
            "status": {
                "privacyStatus": self._privacy,
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(
            str(video), chunksize=CHUNK_SIZE, resumable=True, mimetype="video/mp4"
        )
        log.info("youtube.upload.start", size=video.stat().st_size, privacy=self._privacy)
        try:
            request = self._service().videos().insert(
                part="snippet,status", body=body, media_body=media
            )
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    log.info("youtube.upload.progress", percent=int(status.progress() * 100))
        except HttpError as exc:
            status_code = getattr(getattr(exc, "resp", None), "status", None)
            # 403 quota exceeded và 429 là tạm thời; 400/401 là lỗi của ta.
            if status_code in (403, 429, 500, 503):
                raise PublishFailed(f"YouTube {status_code}: {exc}") from exc
            raise PublishRejected(f"YouTube {status_code}: {exc}") from exc
        except Exception as exc:
            raise PublishFailed(f"upload thất bại: {type(exc).__name__}: {exc}") from exc

        video_id = str(response.get("id") or "")
        if not video_id:
            raise PublishFailed(f"YouTube không trả id: {response}")
        log.info("youtube.upload.done", video_id=video_id)
        return YouTubeResult(
            remote_id=video_id, remote_url=f"https://www.youtube.com/watch?v={video_id}"
        )

    @staticmethod
    def _build_description(metadata: VideoMetadata, clearance: PublishClearance) -> str:
        """Ghép mô tả, ghi nguồn và nhãn AI.

        Nhãn giọng AI là yêu cầu công bố của nền tảng, không phải tuỳ chọn — và
        ghi nguồn là nghĩa vụ license với CC BY. Cả hai đặt ở đây để không có
        đường publish nào bỏ qua chúng.
        """
        parts = [metadata.description.strip()]
        if clearance.attribution_text:
            parts.append(clearance.attribution_text.strip())
        if metadata.ai_generated_voice:
            parts.append("Giọng đọc tổng hợp bằng AI.")
        text = "\n\n".join(p for p in parts if p)
        return text[:MAX_DESCRIPTION]

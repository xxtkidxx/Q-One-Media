"""Adapter Facebook Graph API — Reels lên Page.

Hai ràng buộc đã xác minh (F2.7) và cả hai đều là ràng buộc kiến trúc, không phải
chi tiết:

- **Reels chỉ publish được lên Page, không lên profile cá nhân.** Nên toàn bộ
  trách nhiệm pháp lý đổ về pháp nhân sở hữu Page.
- Cần ``pages_show_list`` + ``pages_read_engagement`` + ``pages_manage_posts``, và
  ``pages_manage_posts`` **không xin riêng được** vì nó kéo theo hai quyền kia.

Upload Reels là ba pha: ``start`` lấy upload session → ``upload`` đẩy nhị phân →
``finish`` để publish. Không phải một lần POST như video thường.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx

from src.domain.publishing.value_objects import PublishPlatform, VideoMetadata
from src.domain.sourcing.clearance import PublishClearance
from src.shared.logging import get_logger

log = get_logger(__name__)

GRAPH_VERSION = "v21.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"
RUPLOAD_BASE = f"https://rupload.facebook.com/video-upload/{GRAPH_VERSION}"

# Mô tả Reels dài hơn giới hạn thì Graph API cắt im lặng — cắt chủ động ở đây để
# biết trước là mất gì.
MAX_DESCRIPTION = 2200


class PublishFailed(RuntimeError):
    retryable = True


class PublishRejected(RuntimeError):
    retryable = False


@dataclass(frozen=True, slots=True)
class FacebookResult:
    remote_id: str
    remote_url: str | None


class FacebookReelsPublisher:
    """Hiện thực port ``VideoPublisher``."""

    platform = PublishPlatform.FACEBOOK

    def __init__(
        self,
        *,
        page_id: str,
        page_access_token: str,
        timeout_sec: float = 300.0,
        publish_immediately: bool = False,
    ) -> None:
        if not page_id or not page_access_token:
            raise PublishRejected("thiếu FB_PAGE_ID hoặc FB_PAGE_ACCESS_TOKEN")
        self._page_id = page_id
        self._token = page_access_token
        self._timeout = timeout_sec
        # Mặc định ``False`` → Reels ở trạng thái draft/scheduled thay vì công khai
        # ngay. Cùng lý do như YouTube: bước cho công khai nên là hành động có ý
        # thức của người vận hành.
        self._publish_immediately = publish_immediately

    def publish(
        self,
        *,
        video: Path,
        metadata: VideoMetadata,
        clearance: PublishClearance,
    ) -> FacebookResult:
        if not video.exists():
            raise PublishRejected(f"không có file {video}")
        size = video.stat().st_size

        with httpx.Client(timeout=self._timeout) as client:
            video_id = self._start_session(client)
            self._upload_binary(client, video_id, video, size)
            self._finish(client, video_id, metadata, clearance)

        log.info("facebook.reel.done", video_id=video_id)
        return FacebookResult(
            remote_id=video_id, remote_url=f"https://www.facebook.com/reel/{video_id}"
        )

    # ---------------- Ba pha ----------------

    def _start_session(self, client: httpx.Client) -> str:
        resp = self._post(
            client,
            f"{GRAPH_BASE}/{self._page_id}/video_reels",
            data={"upload_phase": "start", "access_token": self._token},
        )
        video_id = str(resp.get("video_id") or "")
        if not video_id:
            raise PublishFailed(f"Facebook không trả video_id ở pha start: {resp}")
        log.info("facebook.reel.session", video_id=video_id)
        return video_id

    def _upload_binary(
        self, client: httpx.Client, video_id: str, video: Path, size: int
    ) -> None:
        """Đẩy nhị phân lên rupload.facebook.com — host khác graph.facebook.com.

        Dùng sai host là lỗi hay gặp nhất ở bước này, và thông báo lỗi trả về
        không nói rõ nguyên nhân.
        """
        headers = {
            "Authorization": f"OAuth {self._token}",
            "offset": "0",
            "file_size": str(size),
            "Content-Type": "application/octet-stream",
        }
        log.info("facebook.reel.upload.start", size=size)
        try:
            with video.open("rb") as fh:
                resp = client.post(
                    f"{RUPLOAD_BASE}/{video_id}", headers=headers, content=fh.read()
                )
        except httpx.HTTPError as exc:
            raise PublishFailed(f"đẩy nhị phân thất bại: {exc}") from exc
        if resp.status_code >= 400:
            raise self._classify(resp.status_code, resp.text)
        if not resp.json().get("success", True):
            raise PublishFailed(f"Facebook báo upload không thành công: {resp.text[:200]}")

    def _finish(
        self,
        client: httpx.Client,
        video_id: str,
        metadata: VideoMetadata,
        clearance: PublishClearance,
    ) -> None:
        resp = self._post(
            client,
            f"{GRAPH_BASE}/{self._page_id}/video_reels",
            data={
                "upload_phase": "finish",
                "video_id": video_id,
                "video_state": "PUBLISHED" if self._publish_immediately else "DRAFT",
                "description": self._build_description(metadata, clearance),
                "access_token": self._token,
            },
        )
        if not resp.get("success", True):
            raise PublishFailed(f"pha finish thất bại: {resp}")

    # ---------------- Tiện ích ----------------

    def _post(self, client: httpx.Client, url: str, *, data: dict[str, str]) -> dict:
        try:
            resp = client.post(url, data=data)
        except httpx.HTTPError as exc:
            raise PublishFailed(f"gọi Graph API thất bại: {exc}") from exc
        if resp.status_code >= 400:
            raise self._classify(resp.status_code, resp.text)
        return resp.json()

    @staticmethod
    def _classify(status: int, body: str) -> Exception:
        """Phân loại lỗi Graph API.

        190 (token hết hạn) và 200 (thiếu quyền) là lỗi cấu hình — retry vô nghĩa
        và chỉ làm nhiễu log. Còn 4/17/32 là rate limit, xếp lại được.
        """
        snippet = body[:300]
        if status in (401, 403) or '"code":190' in body or '"code":200' in body:
            return PublishRejected(
                f"Facebook từ chối quyền ({status}): {snippet}\n"
                "Kiểm pages_manage_posts + pages_read_engagement + pages_show_list, "
                "và xem mục ngoại lệ App Review cho app nội bộ (F2.7)."
            )
        if status == 429 or '"code":4' in body or '"code":17' in body or '"code":32' in body:
            return PublishFailed(f"Facebook rate limit ({status}): {snippet}")
        if status >= 500:
            return PublishFailed(f"Facebook lỗi server ({status}): {snippet}")
        return PublishRejected(f"Facebook {status}: {snippet}")

    @staticmethod
    def _build_description(metadata: VideoMetadata, clearance: PublishClearance) -> str:
        parts = [metadata.description.strip()]
        if clearance.attribution_text:
            parts.append(clearance.attribution_text.strip())
        if metadata.ai_generated_voice:
            parts.append("Giọng đọc tổng hợp bằng AI.")
        if metadata.tags:
            parts.append(" ".join(f"#{t.replace(' ', '')}" for t in metadata.tags[:8]))
        return "\n\n".join(p for p in parts if p)[:MAX_DESCRIPTION]

"""Adapter TikTok Content Posting API — upload trực tiếp file video.

Ba ràng buộc của nền tảng, và cả ba đều đổi cách dùng chứ không chỉ là chi tiết:

- **Client chưa qua audit bị khoá ở ``SELF_ONLY``**: video đăng lên chỉ chính chủ
  tài khoản xem được, và mỗi 24 giờ chỉ đăng được cho một số ít tài khoản. Vì vậy
  trước khi TikTok audit xong, adapter này dùng để **kiểm chứng đường đi**, không
  phải để phát hành.
- **Quyền hiển thị phải do người đăng chọn trong app** với client chưa audit: ta
  gửi ``privacy_level`` hợp lệ theo danh sách mà chính API trả về (endpoint
  ``creator_info``), chứ không đoán — đoán sai thì API từ chối cả lần đăng.
- **Nguồn có watermark dán cứng thì không đăng TikTok.** Quy tắc đó nằm ở
  ``domain/publishing/policy.py`` và chặn trước khi tới đây; adapter không tự
  quyết định gì về chuyện đó.

Luồng: ``creator_info/query`` (lấy quyền hiển thị hợp lệ) → ``video/init``
(lấy ``upload_url`` + ``publish_id``) → PUT nhị phân theo ``Content-Range`` →
``status/fetch`` để biết TikTok đã nhận xong chưa.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx

from src.domain.publishing.value_objects import PublishPlatform, VideoMetadata
from src.domain.sourcing.clearance import PublishClearance
from src.shared.logging import get_logger

log = get_logger(__name__)

API_BASE = "https://open.tiktokapis.com/v2"
MAX_TITLE = 2200
# TikTok yêu cầu chunk >= 5 MB (trừ chunk cuối) và <= 64 MB.
CHUNK_SIZE = 10 * 1024 * 1024


class PublishFailed(RuntimeError):
    retryable = True


class PublishRejected(RuntimeError):
    retryable = False


@dataclass(frozen=True, slots=True)
class TikTokResult:
    remote_id: str
    remote_url: str | None


class TikTokPublisher:
    """Hiện thực port ``VideoPublisher``."""

    platform = PublishPlatform.TIKTOK

    def __init__(
        self,
        *,
        access_token: str,
        timeout_sec: float = 300.0,
        privacy_level: str = "SELF_ONLY",
    ) -> None:
        if not access_token:
            raise PublishRejected("thiếu TIKTOK_ACCESS_TOKEN")
        self._token = access_token
        self._timeout = timeout_sec
        # Mặc định SELF_ONLY, không phải PUBLIC_TO_EVERYONE: client chưa audit chỉ
        # được phép mức này, và ngay cả khi đã audit thì cho công khai vẫn nên là
        # một hành động có ý thức của người vận hành (cùng lối với YouTube/Facebook).
        self._privacy_level = privacy_level

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def publish(
        self, *, video: Path, metadata: VideoMetadata, clearance: PublishClearance
    ) -> TikTokResult:
        if not video.exists():
            raise PublishRejected(f"không có file {video}")
        size = video.stat().st_size
        if size <= 0:
            raise PublishRejected(f"file {video} rỗng")

        with httpx.Client(timeout=self._timeout, headers=self._headers) as client:
            privacy = self._pick_privacy(client)
            publish_id, upload_url = self._init_upload(
                client, size=size, title=self._build_title(metadata, clearance), privacy=privacy
            )
            self._upload(client, upload_url, video, size)
            status = self._status(client, publish_id)

        log.info("tiktok.publish.done", publish_id=publish_id, status=status, privacy=privacy)
        return TikTokResult(remote_id=publish_id, remote_url=None)

    # ---------------- Từng pha ----------------

    def _pick_privacy(self, client: httpx.Client) -> str:
        """Hỏi API xem tài khoản này được đặt mức hiển thị nào.

        Hỏi thay vì đoán: danh sách khác nhau theo tài khoản và theo tình trạng
        audit của client, và gửi một giá trị ngoài danh sách thì lần đăng hỏng
        hẳn chứ không hạ cấp.
        """
        data = self._get(client, f"{API_BASE}/post/publish/creator_info/query/")
        options = data.get("data", {}).get("privacy_level_options") or []
        if self._privacy_level in options:
            return self._privacy_level
        if options:
            log.warning(
                "tiktok.privacy.fallback", wanted=self._privacy_level, options=options
            )
            # Ưu tiên mức kín nhất trong số được phép.
            for candidate in ("SELF_ONLY", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR"):
                if candidate in options:
                    return candidate
            return str(options[0])
        raise PublishRejected(
            "TikTok không trả về mức hiển thị nào — kiểm scope video.publish và "
            "tình trạng audit của client (G7.1)"
        )

    def _init_upload(
        self, client: httpx.Client, *, size: int, title: str, privacy: str
    ) -> tuple[str, str]:
        chunk = min(CHUNK_SIZE, size)
        payload = {
            "post_info": {
                "title": title,
                "privacy_level": privacy,
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": chunk,
                "total_chunk_count": max(1, -(-size // chunk)),
            },
        }
        data = self._post(client, f"{API_BASE}/post/publish/video/init/", json=payload)
        body = data.get("data", {})
        publish_id, upload_url = body.get("publish_id"), body.get("upload_url")
        if not publish_id or not upload_url:
            raise PublishFailed(f"TikTok không trả publish_id/upload_url: {data}")
        return str(publish_id), str(upload_url)

    def _upload(self, client: httpx.Client, upload_url: str, video: Path, size: int) -> None:
        with video.open("rb") as handle:
            offset = 0
            while offset < size:
                chunk = handle.read(CHUNK_SIZE)
                if not chunk:
                    break
                last = offset + len(chunk)
                try:
                    resp = client.put(
                        upload_url,
                        content=chunk,
                        headers={
                            "Content-Range": f"bytes {offset}-{last - 1}/{size}",
                            "Content-Type": "video/mp4",
                        },
                    )
                except httpx.HTTPError as exc:
                    raise PublishFailed(f"upload TikTok đứt ở byte {offset}: {exc}") from exc
                if resp.status_code >= 400:
                    raise self._classify(resp.status_code, resp.text)
                offset = last

    def _status(self, client: httpx.Client, publish_id: str) -> str:
        data = self._post(
            client,
            f"{API_BASE}/post/publish/status/fetch/",
            json={"publish_id": publish_id},
        )
        return str(data.get("data", {}).get("status", "UNKNOWN"))

    # ---------------- HTTP ----------------

    def _get(self, client: httpx.Client, url: str) -> dict:
        try:
            resp = client.post(url, json={})
        except httpx.HTTPError as exc:
            raise PublishFailed(f"gọi TikTok API thất bại: {exc}") from exc
        if resp.status_code >= 400:
            raise self._classify(resp.status_code, resp.text)
        return resp.json()

    def _post(self, client: httpx.Client, url: str, *, json: dict) -> dict:
        try:
            resp = client.post(url, json=json)
        except httpx.HTTPError as exc:
            raise PublishFailed(f"gọi TikTok API thất bại: {exc}") from exc
        if resp.status_code >= 400:
            raise self._classify(resp.status_code, resp.text)
        return resp.json()

    @staticmethod
    def _classify(status: int, body: str) -> Exception:
        """Phân loại lỗi: cái nào xếp lại được, cái nào phải sửa cấu hình.

        ``spam_risk_too_many_posts`` và ``rate_limit_exceeded`` là hạn mức trong
        ngày — mai là hết, nên xếp lại. Còn ``unaudited_client_can_only_post_to_private_accounts``
        là tình trạng audit của client: retry bao nhiêu lần cũng vậy.
        """
        snippet = body[:300]
        if "unaudited_client" in body or "scope_not_authorized" in body:
            return PublishRejected(
                f"TikTok từ chối vì client chưa audit hoặc thiếu scope ({status}): {snippet}\n"
                "Client chưa audit chỉ đăng được ở chế độ riêng tư — xem G7.1."
            )
        if status in (401, 403) or "access_token_invalid" in body:
            return PublishRejected(f"TikTok từ chối quyền ({status}): {snippet}")
        if status == 429 or "rate_limit" in body or "spam_risk" in body:
            return PublishFailed(f"TikTok hạn mức ({status}): {snippet}")
        if status >= 500:
            return PublishFailed(f"TikTok lỗi server ({status}): {snippet}")
        return PublishRejected(f"TikTok {status}: {snippet}")

    @staticmethod
    def _build_title(metadata: VideoMetadata, clearance: PublishClearance) -> str:
        """TikTok chỉ có một ô chữ: tiêu đề, mô tả và hashtag dồn vào đây.

        Ghi nguồn vẫn phải có mặt khi license đòi — cắt cho vừa 2200 ký tự thì cắt
        phần hashtag trước, không bao giờ cắt phần ghi nguồn.
        """
        head = metadata.title.strip()
        credit = (clearance.attribution_text or "").strip()
        tags = " ".join(f"#{t.replace(' ', '')}" for t in metadata.tags[:5])
        if metadata.ai_generated_voice:
            credit = f"{credit}\nGiọng đọc tổng hợp bằng AI.".strip()
        fixed = "\n\n".join(part for part in (head, credit) if part)[:MAX_TITLE]
        room = MAX_TITLE - len(fixed) - 2
        return f"{fixed}\n\n{tags}"[:MAX_TITLE] if tags and room > len(tags) else fixed

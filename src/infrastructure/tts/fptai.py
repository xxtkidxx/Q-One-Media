"""Adapter FPT.AI TTS — dự phòng cho VoxCPM2, cùng một port.

Có mặt vì rủi ro đã ghi trong PLAN: **chất lượng giọng Việt của VoxCPM2 chưa
được kiểm chứng** (G0.5). Nếu blind test cho thấy không đạt thì đổi engine bằng
một biến môi trường, không phải viết lại pipeline.

Đặc điểm API cần biết: FPT.AI trả về **đường dẫn tới file audio**, không trả
audio trực tiếp trong response — và file đó cần vài giây mới sẵn sàng. Vì vậy
phải poll, và đó là lý do adapter này có vòng chờ mà VoxCPM2 không có.
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx

from src.domain.sourcing.clearance import DubbingClearance
from src.shared.logging import get_logger

log = get_logger(__name__)

API_URL = "https://api.fpt.ai/hmi/tts/v5"

# Giới hạn của API. Kịch bản dài hơn phải chia — nhưng ở dự án này mỗi cảnh
# 45–75 giây nên không bao giờ tới ngưỡng.
MAX_CHARS = 5000


class FptAiFailed(RuntimeError):
    retryable = True  # lỗi mạng / rate limit — xếp lại được


class FptAiRejected(RuntimeError):
    retryable = False  # input sai hoặc key sai — thử lại vô nghĩa


class FptAiSynthesizer:
    """Hiện thực port ``SpeechSynthesizer`` qua HTTP."""

    name = "fptai"

    def __init__(
        self,
        *,
        api_key: str,
        voice: str = "banmai",
        speed: str = "0",
        measured_syllables_per_sec: float | None = None,
        timeout_sec: float = 30.0,
        poll_attempts: int = 10,
        poll_interval_sec: float = 1.5,
    ) -> None:
        if not api_key:
            raise FptAiRejected("thiếu FPTAI_API_KEY")
        self._api_key = api_key
        self._voice = voice
        # speed "0" = tốc độ gốc. Cố tình không mở tham số tăng tốc ra ngoài:
        # nhồi kịch bản cho vừa khung bằng cách đọc nhanh là thứ F2.3 cấm.
        self._speed = speed
        self._rate = measured_syllables_per_sec
        self._timeout = timeout_sec
        self._poll_attempts = poll_attempts
        self._poll_interval = poll_interval_sec

    def measured_rate(self) -> float | None:
        return self._rate

    def synthesize(
        self,
        *,
        text: str,
        dest: Path,
        clearance: DubbingClearance,
        voice_ref: Path | None = None,
    ) -> Path:
        if not text.strip():
            raise FptAiRejected("không sinh giọng từ chuỗi rỗng")
        if len(text) > MAX_CHARS:
            raise FptAiRejected(f"kịch bản {len(text)} ký tự, vượt giới hạn {MAX_CHARS}")
        if voice_ref is not None:
            # Nói rõ thay vì im lặng bỏ qua: FPT.AI không clone giọng, nên nếu
            # thương hiệu cần giọng riêng thì phải dùng VoxCPM2.
            log.warning("fptai.voice_ref.ignored", reason="FPT.AI không hỗ trợ clone giọng")

        dest.parent.mkdir(parents=True, exist_ok=True)
        headers = {
            "api-key": self._api_key,
            "voice": self._voice,
            "speed": self._speed,
        }
        log.info("fptai.synthesize", chars=len(text), voice=self._voice,
                 source_id=clearance.source_id)

        with httpx.Client(timeout=self._timeout) as client:
            try:
                resp = client.post(API_URL, headers=headers, content=text.encode("utf-8"))
            except httpx.HTTPError as exc:
                raise FptAiFailed(f"gọi FPT.AI thất bại: {exc}") from exc

            if resp.status_code in (401, 403):
                raise FptAiRejected(f"FPT.AI từ chối khoá API ({resp.status_code})")
            if resp.status_code == 429:
                raise FptAiFailed("FPT.AI rate limit (429)")
            if resp.status_code >= 400:
                raise FptAiFailed(f"FPT.AI trả {resp.status_code}: {resp.text[:200]}")

            payload = resp.json()
            audio_url = payload.get("async")
            if not audio_url:
                raise FptAiFailed(f"FPT.AI không trả đường dẫn audio: {payload}")

            self._download_when_ready(client, audio_url, dest)
        return dest

    def _download_when_ready(self, client: httpx.Client, url: str, dest: Path) -> None:
        """Poll cho tới khi file audio sẵn sàng.

        FPT.AI trả URL trước khi file tồn tại, nên request đầu thường 404 — đó là
        hành vi bình thường của API này, không phải lỗi.
        """
        for attempt in range(1, self._poll_attempts + 1):
            try:
                audio = client.get(url)
            except httpx.HTTPError as exc:
                raise FptAiFailed(f"tải audio thất bại: {exc}") from exc
            if audio.status_code == 200 and audio.content:
                dest.write_bytes(audio.content)
                return
            time.sleep(self._poll_interval)
            log.info("fptai.poll", attempt=attempt, status=audio.status_code)
        raise FptAiFailed(
            f"audio chưa sẵn sàng sau {self._poll_attempts} lần thử ({self._poll_interval}s/lần)"
        )

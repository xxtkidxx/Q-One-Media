"""Adapter edge-tts — **chỉ dùng cho dev, bị chặn ở production**.

Mục đích duy nhất: chạy được toàn chuỗi pipeline **không cần GPU**, để kiểm tra
dây nối, ngân sách âm tiết, forced alignment và render trước khi có card. Không
phải lựa chọn sản xuất.

**Vì sao không dùng cho production** — và đây là lý do license, không phải chất
lượng: ``edge-tts`` là client **không chính thức** gọi vào dịch vụ đọc-thành-tiếng
của Microsoft Edge. Điều khoản sử dụng cho mục đích thương mại không rõ ràng, và
dự án này vừa bỏ VoiceStudio/OmniVoice vì đúng loại vấn đề đó (weights CC-BY-NC).
Giữ một chuẩn cho mình thì phải giữ cả ở đây. Production dùng **VoxCPM2**
(Apache-2.0) hoặc **FPT.AI** (hợp đồng thương mại).

``Settings.__post_init__`` từ chối ``APP_ENV=prod`` khi engine là ``edge`` — chặn
bằng cấu hình chứ không bằng lời nhắc, vì lời nhắc thì bị bỏ qua.

Giọng đã xác minh ngày 14/09/2026 bằng ``edge_tts.list_voices()``: đúng hai giọng
tiếng Việt, ``vi-VN-HoaiMyNeural`` (nữ) và ``vi-VN-NamMinhNeural`` (nam).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from src.domain.sourcing.clearance import DubbingClearance
from src.shared.logging import get_logger

log = get_logger(__name__)

VOICE_FEMALE = "vi-VN-HoaiMyNeural"
VOICE_MALE = "vi-VN-NamMinhNeural"
VOICES = (VOICE_FEMALE, VOICE_MALE)


class EdgeTtsFailed(RuntimeError):
    retryable = True  # dịch vụ online — lỗi mạng xếp lại được


class EdgeTtsRejected(RuntimeError):
    retryable = False


class EdgeTtsSynthesizer:
    """Hiện thực port ``SpeechSynthesizer``. Ra file MP3 (edge-tts không cho chọn WAV)."""

    name = "edge"

    def __init__(
        self,
        *,
        voice: str = VOICE_FEMALE,
        rate: str = "+0%",
        measured_syllables_per_sec: float | None = None,
    ) -> None:
        if voice not in VOICES:
            raise EdgeTtsRejected(
                f"giọng {voice!r} không có trong danh sách tiếng Việt đã xác minh: {VOICES}"
            )
        self._voice = voice
        # Cố tình để mặc định "+0%" và không mở tham số này ra cấu hình: tăng tốc
        # độ đọc để nhồi kịch bản cho vừa khung là thứ F2.3 cấm.
        self._rate = rate
        self._measured = measured_syllables_per_sec

    def measured_rate(self) -> float | None:
        return self._measured

    def synthesize(
        self,
        *,
        text: str,
        dest: Path,
        clearance: DubbingClearance,
        voice_ref: Path | None = None,
    ) -> Path:
        if not text.strip():
            raise EdgeTtsRejected("không sinh giọng từ chuỗi rỗng")
        if voice_ref is not None:
            # Nói rõ thay vì im lặng bỏ qua: edge-tts không clone giọng, nên giọng
            # thương hiệu riêng chỉ có ở VoxCPM2.
            log.warning("edge.voice_ref.ignored", reason="edge-tts không clone giọng")

        try:
            import edge_tts
        except ImportError as exc:
            raise EdgeTtsRejected(
                "chưa cài edge-tts — thêm vào requirements của image đang dùng"
            ) from exc

        dest.parent.mkdir(parents=True, exist_ok=True)
        # edge-tts chỉ xuất MP3. Đổi đuôi cho đúng nội dung thật thay vì ghi MP3
        # vào file .wav — ffmpeg đọc được cả hai, nhưng một file nói sai định dạng
        # của chính nó là cái bẫy cho người đọc code sau này.
        target = dest.with_suffix(".mp3")

        log.info(
            "edge.synthesize",
            voice=self._voice,
            chars=len(text),
            source_id=clearance.source_id,
        )
        try:
            asyncio.run(self._run(edge_tts, text, target))
        except Exception as exc:
            raise EdgeTtsFailed(f"edge-tts thất bại: {type(exc).__name__}: {exc}") from exc

        if not target.exists() or target.stat().st_size == 0:
            raise EdgeTtsFailed("edge-tts báo thành công nhưng file rỗng")
        return target

    async def _run(self, edge_tts, text: str, target: Path) -> None:
        communicate = edge_tts.Communicate(text, self._voice, rate=self._rate)
        await communicate.save(str(target))

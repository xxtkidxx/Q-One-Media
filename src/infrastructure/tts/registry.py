"""Chọn engine TTS theo cấu hình.

Tồn tại vì một rủi ro đã ghi trong PLAN: chất lượng giọng Việt của VoxCPM2 chưa
được kiểm chứng (G0.5). Đổi engine phải là đổi một biến môi trường, không phải
sửa pipeline — nên chỗ duy nhất biết tên engine là ở đây.
"""

from __future__ import annotations

from pathlib import Path

from src.application.ports import SpeechSynthesizer
from src.shared.config import ConfigError, Settings


def build_synthesizer(settings: Settings) -> SpeechSynthesizer:
    engine = settings.tts.engine.strip().lower()

    if engine == "voxcpm":
        from src.infrastructure.tts.voxcpm import VoxCpmSynthesizer

        return VoxCpmSynthesizer(
            model_dir=settings.model_cache / "voxcpm",
            default_voice_ref=Path(settings.tts.voice_ref) if settings.tts.voice_ref else None,
            measured_syllables_per_sec=settings.tts.measured_rate,
        )

    if engine == "fptai":
        from src.infrastructure.tts.fptai import FptAiSynthesizer

        if not settings.tts.fptai_api_key:
            raise ConfigError("TTS_ENGINE=fptai nhưng thiếu FPTAI_API_KEY")
        return FptAiSynthesizer(
            api_key=settings.tts.fptai_api_key,
            measured_syllables_per_sec=settings.tts.measured_rate,
        )

    raise ConfigError(f"TTS_ENGINE không nhận ra: {settings.tts.engine!r} (voxcpm | fptai)")

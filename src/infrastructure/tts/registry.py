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

        # Không truyền model_id: mặc định của adapter là openbmb/VoxCPM2, model
        # duy nhất có tiếng Việt. HF_HOME trong compose đã trỏ cache vào /models.
        return VoxCpmSynthesizer(
            default_voice_ref=Path(settings.tts.voice_ref) if settings.tts.voice_ref else None,
            default_voice_ref_text=settings.tts.voice_ref_text,
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

    if engine == "edge":
        from src.infrastructure.tts.edge import VOICE_FEMALE, EdgeTtsSynthesizer

        # Chặn ở đây là lớp thứ hai; lớp thứ nhất ở Settings.__post_init__. Hai lớp
        # vì đây là ràng buộc license, không phải tuỳ chọn kỹ thuật.
        if settings.is_prod:
            raise ConfigError(
                "TTS_ENGINE=edge không dùng được ở production: edge-tts là client "
                "không chính thức của dịch vụ Microsoft Edge, điều khoản thương mại "
                "không rõ ràng. Dùng voxcpm (Apache-2.0) hoặc fptai."
            )
        return EdgeTtsSynthesizer(
            voice=settings.tts.voice_ref or VOICE_FEMALE,
            measured_syllables_per_sec=settings.tts.measured_rate,
        )

    raise ConfigError(
        f"TTS_ENGINE không nhận ra: {settings.tts.engine!r} (voxcpm | fptai | edge)"
    )

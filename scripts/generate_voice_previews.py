"""Sinh và cache mẫu nghe thử cho VoxCPM2, VieNeu-TTS và hai giọng Edge dev."""

from __future__ import annotations

from types import SimpleNamespace

from src.infrastructure.tts.edge import VOICES as EDGE_VOICES
from src.infrastructure.tts.edge import EdgeTtsSynthesizer
from src.infrastructure.tts.vieneu import PRESETS, VieNeuSynthesizer
from src.infrastructure.tts.voxcpm import VoxCpmSynthesizer
from src.shared.config import get_settings

PREVIEW_TEXT = "Xin chào, đây là giọng đọc thử cho video của Q One Media."


def main() -> None:
    settings = get_settings()
    destination = settings.media_root / "work" / "voice-previews"
    destination.mkdir(parents=True, exist_ok=True)
    clearance = SimpleNamespace(source_id=0)
    voxcpm_output = destination / "voxcpm-default.wav"
    if not voxcpm_output.is_file() or voxcpm_output.stat().st_size == 0:
        VoxCpmSynthesizer().synthesize(
            text=PREVIEW_TEXT,
            dest=voxcpm_output,
            clearance=clearance,  # type: ignore[arg-type]
        )
        print(f"ok VoxCPM2: {voxcpm_output}")

    synthesizer = VieNeuSynthesizer()
    for slug, name, _, _ in PRESETS:
        output = destination / f"vieneu-{slug}.wav"
        if output.is_file() and output.stat().st_size > 0:
            print(f"skip {name}: {output}")
            continue
        synthesizer.voice = name
        synthesizer.synthesize(
            text=PREVIEW_TEXT,
            dest=output,
            clearance=None,  # type: ignore[arg-type] -- mẫu hệ thống, không lấy từ nguồn
        )
        print(f"ok {name}: {output}")

    for voice in EDGE_VOICES:
        expected = destination / f"edge-{voice}.mp3"
        if expected.is_file() and expected.stat().st_size > 0:
            print(f"skip Edge {voice}: {expected}")
            continue
        result = EdgeTtsSynthesizer(voice=voice).synthesize(
            text=PREVIEW_TEXT,
            dest=expected.with_suffix(".wav"),
            clearance=clearance,  # type: ignore[arg-type]
        )
        print(f"ok Edge {voice}: {result}")


if __name__ == "__main__":
    main()

"""Danh mục giọng đọc có thể chọn — một chỗ duy nhất biết hệ thống có giọng nào.

Người dựng nội dung chọn giọng theo **video**, không theo biến môi trường: một
video giải thích kỹ thuật và một video giới thiệu nhà máy không nhất thiết cùng
giọng. Vì vậy id giọng đi theo item vào DB, còn ``TTS_ENGINE`` chỉ còn là mặc
định khi người dùng không chọn gì.

Id có dạng ``engine:tên`` để một chuỗi nói đủ cả engine lẫn giọng — không cần
bảng tra thứ hai, và một id cũ trong DB vẫn đọc được sau khi thêm engine mới.

Bốn nguồn giọng, đúng theo thứ tự ưu tiên của dự án:

- **VoxCPM2** (Apache-2.0) — clone giọng từ audio mẫu, nên "giọng" ở đây là file
  mẫu: thả ``.wav`` vào ``media/voices/`` là nó hiện ra trong danh sách. Kèm file
  ``.txt`` cùng tên chứa lời đọc của mẫu thì clone khá hơn rõ rệt (model gióng
  được âm với chữ thay vì chỉ bắt chước âm sắc).
- **VieNeu-TTS** (Apache-2.0, weights + codec đều đã kiểm trên model card) — 20
  giọng **dựng sẵn** đủ Bắc/Trung/Nam, nam và nữ. Đây là nguồn giọng dùng được
  ngay mà không cần thu mẫu, và chạy trên CPU nên không tranh VRAM với Whisper.
- **FPT.AI** (hợp đồng thương mại) — dự phòng khi hai engine trên không đạt (G0.5).
- **edge** — **chỉ dev**, để chạy toàn chuỗi khi không có GPU. Bị chặn ở prod.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.infrastructure.tts.vieneu import PRESETS as VIENEU_PRESETS
from src.shared.config import ConfigError, Settings

VOICE_DIR_NAME = "voices"
AUDIO_SUFFIXES = (".wav", ".mp3", ".flac", ".m4a")
SYSTEM_PREVIEW_TEXT = "Xin chào, đây là giọng đọc thử cho video của Q One Media."


@dataclass(frozen=True, slots=True)
class VoiceOption:
    id: str
    label: str
    engine: str
    gender: str = ""
    region: str = ""
    note: str = ""
    available: bool = True
    ref_path: Path | None = None
    ref_text: str | None = None
    preview_path: Path | None = None

    @property
    def name(self) -> str:
        return self.id.split(":", 1)[1] if ":" in self.id else self.id


# Giọng FPT.AI theo tài liệu công khai của họ. **Chưa xác minh bằng tài khoản
# thật** — chưa có FPTAI_API_KEY (G0.5), nên danh sách này được đánh dấu
# `available=False` cho tới khi có key, và API vẫn là nơi quyết định cuối cùng.
FPTAI_VOICES: tuple[tuple[str, str, str, str], ...] = (
    ("banmai", "Ban Mai", "nữ", "Bắc"),
    ("thuminh", "Thu Minh", "nữ", "Bắc"),
    ("leminh", "Lê Minh", "nam", "Bắc"),
    ("myan", "Mỹ An", "nữ", "Trung"),
    ("giahuy", "Gia Huy", "nam", "Trung"),
    ("ngoclam", "Ngọc Lam", "nữ", "Trung"),
    ("lannhi", "Lan Nhi", "nữ", "Nam"),
    ("linhsan", "Linh San", "nữ", "Nam"),
    ("minhquang", "Minh Quang", "nam", "Nam"),
)

# 20 giọng dựng sẵn của VieNeu-TTS v3 Turbo — miễn phí, Apache-2.0, model card
# cho phép dùng thương mại (kiểm ngày 15/09/2026). Đây là nguồn giọng "dùng được
# ngay" lớn nhất của dự án: VoxCPM2 clone tốt nhưng phải có audio mẫu trước.

# Hai giọng edge đã xác minh ngày 14/09/2026 bằng ``edge_tts.list_voices()`` —
# đúng hai, không phải "một vài" (G0.11).
EDGE_VOICES: tuple[tuple[str, str, str], ...] = (
    ("vi-VN-HoaiMyNeural", "Hoài My", "nữ"),
    ("vi-VN-NamMinhNeural", "Nam Minh", "nam"),
)


def voices_dir(settings: Settings) -> Path:
    return settings.media_root / VOICE_DIR_NAME


def list_voices(settings: Settings) -> list[VoiceOption]:
    """Mọi giọng hệ thống biết, kèm cờ dùng được hay chưa.

    Trả cả giọng **chưa dùng được** thay vì giấu đi: người dùng cần thấy rằng
    FPT.AI có ở đây và chỉ thiếu API key, chứ không phải tưởng hệ thống chỉ có
    một giọng duy nhất.
    """
    options: list[VoiceOption] = []

    default_ref = Path(settings.tts.voice_ref) if settings.tts.voice_ref else None
    options.append(
        VoiceOption(
            id="voxcpm:default",
            label="VoxCPM2 — giọng mẫu mặc định",
            engine="voxcpm",
            note=(
                f"Mẫu: {default_ref.name}" if default_ref
                else "Chưa đặt VOXCPM_VOICE_REF — model đọc bằng giọng tự sinh"
            ),
            ref_path=default_ref,
            ref_text=settings.tts.voice_ref_text,
            preview_path=(
                default_ref
                if default_ref and default_ref.is_file()
                else settings.media_root / "work" / "voice-previews" / "voxcpm-default.wav"
            ),
        )
    )
    directory = voices_dir(settings)
    if directory.is_dir():
        for sample in sorted(directory.iterdir()):
            if sample.suffix.lower() not in AUDIO_SUFFIXES:
                continue
            script = sample.with_suffix(".txt")
            options.append(
                VoiceOption(
                    id=f"voxcpm:{sample.stem}",
                    label=f"VoxCPM2 — {sample.stem}",
                    engine="voxcpm",
                    note=(
                        "Có lời đọc mẫu, clone sát hơn" if script.is_file()
                        else "Thiếu file .txt lời đọc mẫu — clone kém sát hơn"
                    ),
                    ref_path=sample,
                    preview_path=sample,
                    ref_text=(
                        script.read_text(encoding="utf-8").strip()
                        if script.is_file() else None
                    ),
                )
            )


    for slug, name, gender, region in VIENEU_PRESETS:
        options.append(
            VoiceOption(
                id=f"vieneu:{slug}",
                label=f"VieNeu — {name}",
                engine="vieneu",
                gender=gender,
                region=region,
                # Catalog chạy trong API, còn engine nặng chỉ được cài trong worker.
                # Kiểm tra import tại đây sẽ luôn khóa nhầm giọng dù worker dùng được.
                available=True,
                preview_path=(
                    settings.media_root / "work" / "voice-previews" / f"vieneu-{slug}.wav"
                ),
            )
        )

    has_fptai = bool(settings.tts.fptai_api_key)
    for name, label, gender, region in FPTAI_VOICES:
        options.append(
            VoiceOption(
                id=f"fptai:{name}",
                label=f"FPT.AI — {label}",
                engine="fptai",
                gender=gender,
                region=region,
                available=has_fptai,
                note="" if has_fptai else "Cần FPTAI_API_KEY",
            )
        )

    for name, label, gender in EDGE_VOICES:
        options.append(
            VoiceOption(
                id=f"edge:{name}",
                label=f"Edge (chỉ dev) — {label}",
                engine="edge",
                gender=gender,
                region="Bắc",
                available=not settings.is_prod,
                note="Chỉ dùng cho dev; điều khoản thương mại không rõ ràng",
                preview_path=(
                    settings.media_root
                    / "work"
                    / "voice-previews"
                    / f"edge-{name}.mp3"
                ),
            )
        )
    return options


def find_voice(voice_id: str | None, settings: Settings) -> VoiceOption | None:
    if not voice_id:
        return None
    for option in list_voices(settings):
        if option.id == voice_id:
            return option
    return None


def default_voice_id(settings: Settings) -> str:
    """Giọng mặc định suy từ ``TTS_ENGINE`` — giữ hành vi cũ khi không ai chọn."""
    engine = settings.tts.engine.strip().lower()
    if engine == "voxcpm":
        return "voxcpm:default"
    if engine == "vieneu":
        return f"vieneu:{VIENEU_PRESETS[0][0]}"
    if engine == "fptai":
        return "fptai:banmai"
    if engine == "edge":
        return f"edge:{EDGE_VOICES[0][0]}"
    raise ConfigError(f"TTS_ENGINE không nhận ra: {settings.tts.engine!r}")


def label_for(voice_id: str | None, settings: Settings) -> str:
    option = find_voice(voice_id, settings)
    if option is not None:
        return option.label
    return voice_id or "Giọng mặc định"

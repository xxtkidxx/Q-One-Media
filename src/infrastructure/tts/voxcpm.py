"""Adapter VoxCPM2 — giọng tiếng Việt chạy tại chỗ.

Chọn VoxCPM2 vì **Apache-2.0** và có `vi`, nên dùng thương mại được. Đối chiếu:
engine mặc định của VoiceStudio (OmniVoice) có weights CC-BY-NC → không dùng
thương mại được, dù code ứng dụng là giấy phép mở.

Model nạp **lười và giữ lại** (biến module-level): nạp mất hàng chục giây và
chiếm vài GB VRAM, nên worker chỉ nạp một lần cho suốt vòng đời tiến trình. Đây
cũng là lý do worker chạy một việc một lần thay vì thread pool — xem
``src/interfaces/worker/main.py``.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from src.domain.sourcing.clearance import DubbingClearance
from src.shared.logging import get_logger

log = get_logger(__name__)

# Model ID **tường minh**, không dùng mặc định của thư viện. Lý do cụ thể:
# ``openbmb/VoxCPM-0.5B`` chỉ có ``en`` và ``zh`` — **không có tiếng Việt**.
# Chỉ ``openbmb/VoxCPM2`` có ``vi`` (đã xác minh trên HF: license apache-2.0,
# 30 ngôn ngữ gồm vi). Để thư viện tự chọn là rủi ro nạp đúng model không dùng được.
DEFAULT_MODEL_ID = "openbmb/VoxCPM2"

_model: Any = None


class TtsFailed(RuntimeError):
    retryable = False


class ModelUnavailable(RuntimeError):
    """Chưa tải model hoặc không có GPU. Không retry — phải sửa môi trường."""

    retryable = False


def _load_model(model_id: str) -> Any:
    global _model
    if _model is not None:
        return _model
    try:
        from voxcpm import VoxCPM  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ModelUnavailable(
            "chưa cài voxcpm — chỉ có trong image worker, không có trong image api"
        ) from exc
    log.info("voxcpm.load.start", model_id=model_id)
    try:
        _model = VoxCPM.from_pretrained(model_id)
    except Exception as exc:
        raise ModelUnavailable(
            f"nạp {model_id} thất bại: {type(exc).__name__}: {exc}"
        ) from exc
    log.info("voxcpm.load.done", model_id=model_id)
    return _model


# Âm tiết tiếng Việt ≈ cụm ký tự chữ ngăn bởi khoảng trắng hoặc dấu câu.
# Xấp xỉ này đủ dùng vì tiếng Việt viết rời từng âm tiết: đếm "tiếng" cách này
# sát thực tế hơn nhiều so với đếm từ theo nghĩa từ vựng.
_LETTER_GROUP_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
_DIGIT_RE = re.compile(r"\d")

# Mỗi chữ số nở ra khoảng 1,5 âm tiết khi đọc: "380" → "ba trăm tám mươi"
# (4 âm tiết cho 3 chữ số), "67" → "sáu mươi bảy" (3 cho 2). Hệ số này là ước
# lượng **thiên về cao**, và đó là chủ ý: với một ngân sách thì đếm thừa làm
# kịch bản ngắn hơn cần, còn đếm thiếu thì để kịch bản tràn khung đi qua.
_SYLLABLES_PER_DIGIT = 1.5


def count_syllables(text: str) -> int:
    """Ước lượng số âm tiết **nói ra** của một đoạn tiếng Việt.

    Đếm tiếng chứ không đếm từ: "Hệ thống kiểm soát quá trình" = 6 âm tiết.

    Chữ số được tính riêng vì nội dung công nghiệp dày số — "biến tần 380V",
    "Cpk 1.33", "IP67" — và một chữ số trên giấy nở thành nhiều âm tiết khi đọc.
    Bỏ qua điều này thì hàm đếm *thiếu* đúng ở loại nội dung dự án này làm nhiều
    nhất, và thiếu là hướng sai nguy hiểm cho một ngân sách.

    Đây vẫn chỉ là ước lượng. Thẩm quyền cuối cùng là **độ dài audio đo được**
    sau khi TTS chạy — xem ``application/use_cases/synthesize_voice.py``.
    """
    letters = len(_LETTER_GROUP_RE.findall(text))
    digits = len(_DIGIT_RE.findall(text))
    return letters + math.ceil(digits * _SYLLABLES_PER_DIGIT)


class VoxCpmSynthesizer:
    """Hiện thực port ``SpeechSynthesizer``."""

    name = "voxcpm"

    def __init__(
        self,
        *,
        model_id: str = DEFAULT_MODEL_ID,
        default_voice_ref: Path | None = None,
        measured_syllables_per_sec: float | None = None,
    ) -> None:
        self._model_id = model_id
        self._default_voice_ref = default_voice_ref
        # Cố tình để None nếu chưa đo. Các con số 5,28–6 âm tiết/giây tìm được
        # trên mạng không thống nhất; đặc tả F2.3 yêu cầu tự đo giọng đang dùng
        # (G0.7). Không có số đo thật thì không lập ngân sách âm tiết được.
        self._rate = measured_syllables_per_sec

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
        """Sinh audio tiếng Việt.

        ``clearance`` là bắt buộc theo port: lồng tiếng cần quyền sửa audio, và
        vật chứng minh quyền đó chỉ ``Source`` cấp được.
        """
        if not text.strip():
            raise TtsFailed("không sinh giọng từ chuỗi rỗng")
        dest.parent.mkdir(parents=True, exist_ok=True)

        ref = voice_ref or self._default_voice_ref
        model = _load_model(self._model_id)
        log.info(
            "voxcpm.synthesize",
            syllables=count_syllables(text),
            source_id=clearance.source_id,
            voice_ref=str(ref) if ref else None,
        )
        try:
            wav = model.generate(
                text=text,
                prompt_wav_path=str(ref) if ref else None,
                # Không tăng tốc độ đọc để nhồi cho vừa khung: giọng nhanh bất
                # thường là dấu hiệu video máy làm (F2.3). Kịch bản dài quá thì
                # viết ngắn lại, việc đó do use case quyết định.
            )
        except Exception as exc:
            raise TtsFailed(f"VoxCPM2 sinh giọng thất bại: {type(exc).__name__}: {exc}") from exc

        _write_wav(wav, dest, sample_rate=getattr(model, "sample_rate", 16000))
        return dest


def _write_wav(samples: Any, dest: Path, *, sample_rate: int) -> None:
    """Ghi mảng float32 ra WAV 16-bit mà không cần soundfile."""
    import array
    import wave

    try:
        flat = [float(x) for x in samples.reshape(-1)]  # numpy / torch
    except AttributeError:
        flat = [float(x) for x in samples]

    pcm = array.array(
        "h", (max(-32768, min(32767, round(x * 32767))) for x in flat)
    )
    with wave.open(str(dest), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())

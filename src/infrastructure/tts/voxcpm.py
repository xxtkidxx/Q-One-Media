"""Adapter VoxCPM2 — giọng tiếng Việt chạy tại chỗ.

Chọn VoxCPM2 vì **Apache-2.0** và có `vi`, nên dùng thương mại được. Đối chiếu:
engine mặc định của VoiceStudio (OmniVoice) có weights CC-BY-NC → không dùng
thương mại được, dù code ứng dụng là giấy phép mở.

**Model nhả ngay sau mỗi lần sinh giọng, không giữ lại.** Trước đây adapter này giữ
model ở biến module-level cho suốt vòng đời tiến trình, vì nạp tốn hàng chục giây. Số
đo trên card thật (``make measure-load``) cho thấy cách đó không dùng được:

| | VoxCPM2 | Whisper large-v3 |
|---|---|---|
| Giữ trên card | **5,12 GB** | ~3,5 GB |
| VRAM còn rảnh khi đang giữ | **0,00/8,0 GB** | 3,40/8,0 GB |
| Nạp lần đầu | 120,9 s | 20,2 s |
| Nạp lại, cache ấm | **31,9 s** | 17,5 s |

Hai con số quyết định: giữ VoxCPM2 lại thì **không còn một byte VRAM nào** cho Whisper,
mà worker phải chạy cả hai; còn nạp lại chỉ tốn **31,9 s** chứ không phải 120,9 s — phần
chênh 89 s là biên dịch kernel (``torch.compile``/inductor), trả một lần cho mỗi tiến
trình. Đổi 32 giây mỗi việc để không bao giờ ``CUDA out of memory`` là đổi đáng, nhất là
khi mỗi video còn phải qua 20–35 phút người soát.

Nhờ vậy adapter này giờ cùng một giao kèo với ``asr/whisper.py`` và ``asr/demucs.py``:
**nạp trong hàm, nhả trong ``finally``**. Không adapter nào giữ VRAM qua ranh giới lời gọi.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from src.domain.sourcing.clearance import DubbingClearance
from src.shared.gpu import free_vram
from src.shared.logging import get_logger

log = get_logger(__name__)

# Model ID **tường minh**, không dùng mặc định của thư viện. Lý do cụ thể:
# ``openbmb/VoxCPM-0.5B`` chỉ có ``en`` và ``zh`` — **không có tiếng Việt**.
# Chỉ ``openbmb/VoxCPM2`` có ``vi`` (đã xác minh trên HF: license apache-2.0,
# 30 ngôn ngữ gồm vi). Để thư viện tự chọn là rủi ro nạp đúng model không dùng được.
DEFAULT_MODEL_ID = "openbmb/VoxCPM2"


class TtsFailed(RuntimeError):
    retryable = False


class ModelUnavailable(RuntimeError):
    """Chưa tải model hoặc không có GPU. Không retry — phải sửa môi trường."""

    retryable = False


def _device() -> str:
    try:
        import torch
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def _load_model(model_id: str, *, load_denoiser: bool) -> Any:
    """Nạp model. Người gọi **phải** ``del`` nó rồi gọi ``free_vram()`` khi xong.

    Không cache: xem docstring đầu file — trên card 8 GB, giữ model này lại nghĩa là
    Whisper không nạp được nữa.
    """
    try:
        from voxcpm import VoxCPM  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ModelUnavailable(
            "chưa cài voxcpm — chỉ có trong image worker, không có trong image api"
        ) from exc

    device = _device()
    log.info("voxcpm.load.start", model_id=model_id, device=device, denoiser=load_denoiser)
    try:
        model = VoxCPM.from_pretrained(
            model_id,
            device=device,
            # Denoiser là model RIÊNG (~vài trăm MB) chỉ dùng để làm sạch audio
            # mẫu khi clone giọng. Với card 8 GB thì mỗi GB đều đáng, và giọng
            # mẫu của NMI nên được thu sạch ngay từ đầu chứ không dựa vào denoiser.
            load_denoiser=load_denoiser,
        )
    except Exception as exc:
        raise ModelUnavailable(
            f"nạp {model_id} thất bại: {type(exc).__name__}: {exc}"
        ) from exc
    log.info("voxcpm.load.done", model_id=model_id, sample_rate=_sample_rate(model))
    return model


def _sample_rate(model: Any) -> int:
    """Lấy sample rate thật của model, **không đoán**.

    Lớp công khai ``VoxCPM`` bọc ``self.tts_model`` và không expose
    ``sample_rate``; thuộc tính đó nằm trên model bên trong. Dùng một giá trị mặc
    định ở đây là sai âm thầm theo cách tệ nhất: WAV ghi sai tần số thì audio phát
    sai tốc độ, độ dài đo được sai theo, và **ngân sách âm tiết sai theo nữa** —
    không ai truy ra được từ đâu.
    """
    for obj in (getattr(model, "tts_model", None), model):
        rate = getattr(obj, "sample_rate", None)
        if isinstance(rate, int) and rate > 0:
            return rate
    raise TtsFailed(
        "không đọc được sample_rate của VoxCPM2 — không ghi WAV khi chưa biết tần số"
    )


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
        default_voice_ref_text: str | None = None,
        load_denoiser: bool = False,
        measured_syllables_per_sec: float | None = None,
    ) -> None:
        self._model_id = model_id
        # Lời đọc của audio mẫu. Cung cấp thì clone giọng khá hơn rõ rệt vì model
        # gióng được âm với chữ thay vì chỉ bắt chước âm sắc.
        self._voice_ref_text = default_voice_ref_text
        self._load_denoiser = load_denoiser
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
        model = None
        try:
            model = _load_model(self._model_id, load_denoiser=self._load_denoiser)
            log.info(
                "voxcpm.synthesize",
                syllables=count_syllables(text),
                source_id=clearance.source_id,
                voice_ref=str(ref) if ref else None,
            )
            wav = model.generate(
                text=text,
                prompt_wav_path=str(ref) if ref else None,
                prompt_text=self._voice_ref_text if ref else None,
                # normalize=False (mặc định của thư viện) là CÓ Ý: bộ chuẩn hoá
                # của VoxCPM làm cho tiếng Trung và tiếng Anh, đưa tiếng Việt vào
                # thì rủi ro đọc sai số và thuật ngữ. Thay vào đó, prompt viết kịch
                # bản đã yêu cầu viết số thành chữ ("một phẩy ba ba").
                #
                # Cũng không có tham số tăng tốc độ đọc ở đây: nhồi kịch bản cho
                # vừa khung bằng cách đọc nhanh là thứ F2.3 cấm. Tràn thì viết
                # ngắn lại, và use case quyết định việc đó.
            )
            # Ghi WAV **trước** khi nhả model: sample rate đọc từ model, và đoán
            # tần số là sai âm thầm theo cách tệ nhất — xem ``_sample_rate``.
            _write_wav(wav, dest, sample_rate=_sample_rate(model))
        except ModelUnavailable:
            raise
        except Exception as exc:
            raise TtsFailed(f"VoxCPM2 sinh giọng thất bại: {type(exc).__name__}: {exc}") from exc
        finally:
            # Xoá model rồi mới nhả: ``empty_cache()`` không trả được gì khi object
            # còn sống. Bỏ hai dòng này thì Whisper của việc sau hết VRAM.
            del model
            free_vram()

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

"""Nhận dạng lời bằng Whisper, qua ``faster-whisper`` trực tiếp.

**Không dùng WhisperX** nữa, và có hai lý do cộng lại:

1. Phần giá trị nhất của WhisperX với dự án này là forced alignment — nhưng model
   gióng tiếng Việt duy nhất nó trỏ tới là ``cc-by-nc-4.0`` và lại thiếu CTC head,
   nên đã bị thay bằng ``src/infrastructure/asr/align.py``. Sau đó WhisperX chỉ còn
   đóng góp phần gom batch và VAD, mà ``faster-whisper`` có sẵn cả hai.
2. Ràng buộc phiên bản không thoát được: ``whisperx 3.3.1`` khoá
   ``ctranslate2<4.5``, và ctranslate2 < 4.5 link với **cuDNN 8** — trong khi base
   image CUDA 12.4 và torch 2.6 đều mang cuDNN 9. Kết quả là CTranslate2 **abort
   cứng cả tiến trình** (``Fatal Python error: Aborted``). Bản ``whisperx 3.8.6``
   cho phép ctranslate2 mới nhưng lại đòi ``torch~=2.8``, tức một lần di trú nữa
   cho thứ ta không còn cần.

Bỏ WhisperX nên còn **một** đường ASR duy nhất, dùng chung cho cả nhận dạng lời
nguồn và lấy mốc thời gian để gióng phụ đề.

Về mức chính xác: máy **đoán** chữ ở bước này, nên có tỷ lệ sai — tiếng Anh sạch
~93–95% đúng, tiếng Trung ~12,8% CER (đặc tả F2.8). Vì vậy Giai đoạn 1 bắt buộc có
người soát transcript.
"""

from __future__ import annotations

import gc
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.shared.logging import get_logger

log = get_logger(__name__)

DEFAULT_MODEL = "large-v3"

# Ngưỡng gộp từ thành một dòng phụ đề. 42 ký tự là mức đọc kịp trên màn hình dọc
# ở cỡ chữ 54px với lề 80px mỗi bên.
MAX_SUBTITLE_CHARS = 42
MAX_SUBTITLE_SEC = 5.0


class AsrFailed(RuntimeError):
    retryable = False


class WhisperUnavailable(RuntimeError):
    retryable = False


@dataclass(frozen=True, slots=True)
class Word:
    text: str
    start: float
    end: float


@dataclass(frozen=True, slots=True)
class Transcript:
    language: str
    text: str
    segments: list[dict[str, Any]]


def device_and_compute() -> tuple[str, str]:
    try:
        import torch
    except ImportError as exc:
        raise WhisperUnavailable("chưa cài torch — chỉ có trong image worker") from exc
    if torch.cuda.is_available():
        # float16 trên GPU: nhanh gấp ~2 lần float32 và WER gần như không đổi.
        return "cuda", "float16"
    log.warning("whisper.device.cpu", reason="không thấy CUDA — large-v3 trên CPU rất chậm")
    return "cpu", "int8"


def load_model(model_name: str = DEFAULT_MODEL) -> Any:
    """Nạp model Whisper. Người gọi **phải** ``del`` nó khi xong — xem ``free_vram``."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise WhisperUnavailable(
            "chưa cài faster-whisper — chỉ có trong image worker"
        ) from exc
    device, compute_type = device_and_compute()
    log.info("whisper.load", model=model_name, device=device, compute_type=compute_type)
    return WhisperModel(model_name, device=device, compute_type=compute_type)


def free_vram() -> None:
    """Nhả VRAM sau mỗi model.

    Bắt buộc trên card 8 GB: một job đi qua Demucs → Whisper → VoxCPM2, và ba model
    cùng ở trên GPU là CUDA out of memory.

    Đo thực tế trên RTX 3070: trong lúc large-v3 float16 chạy, VRAM rảnh về
    **0,00/8,0 GB**. CTranslate2 cấp bộ nhớ **ngoài** allocator của PyTorch nên
    ``empty_cache()`` một mình không nhả được gì — người gọi phải xoá object model
    trước khi gọi hàm này.
    """
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def transcribe(
    audio: Path,
    *,
    language: str,
    model_name: str = DEFAULT_MODEL,
    initial_prompt: str | None = None,
) -> Transcript:
    """Nhận dạng lời của audio nguồn.

    ``language`` truyền **tường minh** từ ``sources.audio_lang``, không để Whisper
    tự nhận: nội dung kỹ thuật đầy thuật ngữ Anh nên một video tiếng Trung có thể bị
    nhận sai thành tiếng Anh, và khi đó transcript vô dụng mà không có lỗi nào.

    ``initial_prompt`` cải thiện thuật ngữ nhưng **tăng nguy cơ hallucination**
    (F2.8) — dùng thận trọng, và người soát vẫn là bắt buộc.
    """
    model = None
    try:
        model = load_model(model_name)
        log.info("whisper.transcribe.start", language=language, model=model_name)
        segments_iter, info = model.transcribe(
            str(audio),
            language=language,
            initial_prompt=initial_prompt,
            # VAD bỏ khoảng lặng dài: nhanh hơn và giảm hallucination trên đoạn im.
            vad_filter=True,
            word_timestamps=False,
        )
        segments: list[dict[str, Any]] = [
            {"start": float(s.start), "end": float(s.end), "text": str(s.text).strip()}
            for s in segments_iter  # generator — phải duyệt hết mới có kết quả
        ]
    except Exception as exc:
        raise AsrFailed(f"Whisper transcribe thất bại: {type(exc).__name__}: {exc}") from exc
    finally:
        del model
        free_vram()

    text = " ".join(s["text"] for s in segments if s["text"]).strip()
    detected = getattr(info, "language", language) or language
    log.info("whisper.transcribe.done", segments=len(segments), chars=len(text))
    return Transcript(language=detected, text=text, segments=segments)


def group_words_into_cues(
    words: list[Word],
    *,
    max_chars: int = MAX_SUBTITLE_CHARS,
    max_sec: float = MAX_SUBTITLE_SEC,
) -> list[tuple[float, float, str]]:
    """Gộp từ thành dòng phụ đề đọc kịp.

    Hai loại điều kiện, và thứ tự xử lý khác nhau — đây là chỗ dễ viết sai:

    - **Chặn trên** (quá dài, quá lâu): kiểm **trước khi** thêm từ. Kiểm sau thì
      chính từ làm vượt ngưỡng vẫn nằm trong dòng, và dòng xuất ra vượt đúng cái
      giới hạn mà hàm này tồn tại để giữ.
    - **Hết câu** (dấu câu): ngắt **sau khi** thêm, vì dấu câu thuộc về dòng vừa
      kết thúc. Đây là ranh giới ngữ nghĩa thật nên nó được ưu tiên.
    """
    cues: list[tuple[float, float, str]] = []
    buf: list[Word] = []

    def flush() -> None:
        if buf:
            cues.append((buf[0].start, buf[-1].end, " ".join(w.text for w in buf)))
            buf.clear()

    for word in words:
        if buf:
            would_be = len(" ".join(w.text for w in buf)) + 1 + len(word.text)
            would_last = word.end - buf[0].start
            if would_be > max_chars or would_last > max_sec:
                flush()
        buf.append(word)
        if word.text.endswith((".", "!", "?", "…", ":", ";")):
            flush()
    flush()
    return cues

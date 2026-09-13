"""WhisperX: nhận dạng lời nguồn, và **forced alignment cho kịch bản đã biết**.

Hai việc dùng cùng một thư viện nhưng khác nhau về bản chất, và lẫn chúng là một
lỗi tốn kém:

- ``transcribe()`` — audio nguồn tiếng Anh/Trung → chữ. Ở đây máy *đoán* chữ, nên
  có tỷ lệ sai: tiếng Anh sạch ~93–95% đúng, tiếng Trung ~12,8% CER (F2.8). Vì
  vậy Giai đoạn 1 bắt buộc có người soát transcript.
- ``align_known_text()`` — audio TTS + **kịch bản mình vừa viết** → timestamp cấp
  từ. Ở đây chữ là **đầu vào**, không phải đầu ra, nên **không thể sai chữ**.

Đừng bao giờ chạy ASR trên audio TTS vừa tạo để lấy phụ đề: đó là tự tạo lỗi
nhận dạng từ một văn bản đã hoàn hảo (F2.5).
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


def _device_and_compute() -> tuple[str, str]:
    try:
        import torch
    except ImportError as exc:
        raise WhisperUnavailable("chưa cài torch — chỉ có trong image worker") from exc
    if torch.cuda.is_available():
        # float16 trên GPU: nhanh gấp ~2 lần float32 và WER gần như không đổi.
        return "cuda", "float16"
    log.warning("whisperx.device.cpu", reason="không thấy CUDA — large-v3 trên CPU rất chậm")
    return "cpu", "int8"


def transcribe(
    audio: Path,
    *,
    language: str,
    model_name: str = DEFAULT_MODEL,
    batch_size: int = 8,
    initial_prompt: str | None = None,
) -> Transcript:
    """Nhận dạng lời của audio nguồn.

    ``language`` truyền **tường minh** từ ``sources.audio_lang``, không để
    WhisperX tự nhận: nội dung kỹ thuật đầy thuật ngữ Anh nên một video tiếng
    Trung có thể bị nhận sai thành tiếng Anh, và khi đó transcript vô dụng mà
    không có lỗi nào.

    ``initial_prompt`` cải thiện thuật ngữ nhưng **tăng nguy cơ hallucination**
    (F2.8) — dùng thận trọng, và người soát vẫn là bắt buộc.
    """
    try:
        import whisperx
    except ImportError as exc:
        raise WhisperUnavailable("chưa cài whisperx — chỉ có trong image worker") from exc

    device, compute_type = _device_and_compute()
    log.info("whisperx.transcribe.start", language=language, model=model_name, device=device)
    try:
        asr_options = {"initial_prompt": initial_prompt} if initial_prompt else None
        model = whisperx.load_model(
            model_name, device, compute_type=compute_type, language=language,
            asr_options=asr_options,
        )
        result = model.transcribe(str(audio), batch_size=batch_size, language=language)
    except Exception as exc:
        raise AsrFailed(f"WhisperX transcribe thất bại: {type(exc).__name__}: {exc}") from exc
    finally:
        _free_vram()

    segments = list(result.get("segments") or [])
    text = " ".join(str(s.get("text", "")).strip() for s in segments).strip()
    log.info("whisperx.transcribe.done", segments=len(segments), chars=len(text))
    return Transcript(language=result.get("language", language), text=text, segments=segments)


def align_known_text(
    audio: Path,
    text: str,
    *,
    language: str = "vi",
) -> list[Word]:
    """Gióng **chữ đã biết** với audio, trả timestamp cấp từ.

    Chữ là đầu vào nên nội dung phụ đề không thể sai — chỉ có timing mới cần đo.
    Đây là lý do bước này thay cho việc ASR lại audio TTS.
    """
    try:
        import whisperx
    except ImportError as exc:
        raise WhisperUnavailable("chưa cài whisperx — chỉ có trong image worker") from exc

    if not text.strip():
        raise AsrFailed("không gióng được chuỗi rỗng")

    device, _ = _device_and_compute()
    log.info("whisperx.align.start", language=language, chars=len(text))
    try:
        audio_data = whisperx.load_audio(str(audio))
        duration = len(audio_data) / 16000.0
        model_a, metadata = whisperx.load_align_model(language_code=language, device=device)
        # Một segment phủ toàn bộ audio: ta không chia trước, để aligner tự tìm
        # vị trí từng từ trong cả đoạn.
        result = whisperx.align(
            [{"text": text.strip(), "start": 0.0, "end": duration}],
            model_a,
            metadata,
            audio_data,
            device,
            return_char_alignments=False,
        )
    except Exception as exc:
        raise AsrFailed(f"forced alignment thất bại: {type(exc).__name__}: {exc}") from exc
    finally:
        _free_vram()

    words: list[Word] = []
    for seg in result.get("segments") or []:
        for w in seg.get("words") or []:
            token = str(w.get("word", "")).strip()
            start, end = w.get("start"), w.get("end")
            if not token or start is None or end is None:
                # Aligner bỏ trống timestamp ở từ nó không gióng được (thường là
                # số hoặc từ nước ngoài). Bỏ từ đó khỏi timing chứ không đoán —
                # đoán sẽ làm lệch mọi từ sau nó.
                continue
            words.append(Word(text=token, start=float(start), end=float(end)))
    log.info("whisperx.align.done", words=len(words))
    return words


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


def _free_vram() -> None:
    """Nhả VRAM sau mỗi model.

    Bắt buộc: một job đi qua Demucs → WhisperX → VoxCPM2, và ba model cùng ở trên
    GPU là đường ngắn nhất tới CUDA out of memory trên card 8 GB.
    """
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass

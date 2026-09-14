"""WhisperX: nhận dạng lời của audio nguồn.

``transcribe()`` — audio nguồn tiếng Anh/Trung → chữ. Ở đây máy *đoán* chữ, nên có
tỷ lệ sai: tiếng Anh sạch ~93–95% đúng, tiếng Trung ~12,8% CER (F2.8). Vì vậy
Giai đoạn 1 bắt buộc có người soát transcript.

**Việc gióng kịch bản đã biết với audio TTS không ở đây** — nó ở
``src/infrastructure/asr/align.py``. Lý do tách ra và lý do không dùng forced
alignment của WhisperX (license cc-by-nc-4.0 và model thiếu CTC head) ghi trong
docstring của file đó.
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


_SAFE_GLOBALS_DONE = False


def _allow_checkpoint_globals() -> None:
    """Cho phép tường minh các class mà checkpoint của WhisperX/pyannote cần.

    Vì sao cần: torch 2.6 đổi mặc định ``torch.load`` sang ``weights_only=True``.
    Đổi đó là đúng về bảo mật, nhưng checkpoint VAD của pyannote (WhisperX dùng để
    cắt đoạn có tiếng nói) chứa object ``omegaconf`` đã pickle, nên bị từ chối với
    ``Unsupported global: omegaconf.listconfig.ListConfig``.

    Hai cách sửa, và ta chọn cách hẹp hơn:

    - ``weights_only=False`` — tắt hẳn kiểm tra cho **mọi** lần load. Quá rộng.
    - allowlist đúng những class cần — chỉ mở đúng phần cần mở.

    Mức rủi ro còn lại chấp nhận được vì model đến từ **id repo đã pin** trong
    ``scripts/fetch_models.py`` và nằm trong cache local ``data/models``, không phải
    checkpoint tuỳ ý người dùng nạp vào. Nếu về sau cho phép người dùng trỏ tới
    checkpoint của họ thì phải xem lại chỗ này.
    """
    global _SAFE_GLOBALS_DONE
    if _SAFE_GLOBALS_DONE:
        return
    try:
        import torch
    except ImportError:
        return

    allow: list = []
    try:
        from omegaconf.base import ContainerMetadata, Metadata
        from omegaconf.dictconfig import DictConfig
        from omegaconf.listconfig import ListConfig
        from omegaconf.nodes import AnyNode

        allow += [ListConfig, DictConfig, ContainerMetadata, Metadata, AnyNode]
    except ImportError:
        log.warning("whisperx.safe_globals.no_omegaconf")

    # Checkpoint pyannote cũng chứa các kiểu chuẩn này bên trong cấu hình.
    from collections import defaultdict
    from typing import Any as _Any

    allow += [defaultdict, dict, list, _Any]

    try:
        torch.serialization.add_safe_globals(allow)
        _SAFE_GLOBALS_DONE = True
        log.info("whisperx.safe_globals.added", count=len(allow))
    except AttributeError:
        # torch < 2.4 không có API này; ở đó weights_only chưa phải mặc định nên
        # cũng không cần.
        _SAFE_GLOBALS_DONE = True


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

    _allow_checkpoint_globals()
    device, compute_type = _device_and_compute()
    log.info("whisperx.transcribe.start", language=language, model=model_name, device=device)
    model = None
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
        # Xoá object model TRƯỚC khi gọi _free_vram(). Đo thực tế trên RTX 3070:
        # trong lúc large-v3 float16 chạy, VRAM rảnh về **0,00/8,0 GB**. CTranslate2
        # (nền của faster-whisper) cấp bộ nhớ **ngoài** allocator của PyTorch, nên
        # torch.cuda.empty_cache() một mình không giải phóng được gì — chỉ khi object
        # model bị giải phóng thì CTranslate2 mới nhả.
        del model
        _free_vram()

    segments = list(result.get("segments") or [])
    text = " ".join(str(s.get("text", "")).strip() for s in segments).strip()
    log.info("whisperx.transcribe.done", segments=len(segments), chars=len(text))
    return Transcript(language=result.get("language", language), text=text, segments=segments)


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

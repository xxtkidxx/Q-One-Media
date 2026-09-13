"""Tách stem bằng Demucs: **bỏ giọng, giữ tiếng máy**.

Đây là một trong những chỗ dễ làm sai nhất mà không ai nghe ra là sai. Video
công nghiệp có tiếng máy chạy, tiếng bíp HMI, tiếng khí nén — âm thanh đó **mang
thông tin** và làm video đáng tin với khán giả kỹ thuật. Xoá sạch audio gốc rồi
lồng giọng Việt lên thì video nghe như slideshow (đặc tả F2.4).

Tham số ``htdemucs`` với ``shifts=1, overlap=0.25`` và cách **cộng mọi stem không
phải giọng** để làm nền là ý mượn từ ``core/asr_backend/demucs_vl.py`` của
VideoLingo (Apache-2.0). Code ở đây viết lại trên API ``demucs`` trực tiếp, không
vendor — lý do ghi trong ``vendor/README.md`` (D23).
"""

from __future__ import annotations

import gc
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.shared.logging import get_logger

log = get_logger(__name__)


class SeparationFailed(RuntimeError):
    retryable = False


class DemucsUnavailable(RuntimeError):
    retryable = False


@dataclass(frozen=True, slots=True)
class Stems:
    vocals: Path
    background: Path


def _device() -> str:
    try:
        import torch
    except ImportError as exc:
        raise DemucsUnavailable("chưa cài torch — chỉ có trong image worker") from exc
    if torch.cuda.is_available():
        return "cuda"
    # CPU chạy được nhưng chậm hàng chục lần. Không chặn, chỉ nói rõ để người
    # vận hành biết lý do một job chạy 20 phút thay vì 40 giây.
    log.warning("demucs.device.cpu", reason="không thấy CUDA — Demucs trên CPU rất chậm")
    return "cpu"


def separate(audio: Path, work_dir: Path) -> Stems:
    """Tách audio thành hai file: giọng và nền.

    Trả về cả hai vì mỗi cái dùng cho một việc khác nhau: ``vocals`` đi vào ASR
    (sạch hơn nên transcript chính xác hơn), ``background`` đi vào bước trộn audio
    làm nền tiếng máy.
    """
    try:
        from demucs.apply import apply_model
        from demucs.audio import save_audio
        from demucs.pretrained import get_model
    except ImportError as exc:
        raise DemucsUnavailable("chưa cài demucs — chỉ có trong image worker") from exc

    work_dir.mkdir(parents=True, exist_ok=True)
    vocals_path = work_dir / "vocals.wav"
    background_path = work_dir / "background.wav"
    if vocals_path.exists() and background_path.exists():
        log.info("demucs.skip", reason="đã có cả hai stem")
        return Stems(vocals_path, background_path)

    device = _device()
    log.info("demucs.start", audio=str(audio), device=device)
    try:
        model = get_model("htdemucs")
        model.to(device)
        wav = _read_audio(audio, model.samplerate, model.audio_channels)
        # shifts=1: không lấy trung bình nhiều lần dịch pha. Chất lượng tăng rất
        # ít mà thời gian tăng theo số lần — với nền chỉ để lót thì không đáng.
        sources = apply_model(
            model, wav[None], device=device, shifts=1, overlap=0.25, progress=False
        )[0]
        names = list(model.sources)
        by_name = dict(zip(names, sources, strict=True))

        kwargs: dict[str, Any] = {
            "samplerate": model.samplerate,
            "bitrate": 128,
            "preset": 2,
            "clip": "rescale",
            "as_float": False,
            "bits_per_sample": 16,
        }
        save_audio(by_name["vocals"].cpu(), str(vocals_path), **kwargs)
        # Cộng mọi stem KHÔNG phải giọng: drums + bass + other. Đó chính là tiếng
        # máy, tiếng bíp, tiếng môi trường — thứ cần giữ.
        background = sum(t for name, t in by_name.items() if name != "vocals")
        save_audio(background.cpu(), str(background_path), **kwargs)
    except Exception as exc:  # noqa: BLE001 — torch/demucs ném nhiều họ exception
        raise SeparationFailed(f"Demucs thất bại: {type(exc).__name__}: {exc}") from exc
    finally:
        # Nhả VRAM ngay: worker còn phải nạp WhisperX và VoxCPM2 sau đó, và ba
        # model cùng ở trên GPU là đường ngắn nhất tới CUDA out of memory.
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    log.info("demucs.done", vocals=str(vocals_path), background=str(background_path))
    return Stems(vocals_path, background_path)


def _read_audio(path: Path, samplerate: int, channels: int):
    from demucs.audio import AudioFile

    return AudioFile(str(path)).read(streams=0, samplerate=samplerate, channels=channels)

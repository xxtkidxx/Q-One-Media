"""Đo chi phí nạp lại model GPU, để quyết định giữ model trên card hay nhả sau mỗi việc.

Chạy trong container worker có GPU:

    make measure-load

Vì sao cần đo: card RTX 3070 8 GB **không đủ** cho Whisper large-v3 (~4,7 GB) và
VoxCPM2 (~5,1 GB) cùng nằm trên đó. Nên buộc phải chọn một trong hai:

* giữ model lại → nhanh, nhưng model kia không nạp được (CUDA out of memory);
* nhả sau mỗi việc → an toàn, nhưng trả giá bằng thời gian nạp lại.

Chọn cách thứ hai chỉ hợp lý nếu biết **giá thật** của nó, và giá đó không đoán được:
lần nạp đầu của VoxCPM2 còn phải biên dịch kernel (``torch.compile``/inductor), lần
sau thì đọc từ cache. Script này đo cả hai lần để thấy phần biên dịch tách khỏi phần
nạp thật.
"""

from __future__ import annotations

import gc
import time


def _vram() -> tuple[float, float]:
    import torch

    if not torch.cuda.is_available():
        return (0.0, 0.0)
    held = torch.cuda.memory_allocated() / 1024**3
    free, _total = torch.cuda.mem_get_info()
    return (held, free / 1024**3)


def _free_vram() -> None:
    gc.collect()
    import torch

    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _report(label: str, seconds: float) -> None:
    held, free = _vram()
    print(f"  {label:22} {seconds:6.1f} s · đang giữ {held:.2f} GB · rảnh {free:.2f} GB")


def measure_voxcpm(rounds: int = 2) -> None:
    from voxcpm import VoxCPM  # type: ignore[import-not-found]

    from src.infrastructure.tts.voxcpm import DEFAULT_MODEL_ID

    print(f"VoxCPM2 ({DEFAULT_MODEL_ID})")
    for i in range(1, rounds + 1):
        t0 = time.monotonic()
        model = VoxCPM.from_pretrained(DEFAULT_MODEL_ID, device="cuda", load_denoiser=False)
        _report(f"nạp lần {i}", time.monotonic() - t0)

        t0 = time.monotonic()
        model.generate(text="Biểu đồ kiểm soát cho thấy quá trình đang trôi.")
        _report(f"sinh giọng lần {i}", time.monotonic() - t0)

        del model
        t0 = time.monotonic()
        _free_vram()
        _report(f"nhả lần {i}", time.monotonic() - t0)


def measure_whisper(rounds: int = 2) -> None:
    from src.infrastructure.asr.whisper import DEFAULT_MODEL, free_vram, load_model

    print(f"\nWhisper ({DEFAULT_MODEL})")
    for i in range(1, rounds + 1):
        t0 = time.monotonic()
        model = load_model()
        _report(f"nạp lần {i}", time.monotonic() - t0)
        del model
        t0 = time.monotonic()
        free_vram()
        _report(f"nhả lần {i}", time.monotonic() - t0)


def main() -> None:
    import torch

    if not torch.cuda.is_available():
        raise SystemExit("không thấy CUDA — chạy trong container worker có GPU")
    name = torch.cuda.get_device_name(0)
    total = torch.cuda.mem_get_info()[1] / 1024**3
    print(f"{name} · {total:.1f} GB VRAM\n")

    measure_whisper()
    measure_voxcpm()

    print(
        "\nĐọc kết quả: nếu 'nạp lần 2' ngắn hơn 'nạp lần 1' đáng kể thì phần chênh là\n"
        "biên dịch kernel, chỉ trả một lần cho mỗi tiến trình. Chi phí thật của việc nhả\n"
        "model sau mỗi việc là con số 'nạp lần 2'."
    )


if __name__ == "__main__":
    main()

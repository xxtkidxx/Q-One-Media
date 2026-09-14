"""Tải model về ``MODEL_CACHE`` một lần, để lần chạy đầu của worker không phải chờ.

Chạy: ``make models``

Vì sao tách thành script thay vì để worker tự tải lúc cần: tải khoảng 10 GB ở
giữa một job nghĩa là job đó chạy 20 phút và trông như bị treo. Tải trước thì
biết rõ mình đang chờ cái gì, và thất bại mạng xảy ra ở chỗ dễ đọc.

Model **không** nằm trong image: ``data/models/`` là bind mount dùng chung dev và
prod, vì model là artifact bất biến chứ không phải state.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

MODEL_CACHE = Path(os.environ.get("MODEL_CACHE", "/models"))

# Kích thước xấp xỉ, để người chạy biết đang chờ bao nhiêu.
PLAN = [
    ("WhisperX large-v3 (nhận dạng lời nguồn)", "~3 GB"),
    ("WhisperX align vi (forced alignment tiếng Việt)", "~1 GB"),
    ("Demucs htdemucs (tách giọng khỏi tiếng máy)", "~300 MB"),
    ("VoxCPM2 openbmb/VoxCPM2 (giọng tiếng Việt)", "~5 GB"),
]


def _say(msg: str) -> None:
    print(msg, flush=True)


def fetch_whisper() -> None:
    """Tải model ASR và model alignment tiếng Việt.

    Hai model khác nhau và **đều cần**: một để đọc lời nguồn (en/zh), một để gióng
    kịch bản tiếng Việt với audio TTS. Thiếu model align thì bước phụ đề chết.
    """
    import whisperx

    _say("→ WhisperX large-v3 …")
    whisperx.load_model("large-v3", "cpu", compute_type="int8", language="en")

    _say("→ WhisperX align model cho tiếng Việt …")
    whisperx.load_align_model(language_code="vi", device="cpu")


def fetch_demucs() -> None:
    from demucs.pretrained import get_model

    _say("→ Demucs htdemucs …")
    get_model("htdemucs")


def fetch_voxcpm() -> None:
    """Tải **VoxCPM2**, không phải VoxCPM-0.5B.

    Bản 0.5B chỉ có ``en`` và ``zh``; chỉ VoxCPM2 có ``vi``. Để thư viện tự chọn
    là rủi ro tải đúng model không dùng được cho dự án này.
    """
    from src.infrastructure.tts.voxcpm import DEFAULT_MODEL_ID

    _say(f"→ {DEFAULT_MODEL_ID} …")
    try:
        from voxcpm import VoxCPM
    except ImportError:
        _say("  (bỏ qua: chưa cài voxcpm trong image này)")
        return
    VoxCPM.from_pretrained(DEFAULT_MODEL_ID)


def main() -> int:
    MODEL_CACHE.mkdir(parents=True, exist_ok=True)
    # HuggingFace và torch đọc biến này để biết cache ở đâu. Đặt ở đây nữa để
    # script chạy đúng cả khi gọi tay ngoài compose.
    os.environ.setdefault("HF_HOME", str(MODEL_CACHE / "huggingface"))
    os.environ.setdefault("TORCH_HOME", str(MODEL_CACHE / "torch"))

    _say(f"Cache: {MODEL_CACHE}")
    for name, size in PLAN:
        _say(f"  · {name} {size}")
    _say("")

    failed: list[str] = []
    for label, fn in (
        ("WhisperX", fetch_whisper),
        ("Demucs", fetch_demucs),
        ("VoxCPM2", fetch_voxcpm),
    ):
        try:
            fn()
        except Exception as exc:  # mỗi thư viện ném một họ exception khác nhau
            # Không dừng ở model đầu tiên lỗi: tải được 2/3 vẫn hơn 0/3, và người
            # chạy cần biết cả ba trạng thái trong một lần chạy.
            failed.append(f"{label}: {type(exc).__name__}: {exc}")
            _say(f"  ✗ {label} thất bại — xem cuối log")

    if failed:
        _say("\nThất bại:")
        for line in failed:
            _say(f"  {line}")
        _say("\nChạy lại được: model đã tải xong không tải lại.")
        return 1

    _say("\nXong. Worker sẽ không phải chờ tải model ở job đầu tiên.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

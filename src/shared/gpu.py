"""Nhả VRAM — dùng chung cho mọi model chạy trên GPU.

Sống ở ``shared`` vì cả ba adapter đều cần (Demucs, Whisper, VoxCPM2) và không adapter
nào nên phụ thuộc adapter khác chỉ để lấy tám dòng này.

**Vì sao phải có hàm riêng, không chỉ gọi ``empty_cache()``:** card của máy này là
RTX 3070 **8 GB**, đo thực tế:

| Model | Giữ trên card | Nạp lần đầu | Nạp lại (cache ấm) |
|---|---|---|---|
| Demucs `htdemucs` | 0,54 GB | — | — |
| Whisper `large-v3` float16 | ~3,5 GB | 20,2 s | 17,5 s |
| VoxCPM2 | **5,12 GB** | 120,9 s | **31,9 s** |

VoxCPM2 một mình đã làm VRAM rảnh về **0,00/8,0 GB**, nên Whisper không nạp nổi sau
nó. Tức là **không thể giữ model lại giữa các việc** trên card này — mỗi model phải
nhả ngay khi xong, và đó là lý do hàm này được gọi trong ``finally`` ở cả ba adapter.

Hai điều dễ làm sai:

1. ``empty_cache()`` **một mình không nhả được gì** khi object model còn sống. Người
   gọi phải ``del`` model **trước**, rồi mới gọi hàm này. Với CTranslate2 (Whisper)
   còn nghiêm hơn: nó cấp bộ nhớ **ngoài** allocator của PyTorch, nên chỉ việc xoá
   object mới trả được vùng đó.
2. Không phải toàn bộ VRAM về lại được: sau khi nhả VoxCPM2, rảnh là 5,44 GB chứ
   không phải 6,93 GB như lúc chưa nạp gì — phần thiếu là CUDA context và workspace
   của cuBLAS/inductor, giữ đến hết tiến trình. 5,44 GB vẫn đủ cho Whisper (~3,5 GB),
   nên chuỗi Demucs → Whisper → VoxCPM2 chạy được; nhưng đây là lề mỏng, và đó là
   điều ``tests/integration/test_gpu_models.py`` canh.
"""

from __future__ import annotations

import gc


def free_vram() -> None:
    """Nhả VRAM. Người gọi **phải** ``del`` object model trước khi gọi.

    Không có GPU hoặc không có torch thì đây là no-op — nhờ vậy adapter gọi được
    trong cả image api (không có torch) mà không phải bọc điều kiện.
    """
    gc.collect()
    try:
        import torch
    except ImportError:
        return
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

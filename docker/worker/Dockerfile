# Worker GPU — yt-dlp, WhisperX, Demucs, VoxCPM2, ffmpeg, script VideoLingo/Easel
# CUDA 12.4 runtime khớp với torch cu124.

FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04 AS base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ffmpeg: bắt buộc. fonts-*: cần cho burn phụ đề tiếng Việt (bẫy glyph U+1Exx,
# xem docs/phuong-an-cuoi-cung.md mục F2.2). libass đi kèm ffmpeg của Ubuntu.
# Python 3.11 từ deadsnakes, KHÔNG từ repo Ubuntu.
#
# Lý do đo được, không phải sở thích: `apt-cache policy python3.11` trên
# jammy-updates chỉ có **3.11.0~rc1** — một release candidate. Không có bản ổn
# định nào trong repo distro. Còn base image CUDA 12.4 chỉ có bản Ubuntu 22.04
# (nvidia không publish 12.4 cho 24.04), nên không thoát được bằng cách đổi base
# mà không kéo theo đổi cả CUDA và torch.
#
# deadsnakes cho 3.11.x ổn định và giữ nguyên CUDA 12.4.
#
# `build-essential` là phụ thuộc **lúc chạy**, không phải lúc build: VoxCPM2 dùng
# `torch.compile` (backend inductor), và inductor sinh mã C++ rồi gọi compiler ngay
# trong lần suy luận đầu tiên. Thiếu gcc thì nạp model ném
# "BackendCompilerFailed … Failed to find C compiler" — lỗi trông như lỗi model,
# thực ra là thiếu gói hệ thống.
RUN apt-get update && apt-get install -y --no-install-recommends \
      software-properties-common gpg-agent \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y --no-install-recommends \
      python3.11 python3.11-venv python3.11-dev python3.11-distutils \
      ffmpeg \
      git curl ca-certificates \
      fonts-dejavu-core fontconfig \
      build-essential \
    && apt-get purge -y software-properties-common gpg-agent \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Font có bộ tiếng Việt đầy đủ. Cài vào image để không phụ thuộc font của host.
COPY docker/worker/fonts/ /usr/share/fonts/truetype/qone/
RUN fc-cache -fv || true

# Ubuntu 22.04 có python3 = 3.10, nhưng code dùng StrEnum và datetime.UTC nên
# BẮT BUỘC 3.11. Gói `python3-pip` của distro cài pip cho 3.10 — dùng nó là cài
# mọi thư viện vào 3.10 rồi symlink `python` sang 3.11, và 3.11 không thấy gì.
# Build vẫn báo "thành công", chỉ đến lúc chạy mới "No module named 'torch'".
# Vì vậy: bootstrap pip cho ĐÚNG 3.11, và mọi lệnh sau đều gọi python3.11 -m pip.
# Dùng get-pip.py chứ không `ensurepip`: Ubuntu gỡ ensurepip khỏi gói python3.11
# của distro, nên lệnh đó thất bại ngay.
RUN curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py && \
    python3.11 /tmp/get-pip.py --no-cache-dir && \
    rm -f /tmp/get-pip.py && \
    python3.11 -m pip install --no-cache-dir --upgrade setuptools wheel && \
    ln -sf /usr/bin/python3.11 /usr/local/bin/python && \
    ln -sf /usr/bin/python3.11 /usr/local/bin/python3

# Chay "python scripts/x.py" dat sys.path[0] = /app/scripts nen khong thay
# package src. PYTHONPATH sua dieu do cho moi script.
ENV PYTHONPATH=/app

WORKDIR /app

# Torch trước và riêng: layer lớn nhất, cache lại được khi requirements đổi.
# torch >= 2.6 là YÊU CẦU CỨNG, không phải chọn bản mới cho vui.
#
# WhisperX gióng tiếng Việt bằng `nguyenvulebinh/wav2vec2-base-vi`, model đó phát
# hành dạng PyTorch `.bin` chứ không phải safetensors. `transformers` 5.x từ chối
# `torch.load` khi torch < 2.6 vì CVE-2025-32434. Hệ quả với torch 2.5.1:
# load_align_model(language_code="vi") ném ValueError, và **forced alignment tiếng
# Việt không chạy được** — tức là mất luôn cơ chế timing phụ đề của F2.5.
#
# Đã xác minh có wheel cu124 cho cp311: torch 2.6.0 và torchaudio 2.6.0.
RUN python3.11 -m pip install --index-url https://download.pytorch.org/whl/cu124 \
      torch==2.6.0 torchaudio==2.6.0

COPY docker/worker/requirements.txt /tmp/requirements.txt
RUN python3.11 -m pip install -r /tmp/requirements.txt

# Chặn ngay tại build nếu python và pip lệch phiên bản. Không có dòng này thì lỗi
# chỉ lộ ra lúc chạy, dưới dạng "No module named 'torch'" — thông báo không nói gì
# về nguyên nhân thật.
RUN python - <<'PY'
import sys

assert sys.version_info[:2] == (3, 11), sys.version
# Ubuntu 22.04 chi co python3.11 = 3.11.0~rc1 (release candidate) nen phai lay
# qua deadsnakes. Neu ai doi base image, dong duoi bat lai ngay.
assert "rc" not in sys.version, f"Python release candidate: {sys.version}"

import torch

v = tuple(int(x) for x in torch.__version__.split("+")[0].split(".")[:2])
# transformers 5.x tu choi torch.load khi torch < 2.6 (CVE-2025-32434), va duong
# giong tieng Viet di qua transformers — nen torch cu la khong chay duoc.
assert v >= (2, 6), f"torch {torch.__version__} < 2.6"

import ctranslate2

c = tuple(int(x) for x in ctranslate2.__version__.split(".")[:2])
# ctranslate2 < 4.5 link cuDNN 8, con base image CUDA 12.4 mang cuDNN 9. Sai o day
# thi CTranslate2 abort CUNG ca tien trinh (Fatal Python error: Aborted) — khong
# try/except nao bat duoc, nen phai chan ngay tai build.
assert c >= (4, 5), f"ctranslate2 {ctranslate2.__version__} < 4.5 link cuDNN 8"

# Import that, khong chi kiem phien ban: thieu thu vien he thong thi chi import moi lo.
import demucs  # noqa: F401
import faster_whisper  # noqa: F401
import voxcpm  # noqa: F401

print("torch", torch.__version__, "| ctranslate2", ctranslate2.__version__)
PY

# Model KHÔNG bake vào image — tải vào /models (bind mount ../data/models)
# bằng scripts/fetch_models.py để đổi image không phải tải lại ~10 GB.
ENV HF_HOME=/models/huggingface \
    TORCH_HOME=/models/torch \
    MEDIA_ROOT=/data/media

# ---------- dev ----------
FROM base AS dev
RUN python3.11 -m pip install pytest pytest-asyncio ruff
# Code mount từ host qua compose.dev — không COPY ở đây.
CMD ["python", "-m", "src.interfaces.worker.main"]

# ---------- prod ----------
FROM base AS prod
COPY src/ /app/src/
COPY scripts/ /app/scripts/
COPY vendor/ /app/vendor/
RUN useradd -m -u 10001 qone && chown -R qone:qone /app
USER qone
CMD ["python", "-m", "src.interfaces.worker.main"]

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
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3.11 python3.11-venv python3.11-dev \
      ffmpeg \
      git curl ca-certificates \
      fonts-dejavu-core fontconfig \
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
RUN python3.11 -m pip install --index-url https://download.pytorch.org/whl/cu124 \
      torch==2.5.1 torchaudio==2.5.1

COPY docker/worker/requirements.txt /tmp/requirements.txt
RUN python3.11 -m pip install -r /tmp/requirements.txt

# Chặn ngay tại build nếu python và pip lệch phiên bản. Không có dòng này thì lỗi
# chỉ lộ ra lúc chạy, dưới dạng "No module named 'torch'" — thông báo không nói gì
# về nguyên nhân thật.
RUN python -c "import sys; assert sys.version_info[:2] == (3, 11), sys.version" && \
    python -c "import torch, whisperx, demucs, voxcpm; print('torch', torch.__version__)"

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

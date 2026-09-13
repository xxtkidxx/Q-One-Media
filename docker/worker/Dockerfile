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
      python3.11 python3.11-venv python3-pip \
      ffmpeg \
      git curl ca-certificates \
      fonts-dejavu-core fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Font có bộ tiếng Việt đầy đủ. Cài vào image để không phụ thuộc font của host.
COPY docker/worker/fonts/ /usr/share/fonts/truetype/qone/
RUN fc-cache -fv || true

RUN ln -sf /usr/bin/python3.11 /usr/local/bin/python && \
    ln -sf /usr/bin/python3.11 /usr/local/bin/python3

WORKDIR /app

# Torch trước và riêng: layer lớn nhất, cache lại được khi requirements đổi.
RUN pip install --index-url https://download.pytorch.org/whl/cu124 \
      torch==2.5.1 torchaudio==2.5.1

COPY docker/worker/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# Model KHÔNG bake vào image — tải vào /models (bind mount ../data/models)
# bằng scripts/fetch_models.py để đổi image không phải tải lại ~10 GB.
ENV HF_HOME=/models/huggingface \
    TORCH_HOME=/models/torch \
    MEDIA_ROOT=/data/media

# ---------- dev ----------
FROM base AS dev
RUN pip install pytest pytest-asyncio ruff
# Code mount từ host qua compose.dev — không COPY ở đây.
CMD ["python", "-m", "src.worker.main"]

# ---------- prod ----------
FROM base AS prod
COPY src/ /app/src/
COPY vendor/ /app/vendor/
RUN useradd -m -u 10001 qone && chown -R qone:qone /app
USER qone
CMD ["python", "-m", "src.worker.main"]

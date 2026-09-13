# API — hộp thư URL, license gate, job queue, publish dispatch.
# Không cần GPU, không cần ffmpeg: mọi việc nặng do worker làm.

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY docker/api/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

ENV MEDIA_ROOT=/data/media

# ---------- dev ----------
FROM base AS dev
RUN pip install pytest pytest-asyncio httpx ruff
EXPOSE 8000
CMD ["uvicorn", "src.interfaces.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---------- prod ----------
FROM base AS prod
COPY src/ /app/src/
RUN useradd -m -u 10001 qone && chown -R qone:qone /app
USER qone
EXPOSE 8000
CMD ["uvicorn", "src.interfaces.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

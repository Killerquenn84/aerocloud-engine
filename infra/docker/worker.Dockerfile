# syntax=docker/dockerfile:1.7
# AeroCloud Worker — Celery + GPU
# Based on NVIDIA CUDA 12.1 runtime for PyTorch + nvdiffrast

FROM nvidia/cuda:12.1.1-devel-ubuntu22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-dev python3-pip git build-essential \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY packages/ ./packages/
COPY apps/ ./apps/

RUN uv python install 3.11 && \
    uv sync --frozen --no-dev --package aerocloud-worker

# ----- Runtime stage -----
FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04 AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    CUBLAS_WORKSPACE_CONFIG=":4096:8"

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app /app

# D-23: Copy worker entrypoint script (created in Plan 03)
COPY infra/docker/worker-entrypoint.sh /app/infra/docker/worker-entrypoint.sh
RUN chmod +x /app/infra/docker/worker-entrypoint.sh

# D-23: Clean shutdown — SIGTERM triggers Celery warm shutdown (drain in-flight tasks).
# stop_grace_period: 30s in docker-compose gives the worker time to finish.
STOPSIGNAL SIGTERM

# Health check: ping the Celery worker via inspect. Timeout -t 5 < Docker timeout 10s.
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD celery -A aerocloud_worker.celery_app inspect ping -t 5 || exit 1

CMD ["python", "-c", "import aerocloud_worker; print('aerocloud-worker', aerocloud_worker.__version__)"]

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

# Phase 12 will add the actual Celery app. For Phase 1 we expose the entrypoint.
CMD ["python", "-c", "import aerocloud_worker; print('aerocloud-worker', aerocloud_worker.__version__)"]

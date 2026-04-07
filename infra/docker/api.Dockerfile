# syntax=docker/dockerfile:1.7
# AeroCloud API — FastAPI HTTP surface
# CPU-only image (worker handles GPU work)

FROM python:3.11-slim-bookworm AS builder

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY packages/ ./packages/
COPY apps/ ./apps/

RUN uv sync --frozen --no-dev --package aerocloud-api

# ----- Runtime stage -----
FROM python:3.11-slim-bookworm AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=builder /app /app

EXPOSE 8000

# Phase 12 will add the actual FastAPI app. For Phase 1 we expose the entrypoint.
CMD ["python", "-c", "import aerocloud_api; print('aerocloud-api', aerocloud_api.__version__)"]

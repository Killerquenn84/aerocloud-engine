---
title: Phase 1 Foundation — Research
slug: 01-research
created: 2026-04-07
tags: [phase-1, research, gemini, foundation]
source: Gemini CLI
---

# Phase 1 Foundation — Research

**Researched by:** Gemini CLI (April 2026)
**Purpose:** Concrete file templates and patterns for Phase 1 planning. Downstream consumer: the planner writing PLAN.md.

## 1. Root `pyproject.toml` — uv workspace root

```toml
[tool.uv]
managed = true
package = false

[tool.uv.workspace]
members = [
    "packages/engine",
    "apps/api",
    "apps/worker",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "A", "C4", "T20", "RET", "SIM", "ARG", "PTH", "ERA", "PL", "RUF"]
ignore = ["PLR0913"]  # ML often needs many args

[tool.ruff.lint.isort]
known-first-party = ["aerocloud", "aerocloud_api", "aerocloud_worker"]

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true
disallow_untyped_defs = true
check_untyped_defs = true
warn_return_any = true
warn_unused_configs = true
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false

[tool.pytest.ini_options]
minversion = "7.0"
addopts = "-ra -q"
testpaths = ["tests/unit", "tests/integration"]
pythonpath = ["packages/engine/src", "apps/api/src", "apps/worker/src"]
markers = [
    "gpu: requires CUDA-capable GPU (skipped on CPU-only hosts)",
    "slow: long-running tests",
    "integration: spins up postgres+redis via testcontainers",
]
env = ["CUBLAS_WORKSPACE_CONFIG=:4096:8"]
```

## 2. `packages/engine/pyproject.toml`

Codex-verified versions pinned. `nvdiffrast` is fetched from the NVlabs GitHub (no PyPI wheel in 0.3.3.1).

```toml
[project]
name = "aerocloud-engine"
version = "0.1.0"
description = "Core geometric and ML engine for AeroCloud"
readme = "README.md"
requires-python = ">=3.11,<3.12"
authors = [{ name = "AeroCloud Team" }]
dependencies = [
    "torch==2.7.1",
    "numpy==2.4.3",
    "scipy==1.17.1",
    "scikit-learn==1.8.0",
    "scikit-fmm==2025.6.23",
    "opencv-python-headless==4.12.*",
    "Pillow==12.1.1",
    "POT==0.9.6.post1",
    "sentence-transformers==5.3.0",
    "transformers==5.5.0",
    "pyribs>=0.7.0",
    "pydantic==2.12.5",
    "pydantic-settings>=2.5.0",
    "structlog>=24.0.0",
    "opentelemetry-sdk>=1.28.0",
    "svgelements>=1.9.6",
    "reportlab==4.3.*",
    "orjson==3.11.*",
    "tenacity>=9.0.0",
    "nh3==0.3.3",
    "safetensors>=0.4.5",
    "spacy[de,en]>=3.7,<4.0",
]

[project.optional-dependencies]
diff-rendering = [
    # nvdiffrast is installed via tool.uv.sources below (git)
]

[tool.uv.sources]
nvdiffrast = { git = "https://github.com/NVlabs/nvdiffrast.git", rev = "v0.3.3" }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/aerocloud"]
```

## 3. Apps Skeletons

### `apps/api/pyproject.toml`

```toml
[project]
name = "aerocloud-api"
version = "0.1.0"
description = "FastAPI HTTP surface for AeroCloud Engine"
requires-python = ">=3.11,<3.12"
dependencies = [
    "aerocloud-engine",
    "fastapi==0.115.*",
    "uvicorn[standard]==0.43.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/aerocloud_api"]
```

### `apps/worker/pyproject.toml`

```toml
[project]
name = "aerocloud-worker"
version = "0.1.0"
description = "Celery worker for AeroCloud Engine GPU jobs"
requires-python = ">=3.11,<3.12"
dependencies = [
    "aerocloud-engine",
    "celery[redis]==5.6.2",
    "redis[hiredis]==7.3.0",
    "asyncpg==0.31.0",
    "pgvector==0.4.2",
    "alembic>=1.13.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/aerocloud_worker"]
```

## 4. `infra/docker/worker.Dockerfile`

```dockerfile
# syntax=docker/dockerfile:1.7
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

RUN uv sync --frozen --no-dev --package aerocloud-worker

FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04 AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    CUBLAS_WORKSPACE_CONFIG=":4096:8"

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app /app

CMD ["celery", "-A", "aerocloud_worker.app", "worker", "--loglevel=info", "--pool=prefork", "--concurrency=1", "--max-tasks-per-child=50"]
```

### `infra/docker/api.Dockerfile` (no GPU needed)

```dockerfile
# syntax=docker/dockerfile:1.7
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

FROM python:3.11-slim-bookworm AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=builder /app /app

CMD ["uvicorn", "aerocloud_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### `infra/docker/docker-compose.yml`

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: aerocloud
      POSTGRES_USER: aerocloud
      POSTGRES_PASSWORD: devpassword
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./postgres-init.sql:/docker-entrypoint-initdb.d/00-init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U aerocloud"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --save "" --appendonly no
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  api:
    build:
      context: ../..
      dockerfile: infra/docker/api.Dockerfile
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://aerocloud:devpassword@postgres:5432/aerocloud
      REDIS_URL: redis://redis:6379/0
      LOG_LEVEL: INFO
      SEED: "42"
    ports:
      - "8000:8000"

  worker:
    build:
      context: ../..
      dockerfile: infra/docker/worker.Dockerfile
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://aerocloud:devpassword@postgres:5432/aerocloud
      REDIS_URL: redis://redis:6379/0
      LOG_LEVEL: INFO
      SEED: "42"
      CUBLAS_WORKSPACE_CONFIG: ":4096:8"

volumes:
  postgres-data:
```

### `infra/docker/postgres-init.sql`

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## 5. `.github/workflows/ci-python.yml`

```yaml
name: CI Python

on:
  push:
    branches: [main]
  pull_request:
    paths:
      - 'packages/**'
      - 'apps/**'
      - 'tests/**'
      - 'pyproject.toml'
      - 'uv.lock'
      - '.github/workflows/ci-python.yml'

jobs:
  lint-test:
    runs-on: ubuntu-latest
    env:
      CUBLAS_WORKSPACE_CONFIG: ":4096:8"
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"

      - name: Set up Python 3.11
        run: uv python install 3.11

      - name: Sync workspace
        run: uv sync --frozen

      - name: Ruff format check
        run: uv run ruff format --check .

      - name: Ruff lint
        run: uv run ruff check .

      - name: Mypy strict
        run: uv run mypy packages/engine/src apps/api/src apps/worker/src

      - name: Pytest unit
        run: uv run pytest tests/unit -v

      - name: Pytest integration
        run: uv run pytest tests/integration -v
```

## 6. `packages/engine/src/aerocloud/utils/determinism.py`

```python
"""Global determinism controls — call set_seed() at the start of every process."""
from __future__ import annotations

import os
import random

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


def set_seed(seed: int = 42) -> None:
    """Set global seeds for reproducibility across all libraries.

    Covers: Python random, numpy, torch (CPU + CUDA), cuDNN, cuBLAS.

    Must be called once at process startup (API lifespan hook, Celery worker init,
    test fixture). Subsequent calls are idempotent.
    """
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    np.random.seed(seed)

    # Torch is imported lazily — on CPU-only hosts without CUDA, torch.cuda is still callable
    import torch

    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

    # Required for deterministic cuBLAS GEMM operations on CUDA 10.2+
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.use_deterministic_algorithms(True, warn_only=True)

    logger.info("determinism.set_seed", seed=seed)
```

## 7. `tests/unit/test_determinism.py`

```python
"""Verifies global seeding produces identical outputs across runs."""
from __future__ import annotations

import numpy as np
import torch

from aerocloud.utils.determinism import set_seed


def _sample() -> tuple[np.ndarray, torch.Tensor]:
    np_arr = np.random.randn(10, 10)
    torch_t = torch.randn(10, 10)
    return np_arr, torch_t


def test_seed_reproducibility() -> None:
    set_seed(42)
    np_a, torch_a = _sample()

    set_seed(42)
    np_b, torch_b = _sample()

    assert np.array_equal(np_a, np_b)
    assert torch.equal(torch_a, torch_b)


def test_different_seeds_produce_different_outputs() -> None:
    set_seed(42)
    np_a, torch_a = _sample()

    set_seed(123)
    np_b, torch_b = _sample()

    assert not np.array_equal(np_a, np_b)
    assert not torch.equal(torch_a, torch_b)
```

## 8. `.github/workflows/ci-typescript.yml`

```yaml
name: CI TypeScript (Wiki Tools)

on:
  push:
    branches: [main]
  pull_request:
    paths:
      - 'src/**'
      - 'scripts/**'
      - 'wiki/**'
      - 'package.json'
      - 'package-lock.json'
      - 'tsconfig.json'
      - '.github/workflows/ci-typescript.yml'

jobs:
  lint-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Typecheck
        run: npm run typecheck

      - name: Wiki lint
        run: npm run wiki:lint

      - name: Tests
        run: npm test
```

## 9. `.github/workflows/ci-integrity.yml`

```yaml
name: CI Integrity

on:
  pull_request:

jobs:
  integrity:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Validate workflows
        uses: docker://rhysd/actionlint:latest

      - name: Check for secrets
        run: |
          if grep -rE 'sk-[a-zA-Z0-9]{32,}|AKIA[0-9A-Z]{16}|ghp_[a-zA-Z0-9]{36}' \
            --include="*.py" --include="*.ts" --include="*.md" \
            --exclude-dir="node_modules" .; then
            echo "Potential secret leak detected!"
            exit 1
          fi
```

## Gotchas & Notes

- **nvdiffrast via git**: No PyPI wheel for 0.3.3.1. Use `tool.uv.sources` with git rev `v0.3.3`. CI must have build tools installed.
- **torch==2.7.1 wheel source**: Default PyPI wheels include CUDA 12.1 support. No need for extra index URL unless targeting a specific CUDA version.
- **`torch.use_deterministic_algorithms(True, warn_only=True)`**: `warn_only=True` lets CUDA operations that don't have deterministic implementations warn instead of throwing — important because nvdiffrast may use some non-deterministic ops.
- **`CUBLAS_WORKSPACE_CONFIG=:4096:8`**: Must be set BEFORE torch imports (set in Dockerfile ENV, docker-compose environment, and pytest env).
- **GPU tests**: Keep out of the default CI runner. Use `@pytest.mark.gpu` and filter with `pytest -m "not gpu"` on cloud runners.

---

*Research complete. Downstream consumer: gsd-planner writing 01-PLAN.md.*

## Wiki-Related Pages

- [knowledge/phase-01-plan.md](knowledge/phase-01-plan.md) — Phase 1 PLAN.md that consumes these templates
- [knowledge/stack-versions.md](knowledge/stack-versions.md) — Codex-verified library versions
- [research/stack.md](research/stack.md) — Full stack research
- [research/architecture.md](research/architecture.md) — Monorepo best practices
- [discussions/2026-04-07-phase-01-context.md](discussions/2026-04-07-phase-01-context.md) — Phase 1 decisions

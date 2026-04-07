---
title: "Phase 1 Foundation — Context (3-AI consensus)"
slug: 2026-04-07-phase-01-context
created: 2026-04-07
tags: [discussion, phase-1, foundation, 3-ai-consensus]
source: mirrored from .planning/phases/01-foundation/01-CONTEXT.md
---

# Phase 1: Foundation - Context

**Gathered:** 2026-04-07 (assumptions mode with 3-AI consensus: Claude + Gemini + Codex)
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish the reproducible polyglot runtime foundation: monorepo skeleton, Docker + NVIDIA-Docker base, CI pipelines, deterministic seeding, local dev database stack (PostgreSQL+pgvector, Redis), GPU smoke test, bundled fonts, observability baseline. Goal is that a fresh clone can run `docker compose up`, `pytest` (green), and CI passes on a PR. NO engine logic is implemented in this phase — that begins in Phase 3 (NLP-v1).

This phase covers requirements **FOUND-01 to FOUND-12** from REQUIREMENTS.md.
</domain>

<decisions>
## Implementation Decisions

### Repository Structure — Hybrid (3-AI consensus: Option A)

- **D-01:** TypeScript Wiki-Tools and existing `scripts/` stay at repo root. No migration to `tools/wiki/` in Phase 1.
  - Rationale: `scripts/nightly-research.sh` is cron-coupled with absolute paths, `scripts/telegram-send.sh` is infrastructure-critical, `package.json` scripts reference `scripts/*.ts`. Moving them in Phase 1 breaks cron, the Telegram workflow, and existing CI expectations.
  - Codex explicitly blocked Gemini's "migrate to tools/wiki/" proposal for Phase 1.
- **D-02:** Python engine lives in `packages/engine/` with its own `pyproject.toml`. Source layout: `packages/engine/src/aerocloud/`.
- **D-03:** Root has a dual-language setup:
  - `package.json` + `tsconfig.json` + `src/` + `scripts/` (existing, untouched)
  - NEW: `pyproject.toml` (uv workspace root) referencing `packages/engine`, `apps/api`, `apps/worker`
- **D-04:** Apps directory (`apps/api/`, `apps/worker/`) are created as Python package skeletons in Phase 1. They contain empty `pyproject.toml` + `src/aerocloud_api/__init__.py` / `src/aerocloud_worker/__init__.py` — no FastAPI routes or Celery tasks yet (those come in Phase 12).
- **D-05:** Rust workspace `packages/preview-wasm/` is created as a skeleton with `Cargo.toml` + `src/lib.rs` — no WASM code yet (Phase 3+ WASM browser preview work).

### Python Package Manager & Workspace

- **D-06:** `uv` (astral-sh) as the sole Python package manager. No pip, no poetry, no hatch.
- **D-07:** Root `pyproject.toml` uses `[tool.uv.workspace]` with `members = ["packages/engine", "apps/api", "apps/worker"]`.
- **D-08:** Single root `uv.lock` for the entire Python workspace — no per-package lockfiles.
- **D-09:** Python version pinned to **3.11** in every `pyproject.toml` via `requires-python = ">=3.11,<3.12"`.

### Docker & CUDA Base

- **D-10:** Multi-stage Dockerfiles in `infra/docker/`:
  - `api.Dockerfile` — FastAPI runtime (minimal CPU image is fine)
  - `worker.Dockerfile` — GPU worker image based on `nvidia/cuda:12.1.1-runtime-ubuntu22.04`
  - `docker-compose.yml` — local dev stack: postgres-pgvector, redis, api, worker
- **D-11:** Base image SHA-pinning: Phase 1 uses stable tags (`nvidia/cuda:12.1.1-runtime-ubuntu22.04`, `postgres:16-alpine`, `redis:7-alpine`). SHA pins are added once images are verified working on Hostinger VPS (deferred to Phase 12 release gate).
- **D-12:** `docker-compose.yml` exposes:
  - `postgres:5432` (with `pgvector` extension)
  - `redis:6379`
  - `api:8000`
  - `worker:0` (no external port — Celery only)

### Dev Stack (local `docker compose up`)

- **D-13:** PostgreSQL 16 with `pgvector` extension enabled via init SQL script (`infra/docker/postgres-init.sql` → `CREATE EXTENSION IF NOT EXISTS vector;`).
- **D-14:** Redis 7 with AOF persistence disabled for dev (fast startup).
- **D-15:** Alembic baseline migration **NOT** created in Phase 1 — that's Phase 2 scope. Phase 1 only installs Alembic as dependency.

### Determinism Foundation

- **D-16:** Global `set_seed(seed: int) -> None` lives in `packages/engine/src/aerocloud/utils/determinism.py`.
  - Sets `random.seed(seed)`, `numpy.random.seed(seed)`, `torch.manual_seed(seed)`, `torch.cuda.manual_seed_all(seed)`, `torch.use_deterministic_algorithms(True)`, `torch.backends.cudnn.deterministic = True`, `torch.backends.cudnn.benchmark = False`
- **D-17:** `CUBLAS_WORKSPACE_CONFIG=:4096:8` set in `docker-compose.yml` environment AND in `Dockerfile` ENV AND in `pytest.ini` for test runs.
- **D-18:** A `tests/unit/test_determinism.py` test asserts `set_seed(42)` produces identical numpy + torch outputs across repeated runs (Success Criterion #3 from ROADMAP.md).

### CI Pipeline

- **D-19:** GitHub Actions. Workflows in `.github/workflows/`:
  - `ci-python.yml` — Python jobs (paths-filter on `packages/**`, `apps/**`, `tests/**`, `pyproject.toml`, `uv.lock`)
  - `ci-typescript.yml` — TS Wiki tooling (paths-filter on `src/**`, `scripts/**`, `package.json`, `tsconfig.json`, `wiki/**`)
  - `ci-rust.yml` — Rust skeleton (paths-filter on `packages/preview-wasm/**`)
  - `ci-integrity.yml` — Repo-wide lint without paths-filter (YAML lint, commit message check, lockfile drift)
- **D-20:** Python CI job steps: `uv sync` → `uv run mypy --strict packages/engine/src apps/api/src apps/worker/src` → `uv run ruff check` → `uv run ruff format --check` → `uv run pytest tests/unit tests/integration`
- **D-21:** Python CI caching via `astral-sh/setup-uv` action (built-in cache handling).
- **D-22:** TS CI keeps the existing `npm test` + `npm run typecheck` + `npm run wiki:lint`.
- **D-23:** GPU-dependent tests marked with `@pytest.mark.gpu` and skipped when `torch.cuda.is_available()` is False. GitHub Actions runners do NOT have GPUs — gpu tests run only on self-hosted runner or manually on VPS.

### Configuration Management

- **D-24:** `pydantic-settings` v2 for all config. Primary env vars: `DATABASE_URL`, `REDIS_URL`, `GPU_DEVICE`, `MODEL_CACHE_DIR`, `LOG_LEVEL`, `SEED`.
- **D-25:** `.env.example` at repo root documents every required env var (no secrets). `.env` remains gitignored.
- **D-26:** Settings class lives in `packages/engine/src/aerocloud/config.py` as a single source of truth. Apps (api, worker) import from engine.

### Observability Foundation

- **D-27:** `structlog` (not loguru) configured in `packages/engine/src/aerocloud/logging.py` to emit JSON to stdout. Log level from `LOG_LEVEL` env var.
- **D-28:** OpenTelemetry SDK initialized in the same module. In Phase 1 only the SDK import + minimal tracer setup; exporters are configured but pointed at `localhost:4317` (OTLP default) — the actual collector is added in Phase 12.
- **D-29:** Prometheus exporter **NOT** added in Phase 1. It's bundled with the API/worker deployment in Phase 12.

### GPU Smoke Test

- **D-30:** `scripts/gpu-smoke-test.py` (new Python script) reports `torch.__version__`, `torch.cuda.is_available()`, `torch.cuda.device_count()`, compute capability of each device.
  - Exits 0 on CPU-only host (graceful skip)
  - Exits 0 if at least one device has compute capability ≥ 6.0
  - Exits 1 otherwise (compute capability too low)
- **D-31:** A companion `pytest` test `tests/gpu/test_cuda_capability.py` wraps the smoke test logic with `@pytest.mark.gpu` marker.

### Bundled Fonts

- **D-32:** Fonts live in `packages/engine/assets/fonts/`. Phase 1 ships with at least 2 open-source font families:
  - **Inter** (SIL Open Font License) — sans-serif workhorse
  - **IBM Plex Serif** (SIL Open Font License) — serif for variety
- **D-33:** Font loading registered once at engine module import time in `packages/engine/src/aerocloud/fonts.py` (a module-level Set prevents re-registration per render — addresses Pitfall #2 Canvas memory leak).
- **D-34:** Font license files (`OFL.txt`) included alongside `.ttf` files; `packages/engine/assets/fonts/LICENSES.md` lists all bundled fonts with their licenses.

### Tests Layout

- **D-35:** Test tree:
  - `tests/unit/` — pure-function tests, no I/O (pytest + hypothesis)
  - `tests/integration/` — uses `testcontainers` for real Postgres + Redis
  - `tests/gpu/` — GPU-dependent tests marked `@pytest.mark.gpu`
- **D-36:** `pytest.ini` (or `tool.pytest.ini_options` in root `pyproject.toml`) defines custom markers (`gpu`, `slow`, `integration`) and sets `CUBLAS_WORKSPACE_CONFIG` env var.

### Code Quality Tools

- **D-37:** `ruff` for lint AND format (no Black). Config in root `pyproject.toml` `[tool.ruff]`.
- **D-38:** `mypy --strict` mode, config in root `pyproject.toml` `[tool.mypy]`. Excludes `tests/` from strict mode (too verbose for test fixtures).
- **D-39:** `hypothesis` configured with `deadline=None` for CI to avoid flakiness on slow runners.
- **D-40:** `mutmut` **NOT** installed in Phase 1 (comes in Phase 6 when Loss module exists). Only listed in planning notes as a future dev dep.

### What Phase 1 does NOT deliver

- No FastAPI routes (Phase 12)
- No Celery tasks (Phase 12)
- No PyTorch model code (Phase 5+)
- No BERT download/warmup (Phase 8)
- No Alembic migrations (Phase 2)
- No actual Rust/WASM implementation (Phase 3 WASM preview)
- No Prometheus metrics (Phase 12)
- No nightly Self-Play scheduler (already exists for research — engine Self-Play is Phase 10)
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing Phase 1.**

### Project-level specs

- `.planning/PROJECT.md` — Full Blueprint v1 vision, polyglot stack, constraints, 11 Key Decisions
- `.planning/REQUIREMENTS.md` — FOUND-01 to FOUND-12 (Phase 1 requirements)
- `.planning/ROADMAP.md` — Phase 1 section with success criteria and risk mapping

### Research artifacts

- `.planning/research/STACK.md` — Codex-verified library versions (April 2026): Python 3.11, uv, torch 2.7.1, etc.
- `.planning/research/ARCHITECTURE.md` — Monorepo layout, Celery+asyncio separation, GPU resource management
- `.planning/research/PITFALLS.md` — 18 known risks; Phase 1 addresses #10 (NVIDIA-Docker), #11 (determinism), #18 (reproducibility)
- `.planning/research/SUMMARY.md` — Cross-cutting risks synthesis

### Wiki (mirrored, linked)

- `wiki/knowledge/stack-versions.md` — Codex-verified versions as living reference
- `wiki/corrections/2026-04-07-stack-hallucinations.md` — Why we use `nvdiffrast 0.3.3.1`, `POT 0.9.6.post1`, etc.
- `wiki/decisions/2026-04-07-polyglot-stack-selection.md` — 3-AI consensus log
- `wiki/research/architecture.md` — Turborepo-deferred rationale

### Source material

- `raw/sources/AeroCloud-Blueprint.md` — Blueprint Teil XI (IT-Infrastructure)
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`scripts/ingest.ts`, `scripts/query.ts`, `scripts/lint-wiki.ts`** — Wiki tooling in TypeScript. Stay at root, untouched. `package.json` scripts (`wiki:ingest`, `wiki:query`, `wiki:lint`) remain functional.
- **`scripts/nightly-research.sh`** — Cron-scheduled nightly gemini research. Absolute paths, stays at root.
- **`scripts/telegram-send.sh`** — Infrastructure-critical Telegram notifier. Stays at root.
- **`scripts/lint-wiki.ts`** — Recently updated to recurse full depth; handles the new wiki subdirectories (code/, corrections/, decisions/, discussions/, knowledge/, research/, tests/, bugs/).
- **`.nvmrc`** — Node.js 22 pin already present.
- **`tsconfig.json`** — Strict TS config; stays unchanged.
- **`.env.telegram`** — Established pattern for secret env files.

### Established Patterns

- **Karpathy LLM Wiki** — `wiki/` directory with subcategories (code/, corrections/, decisions/, discussions/, knowledge/, research/, tests/, bugs/). Linted by `scripts/lint-wiki.ts` on every PR. Phase 1 must ensure this continues to work (CI job `ci-typescript.yml`).
- **.env.*** — Secret files follow `.env.*` naming (e.g. `.env.telegram`). gitignored.
- **3-AI workflow** — Claude orchestrates, Gemini researches, Codex reviews. Documented in CLAUDE.md sections 1, 4, 6. Phase 1 adheres via this CONTEXT.md itself.

### Integration Points

- **`wiki/log.md`** — Every Phase commit should append a log entry.
- **`docs/ai-team-decisions.md`** — Every architectural decision should be mirrored here (Regel 4).
- **Root `scripts/`** — New scripts (`gpu-smoke-test.py`, etc.) live alongside existing ones.
- **`.planning/STATE.md`** — Updated with Phase 1 active/complete status.
- **Cron (`crontab -l` for aerocloud user)** — Already has `scripts/nightly-research.sh` at 02:00 Europe/Berlin. Phase 1 must not break it.
</code_context>

<specifics>
## Specific Ideas

- Jens explicitly requested **full Blueprint v1 vision — no scope reduction**. Phase 1 Foundation must support all 12 downstream phases without later rework.
- Jens explicitly requested **Fine granularity** (10–12 phases) — Phase 1 is intentionally narrow and only establishes infrastructure.
- **Codex quote:** "Verschiebt Domänenlogik, nicht operative Entrypoints. Root wird 'compat layer'." — Guide for this phase.
- **Gemini quote:** "uv ignoriert package.json. Du kannst beide im Root führen." — Confirms no technical conflict between dual package managers at root.
- Hostinger Cloud VPS deployment target means NVIDIA-Docker toolkit compatibility must be validated in Phase 12 on real VPS. Phase 1 only validates it works locally.
</specifics>

<deferred>
## Deferred Ideas

- **Migration of TS wiki-tools to `tools/wiki/` workspace** — Gemini recommended this, Codex blocked it for Phase 1 due to cron-coupling. Revisit as its own phase after Phase 12 release, OR never if the hybrid layout proves sustainable.
- **SHA-pinned Docker base images** — deferred to Phase 12 release gate once images verified on Hostinger VPS.
- **Alembic baseline migration** — Phase 2 (Datenmodell + Wiki).
- **Turborepo orchestration** — Codex-deferred until JS task orchestration "genuinely hurts". Not in Phase 1.
- **BERT model pre-download in Dockerfile** — Phase 8 (Semantic Vector Space).
- **CUDA compute capability check enforcement** — Phase 1 reports it, Phase 12 may refuse to start on insufficient hardware.
- **Prometheus + NVIDIA DCGM exporter** — Phase 12 observability.
- **mutmut mutation testing setup** — Phase 6 (Inner Loop Loss module exists by then).
- **Python CI job with GPU** — GitHub Actions cloud runners have no GPU. Self-hosted GPU runner or VPS-triggered workflow is a Phase 12 topic.

### Reviewed Todos (not folded)

None — no todos in the backlog matching Phase 1 scope.
</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-04-07*
*3-AI consensus: Claude (orchestrator) + Gemini (research) + Codex (critic) — Option A Hybrid confirmed*

## Wiki-Related Pages

- [knowledge/stack-versions.md](knowledge/stack-versions.md) — Library-Versionen fuer Phase 1 Foundation
- [knowledge/project-specification.md](knowledge/project-specification.md) — Projekt-Kontext
- [knowledge/roadmap-v1.md](knowledge/roadmap-v1.md) — Roadmap mit Phase 1 Position
- [knowledge/requirements-v1.md](knowledge/requirements-v1.md) — FOUND-01 bis FOUND-12
- [research/stack.md](research/stack.md) — Stack Research Details
- [research/architecture.md](research/architecture.md) — Monorepo Best Practices
- [research/pitfalls.md](research/pitfalls.md) — Phase 1 addresses #10 #11 #18
- [decisions/2026-04-07-polyglot-stack-selection.md](decisions/2026-04-07-polyglot-stack-selection.md) — Vorherige Decision Logs
- [corrections/2026-04-07-stack-hallucinations.md](corrections/2026-04-07-stack-hallucinations.md) — Warum wir nvdiffrast 0.3.3.1 pinnen

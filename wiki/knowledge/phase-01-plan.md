---
title: Phase 1 Foundation — Plan
slug: 01-plan
created: 2026-04-07
tags: [phase-1, plan, foundation, tasks]
phase: 01-foundation
requirements: [FOUND-01, FOUND-02, FOUND-03, FOUND-04, FOUND-05, FOUND-06, FOUND-07, FOUND-08, FOUND-09, FOUND-10, FOUND-11, FOUND-12]
---

# Phase 1: Foundation — Executable Plan

**Goal:** Reproducible polyglot runtime foundation. A fresh clone must run `docker compose up`, `pytest` (green), and CI green on a PR.

**Prerequisites:** None (Phase 1 is the first phase).

**Downstream:** Phase 2 (Datenmodell + Wiki) depends on this Foundation.

## Task Breakdown (Waves)

Tasks are grouped into **waves** that execute in order. Within a wave, tasks can be parallelized.

### Wave 0 — Snapshot the Existing State

**Goal:** Protect existing TS wiki tooling + cron before touching the repo.

- **T-0.1** Verify working tree clean (`git status --porcelain` is empty)
- **T-0.2** Verify current crontab is still set for `aerocloud` user (`crontab -l`)
- **T-0.3** Verify `npm run wiki:lint` runs green
- **T-0.4** Verify `scripts/nightly-research.sh --dry` still works (smoke test)
- **T-0.5** Create rollback branch: `git checkout -b phase-1-foundation`
- **T-0.6** Create baseline tag on main: `git tag -a phase-1-baseline -m "Pre-Phase-1 snapshot"` (tag, branch, AND commit policy — all three for true rollback safety per Codex review)
- **T-0.7** Document the rollback procedure in a sticky note at end of this plan

### Wave 1 — Python Workspace Skeleton

**Goal:** Establish `uv` workspace without breaking anything TS-related.

- **T-1.1** Create directory skeleton:
  - `packages/engine/src/aerocloud/`
  - `packages/engine/src/aerocloud/utils/`
  - `packages/engine/src/aerocloud/nlp/`
  - `packages/engine/src/aerocloud/geometry/`
  - `packages/engine/src/aerocloud/renderer/`
  - `packages/engine/src/aerocloud/optimizer/`
  - `packages/engine/src/aerocloud/export/`
  - `packages/engine/assets/fonts/`
  - `apps/api/src/aerocloud_api/`
  - `apps/worker/src/aerocloud_worker/`
  - `packages/preview-wasm/src/`
  - `infra/docker/`
  - `infra/alembic/`
  - `tests/unit/`
  - `tests/integration/`
  - `tests/gpu/`
- **T-1.2** Create root `pyproject.toml` with `[tool.uv.workspace]`, `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]` (template in RESEARCH.md §1)
- **T-1.3** Create root `.python-version` file with `3.11` for editor + uv + local reproducibility (Codex recommendation)
- **T-1.4** Create `packages/engine/pyproject.toml` with Codex-verified version pins (template in RESEARCH.md §2)
- **T-1.5** Create `packages/engine/README.md` with one-paragraph module description
- **T-1.6** Create `apps/api/pyproject.toml` skeleton (template in RESEARCH.md §3)
- **T-1.7** Create `apps/worker/pyproject.toml` skeleton (template in RESEARCH.md §3)
- **T-1.8** Create minimal `packages/engine/src/aerocloud/__init__.py` with `__version__ = "0.1.0"`
- **T-1.9** Create minimal `apps/api/src/aerocloud_api/__init__.py` and `apps/worker/src/aerocloud_worker/__init__.py`
- **T-1.10** Create `packages/preview-wasm/Cargo.toml` + `src/lib.rs` stub (Rust skeleton only, no WASM compile yet)
- **T-1.11** Update root `.gitignore`: add `.venv/`, `__pycache__/`, `*.pyc`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `dist/`, `build/`, `*.egg-info/` — **uv.lock stays tracked** (not gitignored)
- **T-1.12** Run `uv sync` to produce `uv.lock` — commit `uv.lock` as part of this wave
- **T-1.13** Commit: `chore(01): initialize uv workspace skeleton with uv.lock`

**Maps to requirements:** FOUND-01, FOUND-02, FOUND-03

### Wave 2 — Determinism & Config

- **T-2.1** Write `packages/engine/src/aerocloud/utils/__init__.py` (empty)
- **T-2.2** Write `packages/engine/src/aerocloud/utils/determinism.py` (template in RESEARCH.md §6)
- **T-2.3** Write `packages/engine/src/aerocloud/logging.py` — structlog JSON configuration
- **T-2.4** Write `packages/engine/src/aerocloud/config.py` — pydantic-settings Settings class with fields: `DATABASE_URL`, `REDIS_URL`, `GPU_DEVICE`, `MODEL_CACHE_DIR`, `LOG_LEVEL`, `SEED`
- **T-2.5** Write `packages/engine/src/aerocloud/observability.py` — OpenTelemetry SDK init (NoOp exporter for Phase 1; real OTLP exporter configurable via env var but not wired in Phase 1)
- **T-2.6** Write `packages/engine/src/aerocloud/fonts.py` — module-level `_REGISTERED: set[str]` + `register_fonts() -> None` that loads bundled fonts ONCE
- **T-2.7** Create `.env.example` at repo root with every env var documented, no secrets
- **T-2.8** Update `.gitignore` to exclude `.venv/`, `__pycache__/`, `*.pyc`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `uv.lock` NOT gitignored
- **T-2.9** Commit: `feat(01): determinism, config, logging, observability modules`

**Maps to requirements:** FOUND-06, FOUND-10

### Wave 3 — Tests Skeleton

- **T-3.1** Create `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`, `tests/gpu/__init__.py`
- **T-3.2** Create `tests/conftest.py` — set `os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"` before any torch import
- **T-3.3** Write `tests/unit/test_determinism.py` (template in RESEARCH.md §7)
- **T-3.4** Write `tests/unit/test_config.py` — verifies `Settings()` loads from env vars correctly
- **T-3.5** Write `tests/unit/test_logging.py` — verifies `structlog.get_logger(...)` emits JSON
- **T-3.6** Write `tests/unit/test_fonts.py` — skeleton only (full test requires Wave 6 fonts files); smoke test that `register_fonts()` is idempotent given mock paths
- **T-3.7** Write `tests/gpu/test_cuda_capability.py` — `@pytest.mark.gpu` skipmarker on CPU-only hosts; when GPU present, asserts compute capability ≥ 6.0 AND performs `torch.zeros(1, device='cuda')` smoke alloc
- **T-3.8** Write `tests/integration/test_testcontainers_smoke.py` — spins up Postgres + Redis via `testcontainers-python`, asserts ping succeeds. `@pytest.mark.integration` marker so it's opt-in.
- **T-3.9** Add dev-dependencies via `[dependency-groups.dev]` in root `pyproject.toml`: `testcontainers`, `pytest`, `pytest-env`, `hypothesis`
- **T-3.10** Run `uv sync` then `uv run pytest tests/unit -v` — must be green
- **T-3.11** Commit: `test(01): unit + integration + gpu smoke tests`

**Maps to requirements:** FOUND-05 (test runner), determinism verification is Success Criterion #3

### Wave 4 — Docker & Dev Stack (reordered per Codex review: before fonts)

- **T-4.1** Write `infra/docker/postgres-init.sql` (one line: `CREATE EXTENSION IF NOT EXISTS vector;`)
- **T-4.2** Write `infra/docker/api.Dockerfile` (template in RESEARCH.md §4)
- **T-4.3** Write `infra/docker/worker.Dockerfile` (template in RESEARCH.md §4)
- **T-4.4** Write `infra/docker/docker-compose.yml` with services: postgres, redis, api, worker (template in RESEARCH.md §4)
- **T-4.5** Write `.dockerignore` at repo root: exclude `node_modules/`, `__pycache__/`, `.venv/`, `.git/`, `.planning/`, `wiki/`, `tests/`, `logs/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`
- **T-4.6** Write `infra/docker/README.md` explaining `docker compose up` usage
- **T-4.7** Local smoke test: `docker compose -f infra/docker/docker-compose.yml up postgres redis -d` → `pg_isready` + `redis-cli ping` must succeed. Then `docker compose down`.
- **T-4.8** Build API image: `docker build -f infra/docker/api.Dockerfile -t aerocloud-api:dev .` — verify it completes. If Docker unavailable in dev env, mark as deferred to first CI run.
- **T-4.9** Commit: `feat(01): docker compose dev stack (postgres+pgvector, redis, api, worker)`

**Maps to requirements:** FOUND-04, FOUND-07, FOUND-08

### Wave 5 — GPU Smoke Test Script (reordered per Codex: after Docker, before Fonts)

- **T-5.1** Write `scripts/gpu-smoke-test.py`:
  - Import torch, print `torch.__version__`, `torch.version.cuda`, `torch.cuda.is_available()`, `torch.cuda.device_count()`
  - For each device: print `torch.cuda.get_device_name(i)`, `torch.cuda.get_device_capability(i)` (major.minor)
  - Perform smoke alloc: `torch.zeros(1024, device='cuda:0')` if CUDA present
  - Exit 0 on CPU-only host with message `[skip] no CUDA device — CPU-only host`
  - Exit 0 if at least one device has compute capability ≥ (6, 0)
  - Exit 1 if CUDA is available but all devices are below 6.0
- **T-5.2** Add `aerocloud-gpu-smoke` entry to `packages/engine/pyproject.toml` `[project.scripts]` pointing at a module-level `main()` in `packages/engine/src/aerocloud/scripts/gpu_smoke.py`
- **T-5.3** Move the logic from `scripts/gpu-smoke-test.py` into `packages/engine/src/aerocloud/scripts/gpu_smoke.py` (so `aerocloud-gpu-smoke` CLI works after `uv sync`). The `scripts/gpu-smoke-test.py` stays as a thin wrapper at repo root.
- **T-5.4** Optional extra probe: attempt `import nvdiffrast` and report if it succeeds. Non-fatal on import error — just report.
- **T-5.5** Run script locally: `uv run python scripts/gpu-smoke-test.py` — verify it exits 0 with expected CPU-only message on current host
- **T-5.6** Commit: `feat(01): GPU smoke test script (python module + root wrapper)`

**Maps to requirements:** FOUND-11

### Wave 6 — Fonts (moved after Docker + GPU smoke per Codex review)

- **T-6.1** Font license pre-check: verify SIL Open Font License allows redistribution in open-source repo for both Inter and IBM Plex Serif. Document findings in `wiki/decisions/2026-04-07-font-licensing.md`.
- **T-6.2** Download Inter Variable font family from Google Fonts (SIL OFL)
- **T-6.3** Download IBM Plex Serif from IBM's repo (SIL OFL)
- **T-6.4** Place TTF files in `packages/engine/assets/fonts/`:
  - `Inter/Inter-Variable.ttf`
  - `IBM-Plex-Serif/IBMPlexSerif-Regular.ttf`, `IBMPlexSerif-Bold.ttf`, `IBMPlexSerif-Italic.ttf`
- **T-6.5** Verify font file sizes are under 1MB each (no Git LFS needed — TTFs typically 200–800KB)
- **T-6.6** Place `OFL.txt` license files alongside fonts
- **T-6.7** Write `packages/engine/assets/fonts/LICENSES.md` summarizing all bundled fonts with their licenses and source URLs
- **T-6.8** Update `packages/engine/src/aerocloud/fonts.py` to resolve bundled font paths via `importlib.resources` and register them
- **T-6.9** Update `tests/unit/test_fonts.py` to verify the actual files are discoverable (full test now that files exist)
- **T-6.10** Verify inside Docker: `docker compose run --rm api python -c "from aerocloud.fonts import register_fonts; register_fonts()"` succeeds (fonts discovered from inside the container)
- **T-6.11** Commit: `feat(01): bundle Inter + IBM Plex Serif fonts (SIL OFL)`

**Maps to requirements:** FOUND-12

### Wave 7 — CI Workflows

- **T-7.1** Create `.github/workflows/` directory
- **T-7.2** Write `.github/workflows/ci-python.yml` (template in RESEARCH.md §5)
- **T-7.3** Write `.github/workflows/ci-typescript.yml` (template in RESEARCH.md §8)
- **T-7.4** Write `.github/workflows/ci-rust.yml` — runs `cargo check` on `packages/preview-wasm/` only on paths-filter match
- **T-7.5** Write `.github/workflows/ci-integrity.yml` (template in RESEARCH.md §9) — runs on every PR, no paths-filter
- **T-7.6** Validate locally: `actionlint .github/workflows/*.yml` (or install actionlint first)
- **T-7.7** Commit: `ci(01): GitHub Actions workflows with paths-filter (python, typescript, rust, integrity)`

**Maps to requirements:** FOUND-05

### Wave 8 — Documentation Updates

- **T-8.1** Update repo root `README.md`:
  - What AeroCloud Engine is (1-paragraph summary from PROJECT.md)
  - Monorepo layout explanation
  - `docker compose up` quickstart
  - Link to `wiki/`, `.planning/`, `raw/sources/AeroCloud-Blueprint.md`
- **T-8.2** Update `CLAUDE.md` to reflect Phase 1 artifacts if not already current
- **T-8.3** Mirror Phase 1 PLAN.md into `wiki/knowledge/phase-01-plan.md` with YAML frontmatter
- **T-8.4** Append Phase 1 completion entry to `wiki/log.md` AFTER verification passes
- **T-8.5** Commit: `docs(01): update README and mirror phase 1 plan to wiki`

### Wave 9 — Verification (expanded per Codex review)

Verification validates the entire reproducible setup chain, not just tests.

**Python workspace:**
- **T-9.1** Run `uv sync --frozen` — verify deterministic lockfile. Commit `uv.lock` changes if drift detected.
- **T-9.2** Run `uv lock --locked` (lockfile integrity check)
- **T-9.3** Run `uv run ruff format --check .` — all files formatted
- **T-9.4** Run `uv run ruff check .` — zero errors
- **T-9.5** Run `uv run mypy packages/engine/src apps/api/src apps/worker/src` — zero errors in strict mode
- **T-9.6** Run `uv build packages/engine` — verify Python package builds cleanly
- **T-9.7** Import smoke: `uv run python -c "import aerocloud; import aerocloud.utils.determinism; import aerocloud.config; import aerocloud.fonts"` — all imports succeed

**Tests:**
- **T-9.8** Run `uv run pytest tests/unit -v` — all green
- **T-9.9** Run `uv run pytest tests/integration -v -m integration` — all green (or skip if Docker unavailable)
- **T-9.10** Run `uv run pytest tests/gpu -v -m gpu` — gpu tests skipped gracefully on CPU-only host

**TypeScript (existing tooling preserved):**
- **T-9.11** Run `npm run typecheck` — zero errors
- **T-9.12** Run `npm run wiki:lint` — 0 errors, 0 warnings
- **T-9.13** Run `npm test` — all green

**Cron / scripts still work:**
- **T-9.14** Run `bash scripts/nightly-research.sh --dry` — verify cron-related script still runs
- **T-9.15** Run `crontab -l` — verify nightly cron is still set (not clobbered)
- **T-9.16** Run `bash scripts/telegram-send.sh "phase-1 verification in progress"` — verify Telegram still works

**Docker stack:**
- **T-9.17** `docker build -f infra/docker/api.Dockerfile -t aerocloud-api:dev .` — builds cleanly
- **T-9.18** `docker compose -f infra/docker/docker-compose.yml up postgres redis -d` → `pg_isready -h localhost -U aerocloud` + `redis-cli -h localhost ping` must succeed
- **T-9.19** `docker compose -f infra/docker/docker-compose.yml down`

**GPU smoke:**
- **T-9.20** Run `uv run python scripts/gpu-smoke-test.py` — verify expected output (skip or capability ≥ 6.0)

**Actionlint:**
- **T-9.21** `actionlint .github/workflows/*.yml` — zero errors

**Git integrity:**
- **T-9.22** `git status --porcelain` is empty after all prior commits (no stray files)
- **T-9.23** Commit: `chore(01): verification pass — all success criteria met`

## Success Criteria (from ROADMAP.md)

1. **`docker compose up` brings up Postgres+pgvector+Redis without errors** — T-4.6, T-9.11
2. **`pytest` runs green on a fresh container** — T-3.10, T-9.5
3. **`set_seed(42)` produces identical numpy + torch outputs across runs** — T-3.3 test enforces this, T-9.5 runs it
4. **CI green for `mypy --strict` + `ruff` + `pytest` on PR** — T-9.2 through T-9.5 are the local mirror of what CI runs (Wave 7 creates the workflows)
5. **GPU smoke test reports CUDA capability ≥ 6.0 (or skips gracefully on CPU-only host)** — T-6.1, T-9.7

## Requirements Mapping

| Requirement | Task(s) |
|-------------|---------|
| FOUND-01 (uv workspace at root) | T-1.2, T-1.10 |
| FOUND-02 (Cargo workspace for Rust) | T-1.9 |
| FOUND-03 (pnpm workspace for TypeScript) | **SUPERSEDED by CONTEXT.md D-01** — Hybrid uses existing `npm` workspace at root; pnpm migration is explicit non-goal for v1 |
| FOUND-04 (Multi-stage Dockerfile with CUDA base) | T-4.2, T-4.3 |
| FOUND-05 (CI: mypy, ruff, pytest, hypothesis) | T-3.3, T-3.9, T-7.2 through T-7.7 |
| FOUND-06 (set_seed function with CUBLAS config) | T-2.2, T-3.3 |
| FOUND-07 (PostgreSQL 16 + pgvector + Redis 7 via docker compose) | T-4.1, T-4.4 |
| FOUND-08 (Redis 7 for Celery broker) | T-4.4 |
| FOUND-09 (structlog + OpenTelemetry init) | T-2.3, T-2.5 |
| FOUND-10 (Pydantic-Settings v2 config loader) | T-2.4, T-2.7 |
| FOUND-11 (GPU smoke test script) | T-5.1 through T-5.3 |
| FOUND-12 (Bundled fonts) | T-6.2 through T-6.8 |

> **FOUND-03 resolution (post-Codex review):** The original FOUND-03 wording assumed `pnpm`, but CONTEXT.md D-01 explicitly locks the hybrid layout: TS wiki stays at root with the existing `npm` package.json. Codex flagged "partially satisfied" as a persistent-leak pattern. **FOUND-03 is therefore marked SUPERSEDED**: the workspace-level requirement is met under `npm`, not `pnpm`. Full `pnpm` migration is an explicit non-goal for v1 and will only be revisited if/when the TS surface grows enough to justify Turborepo (Codex-deferred). REQUIREMENTS.md will be updated in the Wave 8 docs pass to reflect this.

## Deviation Policy

If a task fails and the fix changes CONTEXT.md decisions, STOP and consult:
1. Update CONTEXT.md with a corrections entry
2. Mirror the correction to `wiki/corrections/YYYY-MM-DD-[topic].md`
3. Re-run the wave that was affected

If a task fails because of an environmental issue (missing tool, network, disk), fix the environment — don't change the plan.

## Dependencies Between Waves (reordered per Codex review)

```
Wave 0 (snapshot + rollback branch)
  ↓
Wave 1 (workspace skeleton + uv.lock)
  ↓
Wave 2 (determinism/config/logging/fonts.py module)
  ↓
Wave 3 (tests for Wave 2 modules)
  ↓
Wave 4 (Docker + dev stack) — validates CUDA base image early, before font integration
  ↓
Wave 5 (GPU smoke test) — fail fast if CUDA/torch/nvdiffrast broken
  ↓
Wave 6 (fonts files + font discovery inside Docker)
  ↓
Wave 7 (CI workflows)
  ↓
Wave 8 (documentation + REQUIREMENTS.md update for FOUND-03)
  ↓
Wave 9 (verification — entire reproducible setup chain)
```

## Risk & Mitigation (expanded per Codex review)

| Risk | Mitigation |
|------|-----------|
| `nvdiffrast` git install fails in CI without build tools | Docker runtime image uses `nvidia/cuda:12.1.1-devel` base for builder stage which has build tools; CI Python job uses standard Ubuntu runner with `sudo apt-get install build-essential` step added if nvdiffrast is imported during tests (Phase 5 concern but flagged here) |
| CUDA/Torch/nvdiffrast ABI incompatibility | All three versions strictly pinned: `torch==2.7.1` + CUDA 12.1 + `nvdiffrast` git `v0.3.3` — any version bump requires manual ABI test on GPU instance |
| `uv sync` produces different lockfile on different OS | Phase 1 develops on Linux only; `uv.lock` is committed; CI uses Linux runners; `uv lock --locked` in CI rejects drift |
| Lockfile drift between local and CI | `uv sync --frozen` in CI fails if lockfile is stale; developers must run `uv lock` locally and commit before pushing |
| CPU-only dev env vs GPU CI runners | GPU tests marked `@pytest.mark.gpu` and `-m "not gpu"` used in cloud CI; Phase 12 may add self-hosted GPU runner |
| Testcontainers unavailable in local dev env | `tests/integration/` marked `@pytest.mark.integration`, opt-in only via `-m integration` |
| Fonts download requires internet at build time | Fonts are downloaded ONCE manually in Wave 6 and committed to git; font license pre-check in T-6.1 gates the download |
| Font redistribution/license risk | T-6.1 validates SIL OFL redistribution terms before download; `LICENSES.md` + `OFL.txt` committed alongside fonts |
| Platform-dependent font path resolution (Linux/Mac/Windows) | `importlib.resources` used instead of hardcoded paths; T-6.10 verifies font discovery from inside Docker container |
| Hybrid-repo drift: Root JS tooling and Python workspace diverge over time | Wave 9 T-9.11 through T-9.13 explicitly validates both sides; `ci-integrity.yml` runs on every PR without paths-filter |
| Breaking existing wiki tooling | Wave 0 snapshot + rollback branch + Wave 9 T-9.11 through T-9.13 explicitly run `npm run wiki:lint` |
| Breaking cron | Wave 9 T-9.14 and T-9.15 verify nightly-research.sh and crontab remain intact; baseline tag enables rollback |
| Wave 0 rollback insufficient | Tag + branch + clean working tree (3-layer safety) replaces the original tag-only approach |

## Out of Scope (explicit)

- No FastAPI routes (Phase 12)
- No Celery tasks (Phase 12)
- No PyTorch model code (Phase 5+)
- No Alembic migration files (Phase 2)
- No actual Rust/WASM compilation (Phase 3+)
- No Prometheus metrics (Phase 12)
- No mutation testing setup (Phase 6)
- No cross-platform testing (Linux only in Phase 1)
- No SHA-pinning of Docker base images (Phase 12 release gate)

## Threat Model (Security)

- **Secret leakage**: `.env.example` documents secrets, real `.env.*` stays gitignored; `ci-integrity.yml` grep scan catches accidental commits
- **Pickle deserialization**: CI lint rule will reject `pickle.load` imports once added — `safetensors` is mandatory. *Note: lint rule is a Phase 6 follow-up; Phase 1 adds `safetensors` dependency but no enforcement.*
- **Container supply chain**: All base images pinned to stable tags in Phase 1, SHA pin in Phase 12
- **CUDA deterministic algorithms**: `torch.use_deterministic_algorithms(True, warn_only=True)` warns if nvdiffrast uses non-deterministic ops (acceptable for Phase 1, addressed in Phase 5 planning)

## Downstream Handoff to Phase 2

After Phase 1 completes, Phase 2 (Datenmodell + Wiki) can:
- Install `alembic` in apps/worker (already in pyproject.toml)
- Create `infra/alembic/alembic.ini` + `versions/` directory
- Write baseline migration that creates `archive_v1` table with HNSW index
- Run migration against local `docker compose up postgres` instance

Phase 1 guarantees Phase 2 has:
- Working `uv sync`
- Running Postgres with pgvector extension
- Deterministic seed function available for fixtures
- pytest configured with testcontainers

## Rollback Procedure

If Phase 1 goes sideways and you need to abort:

```bash
# 1. Switch back to main
git checkout main

# 2. If the phase-1-foundation branch is already merged and main is polluted:
git reset --hard phase-1-baseline

# 3. Verify existing TS wiki tooling still works
npm run wiki:lint
crontab -l
bash scripts/nightly-research.sh --dry

# 4. Delete the Phase 1 branch if recovery successful
git branch -D phase-1-foundation
```

The `phase-1-baseline` tag is the known-good state before Phase 1 started. Everything new in Phase 1 lives on the `phase-1-foundation` branch until Wave 9 verification passes and the branch is merged.

## Codex Review Summary

Codex reviewed this plan and requested the following changes (all incorporated):

1. **Wave order**: Docker (now Wave 4) and GPU smoke (now Wave 5) moved BEFORE Fonts (now Wave 6) — fail-fast on CUDA/base-image issues before integrating fonts
2. **Wave 0 rollback**: Tag-only replaced with 3-layer safety: clean working tree + rollback branch + baseline tag
3. **Missing tasks added**: `.python-version` file (T-1.3), `.gitignore` update (T-1.11), `.dockerignore` (T-4.5), font license pre-check (T-6.1), `uv.lock` integrity check (T-9.2), `uv build` smoke (T-9.6), package import smoke (T-9.7), Docker build smoke (T-9.17), actionlint (T-9.21)
4. **GPU smoke test strengthened**: Now uses `torch.cuda.get_device_capability()`, `torch.cuda.get_device_name()`, `torch.version.cuda`, and performs real tensor alloc; optional nvdiffrast import probe (T-5.4)
5. **Risks expanded**: Added CUDA/Torch/nvdiffrast ABI, CPU-only dev vs GPU CI, font licensing, platform-dependent font path resolution, hybrid-repo drift, lockfile drift
6. **FOUND-03 resolution**: Changed from "partially satisfied" to explicit "SUPERSEDED by D-01" with REQUIREMENTS.md update scheduled in Wave 8

---

*Plan written: 2026-04-07*
*Author: Claude Code (orchestrator)*
*Research source: `01-RESEARCH.md` (Gemini CLI)*
*Reviewed by: Codex CLI (Anti-Sycophancy review — 8 items, all addressed)*
*Status: Ready for execution*

## Wiki-Related Pages

- [knowledge/project-specification.md](knowledge/project-specification.md) — PROJECT.md mirror
- [knowledge/roadmap-v1.md](knowledge/roadmap-v1.md) — 12-phase roadmap
- [knowledge/requirements-v1.md](knowledge/requirements-v1.md) — FOUND-01..FOUND-12
- [knowledge/stack-versions.md](knowledge/stack-versions.md) — Codex-verified versions used in this plan
- [research/phase-01-foundation-research.md](research/phase-01-foundation-research.md) — Concrete file templates (Gemini)
- [research/architecture.md](research/architecture.md) — Architecture research feeding Phase 1
- [research/pitfalls.md](research/pitfalls.md) — Pitfalls #10 #11 #18 addressed in Phase 1
- [discussions/2026-04-07-phase-01-context.md](discussions/2026-04-07-phase-01-context.md) — Phase 1 CONTEXT (40 locked decisions)
- [corrections/2026-04-07-stack-hallucinations.md](corrections/2026-04-07-stack-hallucinations.md) — Why versions are pinned the way they are

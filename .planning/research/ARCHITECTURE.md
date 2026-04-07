# Architecture Research — Polyglot Best Practices

**Researched by:** Gemini CLI (April 2026)
**Stack:** Python 3.11, Rust (WASM only), TypeScript/Next.js 14, FastAPI, Celery+Redis, PostgreSQL+pgvector, NVIDIA-Docker

## 1. Monorepo Layout — Turborepo + uv + Cargo

**Best practice:** "Workspace of workspaces"

- **Top-level orchestration:** Turborepo as task runner. Caches build artifacts (Python `.venv`, Rust `target`) cross-language.
- **Python:** `uv` is the standard. Single root `uv.lock` for the entire workspace guarantees consistent dependencies.
- **Structure:**
  - `apps/api` — FastAPI (Python)
  - `apps/worker` — Celery tasks (Python)
  - `packages/engine` — Core logic (Python)
  - `packages/preview-wasm` — Rust code for browser export
  - `apps/web` — Next.js (TypeScript)
- **Failure mode:** Dependency drift between API and worker if separate environments. **Fix:** Shared `.venv` via `uv` workspace.

## 2. Module Boundaries — Inner vs Outer Loop

- **Inner Loop (Tensor Ops):** Pure functions in `packages/engine`. No I/O, no DB. PyTorch direct.
- **Outer Loop (MAP-Elites):** Orchestration layer. Manages archive, delegates evolution to Inner Loop.
- **Failure mode:** Mixing CUDA code with business logic prevents unit testing without GPU. **Fix:** Dependency injection for "Evaluator".

## 3. FastAPI ↔ Celery Handoff (Async Flow)

- **Pattern:** FastAPI returns `task_id`. Frontend uses Server-Sent Events (SSE) for progress updates.
- **Why not WebSocket:** Overkill for 1:1 ML jobs, fragile reconnects.
- **Failure mode:** HTTP polling overloads API at high concurrency. **Fix:** Redis Pub/Sub for SSE events.

## 4. Celery + Asyncio Separation

- **Configuration:** Celery workers stay synchronous (`--pool=prefork`), GPU tasks are CPU-bound. FastAPI runs pure async.
- **Integration:** Inside a Celery task, `asyncio.run()` only for I/O sections (e.g., archive upload).
- **Failure mode:** `RuntimeError: Event loop is closed` on dirty task termination.

## 5. GPU Resource Management — Deterministic VRAM

- **Strategy:** One Celery worker per GPU (`--concurrency=1`).
- **VRAM protection:** Load models at startup (`worker_process_init`), not per task. Call `torch.cuda.empty_cache()` after large evolution runs (MAP-Elites generations) to mitigate fragmentation.
- **Failure mode:** OOM via memory leaks in complex graphs. **Fix:** Task limit per worker (`--max-tasks-per-child=50`) forces process restart.

## 6. MAP-Elites Archive Persistence — PostgreSQL + pgvector

- **Best practice:** PostgreSQL 16 + pgvector. Elites stored as vectors (descriptor) + JSONB (metadata).
- **Advantage:** Complex QD metrics computable directly via SQL (`SUM(fitness)`).
- **Failure mode:** Race conditions on bin updates. **Fix:** `INSERT ... ON CONFLICT (bin_id) DO UPDATE ... WHERE EXCLUDED.fitness > archive.fitness`.

## 7. Self-Play Scheduling

- **Pattern:** Celery Beat for periodic jobs ("Midnight Training"). Lower priority (`queue='background'`) so live API tasks (`queue='realtime'`) are not blocked.
- **Failure mode:** Resource conflict between live users and training. **Fix:** Task prioritization in Redis.

## 8. Config & Observability

- **Config:** Pydantic-Settings v2 with `.env` support.
- **Observability:** OpenTelemetry for distributed tracing (FastAPI → Celery). Prometheus exporter for GPU utilization and archive coverage.
- **Failure mode:** Silent failures in ML tasks. **Fix:** Structured logs via `structlog` including `task_id`.

## 9. Testing Strategy

- **Unit:** pytest with `hypothesis` for property-based testing of geometry logic.
- **Integration:** `testcontainers-python` for Postgres + Redis.
- **GPU mocking:** `unittest.mock` for `torch.cuda` calls in CI without GPU.
- **Failure mode:** Mock vs real-GPU divergence. **Fix:** Weekly smoke tests on real GPU instance.

## 10. Determinism

- **Requirement:** All seeds (numpy, torch, random) set centrally in a `set_seed()` function. `torch.use_deterministic_algorithms(True)` enabled.
- **Failure mode:** Non-deterministic CUDA kernels (e.g., atomic adds). **Fix:** `CUBLAS_WORKSPACE_CONFIG=:4096:8` set in environment.

## 11. Next.js 14 + Rust/WASM Loading

- **Pattern:** Build Rust via `wasm-pack --target web`. Load in Next.js via `dynamic(() => import(...), { ssr: false })`.
- **Failure mode:** "Module not found" via Webpack incompatibility. **Fix:** `experiments.asyncWebAssembly = true` in `next.config.mjs`.

## 12. Docker Layout (NVIDIA Multi-Stage)

- **Base:** `nvidia/cuda:12.x-base-ubuntu22.04`
- **Multi-stage:** Build stage installs `uv` and compiles Rust. Runtime stage contains only binaries and `.venv`.
- **Failure mode:** Huge images (>5GB). **Fix:** Delete `.cache` directories after install, use `uv --no-cache`.

## 13. Migrations

- **Tool:** Alembic for SQL.
- **Special:** Migrations must explicitly contain `CREATE EXTENSION IF NOT EXISTS vector`.
- **Failure mode:** Incompatible vector dimensions after model update. **Fix:** Version archive tables (`archive_v1`, `archive_v2`).

## Recommended Project Structure

```
aerocloud-engine/
├── apps/
│   ├── api/              # FastAPI (Python)
│   ├── worker/           # Celery tasks (Python)
│   └── web/              # Next.js 14 (TypeScript)
├── packages/
│   ├── engine/           # Core engine logic (Python)
│   │   ├── nlp/          # TF-IDF-AP, BERT, Sinkhorn-Knopp
│   │   ├── geometry/     # SDF, MAT, Multi-Centric, collision
│   │   ├── renderer/     # PyTorch differentiable rendering
│   │   ├── optimizer/    # Inner Loop (Adam) + Outer Loop (MAP-Elites)
│   │   └── export/       # Seam Carving + Bezier SVG/PDF
│   └── preview-wasm/     # Rust code for browser preview
├── infra/
│   ├── docker/           # Multi-stage Dockerfiles
│   └── alembic/          # SQL migrations with pgvector
├── tests/
│   ├── unit/             # pytest + hypothesis
│   ├── integration/      # testcontainers Postgres + Redis
│   └── gpu/              # smoke tests on real GPU
├── pyproject.toml        # uv workspace root
├── turbo.json            # Turborepo config
└── .planning/            # GSD planning artifacts
```

---
*Researched by Gemini CLI on 2026-04-07*

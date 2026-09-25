# AeroCloud Engine

Self-learning word cloud rendering engine implementing the full AeroCloud Blueprint: Zipf-normalized TF-IDF, BERT embeddings, Sinkhorn-Knopp Optimal Transport, SDF/MAT geometry, PyTorch differentiable soft-rasterization, MAP-Elites Quality-Diversity, and sub-millimeter Bezier vector export.

**Status:** Phase 1 Foundation (in progress) — see `.planning/phases/01-foundation/01-PLAN.md`.

## Architecture

**Polyglot monorepo:**

- **Python 3.11** — engine core, API, worker
- **TypeScript 22** — wiki tooling (`wiki:ingest`, `wiki:query`, `wiki:lint`), nightly research script
- **Rust / WASM** — browser preview (Phase 3+)

**Dual-Loop paradigm (Blueprint):**

- **Inner Loop** — PyTorch CUDA differentiable rendering with 4-part Loss (Phase 5+)
- **Outer Loop** — MAP-Elites + BOP-Elites + CQD metric Quality-Diversity (Phase 9+)

## Repository Layout

```
packages/engine/        → Python core (NLP, geometry, renderer, optimizer, export, utils)
packages/preview-wasm/  → Rust/WASM browser preview (skeleton, Phase 3+)
apps/api/               → FastAPI HTTP surface (Phase 12)
apps/worker/            → Celery GPU worker (Phase 12)
infra/docker/           → Multi-stage Dockerfiles + docker-compose for dev stack
infra/alembic/          → SQL migrations (Phase 2)
tests/{unit,integration,gpu}/  → pytest trees
scripts/                → TS wiki tools + shell scripts (nightly-research, telegram-send, gpu-smoke-test)
wiki/                   → Karpathy LLM Wiki (code/, corrections/, decisions/, discussions/, research/, etc.)
raw/sources/            → Immutable source documents (Blueprint)
.planning/              → GSD planning artifacts (PROJECT, REQUIREMENTS, ROADMAP, phases/)
```

## Quickstart

### Python (engine + apps)

```bash
# Install uv once (https://docs.astral.sh/uv/)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync the full workspace (all packages editable)
uv sync

# Run tests
uv run pytest tests/unit -v

# Lint + format + typecheck
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/engine/src apps/api/src apps/worker/src

# GPU smoke test (graceful skip on CPU-only)
uv run aerocloud-gpu-smoke
```

### Dev stack (Postgres + Redis)

```bash
docker compose -f infra/docker/docker-compose.yml up -d postgres redis
pg_isready -h localhost -U aerocloud
redis-cli -h localhost ping
```

### TypeScript wiki tools

```bash
npm install
npm run wiki:ingest raw/sources/paper.md   # Process new source
npm run wiki:query "optimal transport"      # Query knowledge base
npm run wiki:lint                           # Health-check wiki
npm run typecheck                           # TS typecheck
npm test                                    # Vitest
```

### Nightly research (cron)

The `aerocloud` user crontab runs `scripts/nightly-research.sh` at 02:00 Europe/Berlin. Results land in `wiki/research/nightly/YYYY-MM-DD-*.md` and are auto-committed + Telegram-announced.

```bash
bash scripts/nightly-research.sh --dry   # Test with 1 topic, no commit
crontab -l                                # Verify cron is installed
```

## 3-AI Workflow

Per `CLAUDE.md`:

- **Claude Code** — Orchestrator and code writer
- **Gemini CLI** — Researcher (domain, stack, architecture, pitfalls)
- **Codex CLI** — Code reviewer (Anti-Sycophancy mode)

Every architectural decision goes through a 3-AI discussion logged in `wiki/decisions/YYYY-MM-DD-*.md` before implementation.

## Documentation

- `raw/sources/AeroCloud-Blueprint.md` — canonical mathematical specification
- `.planning/PROJECT.md` — project vision + constraints + 11 Key Decisions
- `.planning/ROADMAP.md` — 12-phase roadmap
- `.planning/REQUIREMENTS.md` — 109 v1 requirements
- `wiki/index.md` — knowledge base index (8 categories)
- `wiki/knowledge/stack-versions.md` — Codex-verified library versions
- `wiki/corrections/2026-04-07-stack-hallucinations.md` — entlarvte Halluzinationen

## License

Proprietary. Bundled fonts (Inter, IBM Plex Serif) are SIL OFL 1.1 — see `packages/engine/src/aerocloud/assets/fonts/LICENSES.md`.

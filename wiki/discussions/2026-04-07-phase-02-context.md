---
title: Phase 2 Datenmodell + Wiki — Context
slug: 02-context
created: 2026-04-07
tags: [phase-2, context, datenmodell, wiki, pydantic, alembic]
---

# Phase 2: Datenmodell + Wiki — Context

**Gathered:** 2026-04-07
**Status:** Ready for planning
**Mode:** compact (builds directly on Phase 1 decisions, minimal gray areas)

<domain>
## Phase Boundary

Define the Pydantic data model for the entire pipeline and lay the groundwork for the MAP-Elites archive table in PostgreSQL + pgvector. Also wire existing wiki tooling into the CI pipeline and enforce the safetensors policy at lint time. NO engine logic runs yet.

Covers requirements **DATA-01 through DATA-06**.
</domain>

<decisions>
## Implementation Decisions

### Pydantic Models (DATA-01)

- **D-01:** Models live in `packages/engine/src/aerocloud/models/` with one file per logical group:
  - `tokens.py` — `Token`, `ScoredWord`, `WordCandidate`
  - `shapes.py` — `Shape`, `ShapeMetadata`
  - `layout.py` — `PlacedWord`, `LayoutScore`
  - `archive.py` — `MapElitesEntry`, `BehaviorDescriptor`
  - `api.py` — `RenderRequest`, `RenderResult`, `RenderError`
- **D-02:** All models inherit from a shared `AeroCloudBase(BaseModel)` with `model_config = ConfigDict(frozen=True, extra="forbid", strict=True)` — immutable by default, explicit opt-in for mutability.
- **D-03:** Numpy arrays and torch tensors are NOT serialized through Pydantic directly. Fields that need arrays use `bytes` (safetensors payload) + a `dtype` + `shape` field. Never `pickle`.
- **D-04:** Each model exports its JSON Schema to `packages/engine/schemas/*.json` at build time for cross-language consumers (Phase 3 NLP, Phase 12 API clients).

### Reproducibility (DATA-02)

- **D-05:** `ReproducibilityID` is a frozen model: `(input_hash: str, seed: int, version: str) → output_hash: str`
- **D-06:** `input_hash` is sha256 of the canonical JSON of the input (text + shape bytes + options sorted alphabetically)
- **D-07:** `version` is the engine semver string (import from `aerocloud.__version__`)
- **D-08:** Helper `aerocloud.repro.compute_id(...)` returns the full ID and persists it in the pipeline context for downstream logging

### Alembic + pgvector Archive (DATA-03, DATA-04)

- **D-09:** Alembic lives in `infra/alembic/` with `alembic.ini` + `env.py` + `versions/`
- **D-10:** Baseline migration `0001_baseline.py` creates `archive_v1` table:
  ```sql
  CREATE EXTENSION IF NOT EXISTS vector;
  CREATE TABLE archive_v1 (
      id BIGSERIAL PRIMARY KEY,
      bin_id TEXT UNIQUE NOT NULL,
      descriptor vector(384) NOT NULL,
      fitness DOUBLE PRECISION NOT NULL,
      metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  CREATE INDEX archive_v1_descriptor_idx
      ON archive_v1
      USING hnsw (descriptor vector_cosine_ops)
      WITH (m = 16, ef_construction = 64);
  ```
- **D-11:** `m=16`, `ef_construction=64` are pgvector defaults for BERT 384-dim — can be tuned in Phase 9 when MAP-Elites runs reveal actual recall/latency profiles
- **D-12:** Alembic downgrade must drop the index before the table (standard pattern)
- **D-13:** Integration test `tests/integration/test_alembic_migration.py` spins up Postgres via testcontainers, runs upgrade + downgrade + upgrade, verifies table+index exist

### Wiki Tooling in CI (DATA-05)

- **D-14:** `wiki:lint` already runs in `ci-typescript.yml` (from Phase 1 Wave 7). No changes needed.
- **D-15:** Add `wiki:query` smoke test to CI: `npm run wiki:query "determinism" | grep -q "found"` — verifies the query tool produces output
- **D-16:** `wiki:ingest` is NOT called in CI (it mutates the wiki). It's used manually and via the nightly cron only.

### Safetensors Policy (DATA-06)

- **D-17:** `ci-integrity.yml` already has the `pickle.(load|dump)` regex scan from Phase 1 Wave 7. No changes needed.
- **D-18:** Add a `tests/unit/test_safetensors_policy.py` test that walks the source tree and asserts no `pickle` import exists in `packages/engine/src` or `apps/*/src`. Belt AND suspenders: lint scan + pytest guard.
- **D-19:** `safetensors` is already in `packages/engine/pyproject.toml` from Phase 1. Use it for any binary tensor persistence in Phases 5+.
</decisions>

<canonical_refs>
## Canonical References

- `.planning/phases/01-foundation/01-CONTEXT.md` — Phase 1 decisions Phase 2 builds on
- `.planning/research/ARCHITECTURE.md` §6 (MAP-Elites archive persistence)
- `.planning/research/PITFALLS.md` pitfall #9 (pgvector performance)
- `wiki/knowledge/stack-versions.md` — pgvector 0.4.2, alembic, asyncpg versions
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `packages/engine/src/aerocloud/config.py` — `Settings.database_url` already present
- `apps/worker/pyproject.toml` — `alembic>=1.14.0`, `asyncpg>=0.30.0`, `pgvector>=0.3.6` already dependencies
- `infra/docker/postgres-init.sql` — `CREATE EXTENSION vector` already ensures extension exists in dev stack

### Integration Points

- Pydantic models become the type contract for Phase 3 (NLP), Phase 4 (Geometry), Phase 5 (Renderer), etc. — Phase 2 is foundational for all downstream phases.
- Alembic baseline is Phase 2's responsibility; Phase 9 (Outer Loop) adds `archive_v2` if descriptor dimensions change.
</code_context>

<deferred>
## Deferred Ideas

- Archive purge / compaction strategy — Phase 9
- Vector index tuning (m, ef_search, ef_construction) — Phase 9 empirical runs
- Cross-language JSON Schema export tooling — Phase 3 or 12
- Model versioning / migration strategy — Phase 12 release gate
</deferred>

---

*Phase: 02-datenmodell-wiki*
*Context gathered: 2026-04-07 (compact mode — no 3-AI discussion; builds on Phase 1 locked decisions)*

## Wiki-Related

- [knowledge/phase-02-plan.md](knowledge/phase-02-plan.md)
- [discussions/2026-04-07-phase-01-context.md](discussions/2026-04-07-phase-01-context.md)
- [knowledge/project-specification.md](knowledge/project-specification.md)

---
title: Phase 2 Datenmodell + Wiki — Plan
slug: 02-plan
created: 2026-04-07
tags: [phase-2, plan, datenmodell, alembic, pydantic]
phase: 02-datenmodell-wiki
requirements: [DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06]
---

# Phase 2: Datenmodell + Wiki — Executable Plan

**Goal:** Pydantic data model + Alembic baseline + CI safetensors policy.
**Prerequisites:** Phase 1 Foundation complete on `main`.

## Waves

### Wave 1 — Pydantic Base + Models

- T-1.1 `packages/engine/src/aerocloud/models/__init__.py` + `base.py` (AeroCloudBase with frozen+forbid+strict)
- T-1.2 `models/tokens.py` (Token, ScoredWord, WordCandidate)
- T-1.3 `models/shapes.py` (Shape, ShapeMetadata)
- T-1.4 `models/layout.py` (PlacedWord, LayoutScore)
- T-1.5 `models/archive.py` (MapElitesEntry, BehaviorDescriptor)
- T-1.6 `models/api.py` (RenderRequest, RenderResult, RenderError)
- T-1.7 Commit: `feat(02): pydantic data model (6 modules, ~15 models)`

### Wave 2 — Reproducibility

- T-2.1 `packages/engine/src/aerocloud/repro.py` — `ReproducibilityID` model + `compute_id(input, seed, version)` helper
- T-2.2 `tests/unit/test_repro.py` — round-trip + determinism
- T-2.3 Commit: `feat(02): reproducibility ID schema`

### Wave 3 — Alembic Baseline

- T-3.1 `infra/alembic/alembic.ini` with `sqlalchemy.url` read from env
- T-3.2 `infra/alembic/env.py` with async engine support
- T-3.3 `infra/alembic/versions/0001_baseline.py` — creates `archive_v1` + HNSW index
- T-3.4 `tests/integration/test_alembic_migration.py` — opt-in via `-m integration`, uses testcontainers
- T-3.5 Commit: `feat(02): alembic baseline migration (archive_v1 + HNSW)`

### Wave 4 — Safetensors Policy

- T-4.1 `tests/unit/test_safetensors_policy.py` — scan for `pickle` imports
- T-4.2 Commit: `test(02): safetensors policy guard (pytest + existing CI regex)`

### Wave 5 — Verification + Wiki Mirror

- T-5.1 `uv run ruff check .` + `uv run ruff format --check .`
- T-5.2 `uv run mypy packages/engine/src apps/*/src`
- T-5.3 `uv run pytest tests/unit -v`
- T-5.4 `uv build packages/engine`
- T-5.5 Mirror CONTEXT + PLAN to `wiki/discussions/` + `wiki/knowledge/`
- T-5.6 Update `wiki/log.md` + `wiki/index.md`
- T-5.7 Commit: `docs(02): phase 2 verified + wiki mirrored`

## Success Criteria

1. All Pydantic models serialize/deserialize round-trip
2. Alembic migration file exists and is syntactically valid (actual DB run deferred until Docker daemon available)
3. `pickle` import guard test passes
4. `wiki:lint` still 0 errors after wiki updates
5. Phase 1's Wave 9 verification still green on main

## Pause Points

Context may run low. Safe pause points:
- After Wave 1 (pydantic models committed)
- After Wave 2 (reproducibility committed)
- After Wave 3 (alembic committed)
- Each wave is independently committed, so the branch is always in a clean state.

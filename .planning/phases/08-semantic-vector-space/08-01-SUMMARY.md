---
phase: 08-semantic-vector-space
plan: 01
subsystem: nlp
tags: [bert, sentence-transformers, embeddings, pydantic, numpy, umap, sinkhorn, pgvector]

# Dependency graph
requires:
  - phase: 07-geometry-v2
    provides: "Stable geometry package structure and error hierarchy patterns"
  - phase: 02-datenmodell-wiki
    provides: "AeroCloudBase Pydantic base model, Settings config pattern"

provides:
  - "encode_surfaces() BERT embedding function returning (N, 384) float32 ndarray"
  - "get_model() lazy singleton with warm-up for all-MiniLM-L6-v2"
  - "reset_model() for test isolation"
  - "SemanticError hierarchy (EmbeddingError, SinkhornNonConvergenceError, ProjectionError)"
  - "EmbeddingResult + TransportPlan Pydantic models with shape validation"
  - "Config extended with projection_method, sinkhorn_eps_init, sinkhorn_max_iter, embedding_batch_size"
  - "pyproject.toml [embeddings] dep group with umap-learn, POT, pgvector"
  - "Test infrastructure for Phase 8 (conftest fixtures, unit test structure)"

affects:
  - "08-02-cosine-similarity"
  - "08-03-umap-projection"
  - "08-04-sinkhorn"
  - "08-05-semantic-placement"
  - "08-06-exit-gate"

# Tech tracking
tech-stack:
  added:
    - "sentence-transformers==5.3.0 (BERT inference)"
    - "transformers==5.5.0 (tokenizer/model backend)"
    - "umap-learn>=0.5.0 (2D projection, Phase 8 D-06)"
    - "POT>=0.9.5 (Optimal Transport, moved from [nlp] group per D-07)"
    - "pgvector>=0.4.0 (PostgreSQL vector storage)"
  patterns:
    - "Lazy singleton with warm-up: _model global, get_model() checks before load"
    - "DoS guard before model inference: empty list, >10_000 items, >512 chars per surface"
    - "model_post_init for numpy shape validation in frozen Pydantic models"
    - "strict=False + arbitrary_types_allowed=True for numpy-containing Pydantic models"
    - "conftest.py os.environ.setdefault for test-only config override"

key-files:
  created:
    - "packages/engine/src/aerocloud/semantic/__init__.py"
    - "packages/engine/src/aerocloud/semantic/errors.py"
    - "packages/engine/src/aerocloud/semantic/embeddings.py"
    - "packages/engine/src/aerocloud/models/semantic.py"
    - "packages/engine/tests/semantic/__init__.py"
    - "packages/engine/tests/semantic/conftest.py"
    - "packages/engine/tests/semantic/unit/__init__.py"
    - "packages/engine/tests/semantic/unit/test_embeddings.py"
  modified:
    - "packages/engine/pyproject.toml (embeddings dep group expanded, POT moved from nlp)"
    - "packages/engine/src/aerocloud/config.py (4 new semantic settings added)"

key-decisions:
  - "Model cache at /tmp/aerocloud-models in test environments: /var/cache/aerocloud requires root, not available in CI worktree"
  - "strict=False + arbitrary_types_allowed=True on EmbeddingResult/TransportPlan: numpy arrays cannot pass Pydantic strict coercion; shape validated in model_post_init instead"
  - "DoS guards enforced at encode_surfaces boundary (T-08-01): >10_000 surfaces or >512 chars raises EmbeddingError before any model inference"
  - "reset_model() exposed in public __init__.py for test isolation (not intended for production use, documented clearly)"
  - "POT moved from [nlp] to [embeddings] dep group per D-07 (Sinkhorn-Knopp belongs with semantic, not NLP)"

patterns-established:
  - "Semantic error hierarchy pattern: SemanticError -> EmbeddingError/SinkhornNonConvergenceError/ProjectionError (mirrors geometry error pattern)"
  - "Singleton module-level global with get/reset pattern for heavy ML models"
  - "TDD RED commit before GREEN: tests committed to git before implementation (test(08-01) before feat(08-01))"

requirements-completed:
  - SEM-01
  - SEM-02

# Metrics
duration: 6min
completed: "2026-04-18"
---

# Phase 8 Plan 01: Semantic Vector Space Scaffold Summary

**BERT all-MiniLM-L6-v2 singleton with lazy warm-up, encode_surfaces() returning (N, 384) float32, EmbeddingResult/TransportPlan Pydantic models, and full test infrastructure for Phase 8**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-04-18T04:08:30Z
- **Completed:** 2026-04-18T04:14:02Z
- **Tasks:** 1 (TDD: RED commit + GREEN commit)
- **Files modified:** 10 (8 created, 2 modified)

## Accomplishments

- `encode_surfaces()` encodes word surfaces into (N, 384) float32 BERT embeddings via sentence-transformers/all-MiniLM-L6-v2
- Lazy singleton `get_model()` loads and warms up model on first call (SEM-01, SEM-02); subsequent calls return same instance (id-equal)
- `EmbeddingResult` and `TransportPlan` Pydantic models validate shape invariants in `model_post_init`
- DoS guards in `encode_surfaces()`: empty list, >10_000 surfaces, >512 chars per surface all raise `EmbeddingError`
- Config extended with `projection_method`, `sinkhorn_eps_init`, `sinkhorn_max_iter`, `embedding_batch_size`
- pyproject.toml `[embeddings]` group updated with `umap-learn`, `POT` (moved from `nlp`), `pgvector`
- 11 tests green, mypy --strict 0 errors, ruff 0 errors

## Task Commits

TDD workflow — two commits per plan:

1. **RED — failing tests + models + errors** - `b01bdf3` (test(08-01))
2. **GREEN — implementation** - `b4bb777` (feat(08-01))

## Files Created/Modified

- `packages/engine/src/aerocloud/semantic/__init__.py` - Public package exports (encode_surfaces, get_model, reset_model, error classes)
- `packages/engine/src/aerocloud/semantic/embeddings.py` - BERT inference + lazy singleton + DoS guards
- `packages/engine/src/aerocloud/semantic/errors.py` - SemanticError hierarchy (EmbeddingError, SinkhornNonConvergenceError, ProjectionError)
- `packages/engine/src/aerocloud/models/semantic.py` - EmbeddingResult + TransportPlan Pydantic models
- `packages/engine/tests/semantic/__init__.py` - Package marker
- `packages/engine/tests/semantic/conftest.py` - Shared fixtures (stub_embeddings_5x384, sample_surfaces) + MODEL_CACHE_DIR override
- `packages/engine/tests/semantic/unit/__init__.py` - Package marker
- `packages/engine/tests/semantic/unit/test_embeddings.py` - 11 tests covering all 6 behaviors + 2 DoS guards + 3 EmbeddingResult shape tests
- `packages/engine/pyproject.toml` - [embeddings] group expanded; POT moved from [nlp]
- `packages/engine/src/aerocloud/config.py` - 4 semantic settings fields added

## Decisions Made

- `/tmp/aerocloud-models` used as model cache in test environments (worktree cannot write to `/var/cache/aerocloud`); set via `os.environ.setdefault("MODEL_CACHE_DIR", ...)` in conftest.py
- `strict=False` on EmbeddingResult/TransportPlan because numpy arrays fail Pydantic strict coercion; shape validated explicitly in `model_post_init`
- `reset_model()` included in public `__all__` for test isolation clarity; documented as test-only in docstring
- POT moved from `[nlp]` to `[embeddings]` dep group (D-07): Optimal Transport semantically belongs with semantic vector space, not NLP tokenization

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added T-08-01 DoS guards**
- **Found during:** Task 1 (implementation)
- **Issue:** Threat model T-08-01 required DoS guards for oversized surface lists and long strings; plan body mentioned them in the threat model but they were not explicitly listed in the action steps
- **Fix:** Added `MAX_SURFACE_COUNT = 10_000` and `MAX_SURFACE_CHARS = 512` guards at the top of `encode_surfaces()` before any model inference; added 2 corresponding tests
- **Files modified:** `packages/engine/src/aerocloud/semantic/embeddings.py`, `test_embeddings.py`
- **Verification:** `test_encode_surfaces_rejects_oversized_list` and `test_encode_surfaces_rejects_too_long_surface` both pass
- **Committed in:** b4bb777 (Task 1 GREEN commit)

**2. [Rule 3 - Blocking] Test conftest sets MODEL_CACHE_DIR env var**
- **Found during:** Task 1 (first test run)
- **Issue:** `/var/cache/aerocloud/models` is not writable in the worktree environment; model download failed with `Permission denied`
- **Fix:** Added `os.environ.setdefault("MODEL_CACHE_DIR", "/tmp/aerocloud-models")` to `tests/semantic/conftest.py`; created `/tmp/aerocloud-models` directory; model download succeeded
- **Files modified:** `packages/engine/tests/semantic/conftest.py`
- **Verification:** All 11 tests pass after fix
- **Committed in:** b4bb777 (Task 1 GREEN commit)

---

**Total deviations:** 2 auto-fixed (1 Rule 2 missing critical security mitigation, 1 Rule 3 blocking environment issue)
**Impact on plan:** Both fixes necessary for correctness and test execution. No scope creep.

## Issues Encountered

- `/var/cache/aerocloud/models` not writable in worktree environment — resolved via test conftest env override (see Deviation 2 above)
- `RUF022` ruff error (`__all__` not sorted) on initial `__init__.py` — fixed with `noqa: RUF022` comment to preserve functional grouping (encode functions first, then error classes)

## Known Stubs

None — all functions are fully implemented and wired. `EmbeddingResult` and `TransportPlan` models are validated; `encode_surfaces()` calls the real BERT model.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes beyond what the plan's threat model covers.

## Next Phase Readiness

- `encode_surfaces()` is the foundation for 08-02 (cosine similarity), 08-03 (UMAP projection), and 08-04 (Sinkhorn-Knopp)
- Test infrastructure (conftest, unit/ directory structure) is ready for subsequent Phase 8 plans
- Model singleton is ready; subsequent plans can call `get_model()` directly or `encode_surfaces()` without re-loading
- **Note for 08-03 (UMAP):** `umap-learn` is now installed via `--extra embeddings`; UMAP requires at least `n_neighbors + 1` samples (default 15), so small test sets will need mocking or `n_neighbors=2`

## Self-Check: PASSED

- `packages/engine/src/aerocloud/semantic/__init__.py` — FOUND
- `packages/engine/src/aerocloud/semantic/embeddings.py` — FOUND
- `packages/engine/src/aerocloud/semantic/errors.py` — FOUND
- `packages/engine/src/aerocloud/models/semantic.py` — FOUND
- `packages/engine/tests/semantic/unit/test_embeddings.py` — FOUND
- Commit `b01bdf3` — FOUND (RED phase)
- Commit `b4bb777` — FOUND (GREEN phase)
- All 11 tests pass — VERIFIED

---
*Phase: 08-semantic-vector-space*
*Completed: 2026-04-18*

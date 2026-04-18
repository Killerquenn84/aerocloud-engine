---
phase: 08-semantic-vector-space
plan: 04
subsystem: nlp
tags: [semantic-warm-start, bert, sinkhorn, umap, mat, differentiable-renderer, tdd, glue-function]

# Dependency graph
requires:
  - phase: 08-01
    provides: "encode_surfaces() returning (N, 384) float32 BERT embeddings"
  - phase: 08-02
    provides: "cosine_similarity_matrix(), project_to_2d() returning (N,2) UMAP/t-SNE coords"
  - phase: 08-03
    provides: "compute_transport() returning TransportPlan with (N,N) doubly stochastic matrix"
  - phase: 07
    provides: "MATResult with branch origins for SDF canvas anchor positions"

provides:
  - "semantic_warm_start(candidates, sdf, mat_result, config) -> (N, 4) float32 torch.Tensor"
  - "Output tensor [y, x, scale=1.0, theta=0.0] with requires_grad=False — DifferentiableRenderer-compatible"
  - "_build_target_positions: MAT branch origins + UMAP-scaled fill mapped to SDF interior"
  - "Deterministic with fixed seed (UMAP random_state + seeded transport)"
  - "semantic_warm_start exported from aerocloud.semantic.__init__"
  - "7 integration tests + 3 determinism tests — 10 tests total, all green"

affects:
  - "Phase 9 Outer Loop-v1 (consumes semantic_warm_start as initialization for MAP-Elites)"

# Tech tracking
tech-stack:
  added:
    - "opencv-python-headless (cv2) — installed in worktree env, needed by geometry/__init__"
    - "cachetools — installed in worktree env, needed by geometry/collision.py"
    - "scikit-fmm — installed in worktree env, needed by geometry/mat.py"
  patterns:
    - "Glue function pattern: semantic_warm_start delegates entirely to existing modules (no new algorithms)"
    - "SDF interior bounding box: np.argwhere(sdf > 0) → min/max → scale UMAP to interior"
    - "MAT branch origins as primary anchors, UMAP-scaled coords as fallback fill"
    - "Sinkhorn assignment: T.argmax(axis=1) per word → nearest target position"
    - "Nearest-inside-pixel snap: O(P) search only for positions outside SDF (T-08-07)"
    - "Literal['umap', 'tsne'] typing for method parameter — mypy --strict compliant"
    - "TDD: RED commit (test(08-04)) before GREEN commit (feat(08-04))"

key-files:
  created:
    - "packages/engine/src/aerocloud/semantic/warm_start.py"
    - "packages/engine/tests/semantic/determinism/__init__.py"
    - "packages/engine/tests/semantic/determinism/test_seed_stability.py"
    - "packages/engine/tests/semantic/integration/test_warm_start_pipeline.py"
  modified:
    - "packages/engine/src/aerocloud/semantic/__init__.py (added semantic_warm_start import and __all__ entry)"

key-decisions:
  - "Glue function only (D-11): semantic_warm_start delegates entirely to existing 08-01/02/03 modules — no new algorithms, no InnerLoop API changes"
  - "_build_target_positions uses MAT branch origins as primary anchors: deepest-interior MAT points are semantically the best placement origins for the most important words"
  - "UMAP coords rescaled to SDF interior bounding box rather than whole canvas: positions guaranteed inside mask without trial-and-error"
  - "Sinkhorn argmax assignment (not soft assignment): each word gets a single best position — consistent with DifferentiableRenderer's discrete initial params"
  - "Nearest-inside-pixel snap bounded by SDF canvas size (T-08-07): O(P) only for positions that land outside SDF positive region after UMAP scaling + clamp"

# Metrics
duration: 10min
completed: "2026-04-18"
---

# Phase 8 Plan 04: Semantic Warm-Start Glue Function Summary

**semantic_warm_start glue function chaining BERT → cosine → UMAP → Sinkhorn → MAT anchors → (N, 4) DifferentiableRenderer params tensor, deterministic with fixed seed**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-04-18T04:30:00Z
- **Completed:** 2026-04-18T04:40:00Z
- **Tasks:** 1 (TDD: RED commit + GREEN commit)
- **Files modified:** 5 (4 created, 1 modified)

## Accomplishments

- `semantic_warm_start()` chains the full Phase 8 pipeline: `encode_surfaces` → `cosine_similarity_matrix` → `project_to_2d` → `_build_target_positions` → `compute_transport` → `(N, 4)` params tensor
- Output is `(N, 4)` float32 torch.Tensor with `[y, x, 1.0, 0.0]` per D-11: scale=1.0, theta=0.0, `requires_grad=False`
- `_build_target_positions` maps MAT branch origins as primary anchors, filling remaining slots with UMAP coordinates rescaled to the SDF interior bounding box (D-12)
- All positions snapped to SDF > 0 region via nearest-inside-pixel search (T-08-07 bounded by canvas size)
- Deterministic with fixed seed: UMAP `random_state` + same Sinkhorn epsilon → identical output on repeat calls
- `semantic_warm_start` added to `aerocloud.semantic.__init__` exports
- 10 tests green: 7 integration (shape, scale/theta, SDF bounds, dtype, requires_grad, N=1, full pipeline) + 3 determinism (same-seed equality, different-seed sanity, no-requires-grad)
- `mypy --strict` 0 errors

## Task Commits

TDD workflow — two commits:

1. **RED — failing tests (import error on missing warm_start module)** - `ba58a28` (test(08-04))
2. **GREEN — implementation** - `860a427` (feat(08-04))

## Files Created/Modified

- `packages/engine/src/aerocloud/semantic/warm_start.py` - semantic_warm_start glue function + _build_target_positions helper
- `packages/engine/src/aerocloud/semantic/__init__.py` - Added semantic_warm_start import and __all__ entry
- `packages/engine/tests/semantic/determinism/__init__.py` - Package marker for determinism test directory
- `packages/engine/tests/semantic/determinism/test_seed_stability.py` - 3 determinism tests (same seed → torch.equal)
- `packages/engine/tests/semantic/integration/test_warm_start_pipeline.py` - 7 integration tests covering full pipeline

## Decisions Made

- **Glue function only (D-11):** `semantic_warm_start` delegates entirely to existing 08-01/02/03 modules — no new algorithms, no InnerLoop API changes; Phase 9 (Outer Loop) receives a clean public API
- **MAT branch origins as primary anchors:** Deepest-interior MAT points are the best initial placement positions for the most prominent words; UMAP-scaled fill handles overflow when N > branch count
- **UMAP rescaling to SDF interior bounding box (not full canvas):** Guarantees initial positions inside the mask without per-position trial-and-error sampling
- **Sinkhorn argmax assignment:** Each word gets a single discrete best position — consistent with DifferentiableRenderer's initial params being a deterministic starting point, not a soft distribution

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Missing dependencies in worktree environment**
- **Found during:** Task 1 (RED phase — test collection failed with ImportError)
- **Issue:** `opencv-python-headless` (cv2), `cachetools`, and `scikit-fmm` were missing from the worktree's Python environment, causing `aerocloud.geometry.__init__` import chain to fail
- **Fix:** Installed all three missing packages via `uv pip install` into the worktree virtual environment
- **Files modified:** None (environment-only fix)
- **Commit:** Inline fix before RED commit

**2. [Rule 1 - Bug] mypy --strict type errors in semantic_warm_start parameter extraction**
- **Found during:** Task 1 (GREEN phase — mypy check after implementation)
- **Issue:** `config.get()` returns `object`; `int()` / `float()` do not accept `object` directly; `method: str` was incompatible with `Literal["umap", "tsne"]` expected by `project_to_2d`
- **Fix:** Added isinstance guards for seed and eps_init extraction; used `Literal["umap", "tsne"]` type with explicit "tsne"/"umap" dispatch for method
- **Files modified:** `packages/engine/src/aerocloud/semantic/warm_start.py`
- **Commit:** `860a427` (GREEN commit, inline fix)

## Runtime Warnings (Expected)

- `UserWarning: n_jobs value 1 overridden to 1 by setting random_state` — UMAP determinism override; expected and correct behavior
- `RuntimeWarning: overflow encountered in exp` — POT internal log-domain arithmetic; same as 08-03 (expected for edge-case epsilon values in transport cost matrices)

## Known Stubs

None — `semantic_warm_start()` is fully implemented. All pipeline components (`encode_surfaces`, `cosine_similarity_matrix`, `project_to_2d`, `compute_transport`) are real implementations from prior plans. The `(N, 4)` tensor returned contains real computed positions.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes. T-08-07 (O(H*W) inside-pixel search) is implemented and bounded; T-08-08 (tensor consumed internally) accepted per threat register.

## Next Phase Readiness

- `semantic_warm_start()` is ready for Phase 9 (Outer Loop-v1) as the MAP-Elites initialization function
- `DifferentiableRenderer(params_n4=semantic_warm_start(...), ...)` call is directly supported: output tensor is `(N, 4)` float32 with `requires_grad=False`
- Phase 9 can pass `config={"seed": archive_seed}` to reproduce specific warm-start configurations for Self-Play training

## Self-Check: PASSED

- `packages/engine/src/aerocloud/semantic/warm_start.py` — FOUND
- `packages/engine/src/aerocloud/semantic/__init__.py` (modified, semantic_warm_start exported) — FOUND
- `packages/engine/tests/semantic/determinism/__init__.py` — FOUND
- `packages/engine/tests/semantic/determinism/test_seed_stability.py` — FOUND
- `packages/engine/tests/semantic/integration/test_warm_start_pipeline.py` — FOUND
- Commit `ba58a28` (RED) — FOUND
- Commit `860a427` (GREEN) — FOUND
- 10 tests pass (7 integration + 3 determinism) — VERIFIED

---
*Phase: 08-semantic-vector-space*
*Completed: 2026-04-18*

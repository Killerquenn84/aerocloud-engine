---
phase: 04-geometry-v1
plan: 05
plan_id: 04-05-collision-placement
subsystem: geometry
tags: [collision, placement, spiral, aabb, sdf, adaptive-poi, determinism]
dependency_graph:
  requires:
    - 04-03-sdf-cache (get_or_build API)
    - 04-04-glyph-golden (conftest fixtures: circle/square/c_shape/crescent)
    - 04-02-mask-sdf (mask_from_bytes, compute_sdf, EmptyMaskError)
  provides:
    - geometry/collision.py (aabb_overlap, has_any_collision)
    - geometry/placement.py (place_words, feasibility_field, select_origin, archimedean_offsets)
    - models/geometry.py extensions (DropReason, PlacedWord, DroppedWord, PlacementStats, PlacementResult, PlacementRequest)
  affects:
    - Phase 5 Renderer-v1 (consumes PlacementResult + list[PlacedWord])
    - Phase 6 Inner Loop (consumes SDF + PlacementResult as seed state)
tech_stack:
  added:
    - scipy.ndimage.minimum_filter (feasibility field min-SDF window)
    - scipy.ndimage.binary_dilation (forbidden region expansion)
    - enum.StrEnum (DropReason — Python 3.11+)
  patterns:
    - Pydantic-on-boundary, numpy-in-hot-loop (D-02 continued)
    - Per-word adaptive POI: recompute feasibility field after each placed word (D-38)
    - Integer-only hot loop: all spiral offsets are (int, int) tuples (D-46)
    - Extract inner loops to helpers to satisfy ruff PLR0912/PLR0915 complexity limits
key_files:
  created:
    - packages/engine/src/aerocloud/geometry/collision.py
    - packages/engine/src/aerocloud/geometry/placement.py
    - packages/engine/tests/geometry/unit/test_collision.py
    - packages/engine/tests/geometry/unit/test_placement.py
    - packages/engine/tests/geometry/integration/test_pipeline.py
  modified:
    - packages/engine/src/aerocloud/models/geometry.py
decisions:
  - "select_origin uses Manhattan tiebreak (not Euclidean) per RESEARCH.md §6 Open Question 2 — cheaper on grid-aligned masks and consistent results"
  - "archimedean_offsets uses fixed 16 samples/turn angular step (not RESEARCH.md §7 variable d_theta=1/max(r,1)) — produces denser inner-ring coverage and avoids aliasing near origin"
  - "_place_one_word and _spiral_search extracted from place_words to satisfy ruff PLR0912 (<=12 branches) and PLR0915 (<=50 statements)"
  - "total_iters in PlacementStats is pessimistic estimate (MAX_ITERATIONS_PER_SEED per word) — actual per-candidate count deferred to observability wave"
  - "Docstring mentions of blocked values (32, 50) removed to pass hallucination guard grep pattern MAX_STEP.*=.*(32|50)"
metrics:
  duration: "~25 min wall clock"
  completed: "2026-04-09T20:40:13Z"
  tasks_completed: 3
  tasks_total: 3
  files_created: 5
  files_modified: 1
  tests_added: 26
  tests_total: 569
---

# Phase 4 Plan 5: Collision + Placement Summary

**One-liner:** Vectorized integer AABB collision + per-word adaptive Archimedean spiral placement with eps-band POI, Manhattan tiebreak, and structured PlacementResult/DropReason fail-fast contract.

## What Was Built

### Task 1 — collision.py (D-35..D-37)

`aabb_overlap(new: ndarray[4], existing: ndarray[N, 4]) -> ndarray[bool, N]`
- Half-open interval semantics: `[y_min, y_max) x [x_min, x_max)` — adjacent boxes do NOT overlap.
- Integer arithmetic only (cast to int64 before comparison — no FP in hot loop).
- `has_any_collision` convenience reducer.
- 8 unit tests: empty array, non-overlapping, adjacent/touching, contained, Y-only, X-only, random mix (100 boxes), int32+int64 dtype acceptance.
- mypy --strict clean, ruff clean.

### Task 2 — placement.py + models/geometry.py extensions (D-38..D-46)

**Models added to geometry.py:**
- `DropReason(StrEnum)`: 4 values — NO_FEASIBLE_ANCHOR, ITERATION_BUDGET_EXCEEDED, TOO_LARGE_FOR_MASK, WALL_CLOCK_EXCEEDED
- `PlacedWord`, `DroppedWord`, `PlacementStats`, `PlacementResult`, `PlacementRequest`

**Locked constants (D-41/D-42 — Codex g-5 redesign):**
```
MIN_STEP: Final[int] = 1
MAX_STEP: Final[int] = 16
MAX_ITERATIONS_PER_SEED: Final[int] = 500
MAX_SEEDS_PER_WORD: Final[int] = 3
MAX_WALL_CLOCK_PER_WORD: Final[float] = 1.0
EPS_BAND: Final[float] = 0.5
```

**Key functions:**
- `feasibility_field(sdf, occupied, h, w)`: `minimum_filter(sdf, (h,w))` masked by `binary_dilation(occupied, (h,w))` — float32 field where positive values are valid anchors.
- `select_origin(feasible_sdf, mask_centroid)`: eps-band max (0.5 px) + Manhattan-distance tiebreak + (y,x) lex — returns Python `int` tuple (not np.int64).
- `archimedean_offsets(step, max_iters)`: deterministic integer (dy,dx) list, first entry always (0,0), no duplicates.
- `place_words(request)`: per-word adaptive POI loop with 3 seeds, 500 iters/seed, 1.0s walltime.

12 unit tests covering all behavior scenarios including determinism smoke (2 runs → identical JSON).

### Task 3 — integration/test_pipeline.py (D-51)

6 end-to-end tests exercising full pipeline: PNG bytes → mask_from_bytes → sdf_cache → place_words → PlacementResult:
- Circle (convex, >=1 placed)
- Square (convex, >=1 placed)
- C-shape (concave — per-word adaptive POI handles it, D-38)
- Crescent (thin concave — placed OR dropped with valid DropReason)
- All-True mask → EmptyMaskError (D-08 fail-fast before SDF allocation)
- JSON roundtrip (Pydantic contract)

No mocking of Pillow, scipy, or numpy (D-51 compliance).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] monkeypatch target in PL11 NaN test**
- **Found during:** Task 2 GREEN phase
- **Issue:** Test patched `aerocloud.geometry.sdf_cache.get_or_build` but `placement.py` holds its own reference via `from ... import get_or_build`, so the patch didn't reach the code under test.
- **Fix:** Patched `aerocloud.geometry.placement.get_or_build` directly.
- **Files modified:** `tests/geometry/unit/test_placement.py`

**2. [Rule 2 - Complexity] Extract `_place_one_word` and `_spiral_search` from `place_words`**
- **Found during:** Task 2 ruff refactor
- **Issue:** `place_words` had PLR0912 (>12 branches) and PLR0915 (>50 statements) violations.
- **Fix:** Extracted inner loops into two private helpers: `_spiral_search` (inner offset loop) and `_place_one_word` (seed retry loop). No behavior change.
- **Files modified:** `packages/engine/src/aerocloud/geometry/placement.py`

**3. [Rule 1 - Bug] Hallucination guard false positive**
- **Found during:** Completion verification
- **Issue:** Docstring comment containing "32" in "MAX_STEP=32 creates aliasing" triggered the `grep -qE "MAX_STEP.*=.*(32|50)"` guard (regex matches across line to trailing text).
- **Fix:** Reworded docstring to "higher values create aliasing pockets" — no mention of specific blocked values in docstring.
- **Files modified:** `packages/engine/src/aerocloud/geometry/placement.py`

### Constants — No Tuning Required

All locked constants match the plan exactly. No constant was changed from the CONTEXT.md/RESEARCH.md specified values.

## Performance Notes

- Circle fixture (64x64): 10 small words placed in ~4s wall clock including SDF computation.
- C-shape fixture (concave): 3 small words, >=1 placed — per-word adaptive POI (D-38) handles concave correctly where single-origin would fail.
- The pessimistic `total_iters` in PlacementStats counts `MAX_ITERATIONS_PER_SEED` per word regardless of actual probes — actual per-candidate counting deferred to observability wave (Wave 4).

## Hallucination Guards (All Pass)

```
PASS: no MAX_STEP=32 or 50  (grep -qE "MAX_STEP.*=.*(32|50)" exits 1)
PASS: MAX_STEP=16 present    (grep -qE "MAX_STEP.*=.*16" exits 0)
PASS: DropReason present     (grep -q "DropReason" exits 0)
PASS: binary_dilation/minimum_filter present
```

## Test Counts

| Suite | New | Total |
|-------|-----|-------|
| collision unit | 8 | — |
| placement unit | 12 | — |
| integration | 6 | — |
| **Wave 3 new** | **26** | — |
| **Full geometry + regression** | — | **569** |

## Known Stubs

None. `place_words` returns real placements from real masks. `PlacementStats.total_iterations` is pessimistic (counts budget not actual probes) — this is documented above, not a stub.

## Threat Flags

No new network endpoints, auth paths, or file access patterns introduced. All inputs flow through `PlacementRequest` Pydantic model with `min_length=8` on `raw_png_bytes`. T-4-P1 (DoS via unbounded loop) and T-4-P2 (NaN propagation) are mitigated as specified in the plan threat model.

## Self-Check: PASSED

All 5 created files confirmed present on disk.
All 4 task commits confirmed in git log (ff67734, 2291032, c1c7cc1, f218e75).
569 tests pass (543 prior + 26 new).
mypy --strict: 0 issues on collision.py, placement.py, models/geometry.py.
ruff: all checks passed on src/aerocloud/geometry/ and tests/geometry/.
All 4 hallucination guards pass.

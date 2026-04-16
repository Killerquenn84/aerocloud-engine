---
phase: 07-geometry-v2
plan: 04
subsystem: geometry
tags: [multi-centric, mat, placement, voronoi, numpy, structlog, pydantic, determinism, tdd]

# Dependency graph
requires:
  - phase: 07-geometry-v2
    plan: 01
    provides: extract_mat(), get_or_build_mat(), MATResult, MATBranch — branch origins and Voronoi branch_map
  - phase: 07-geometry-v2
    plan: 03
    provides: SAT + Bitmap collision hierarchy (5-stage pipeline)
  - phase: 04-geometry-v1
    provides: place_words() pipeline internals (_place_one_word, feasibility_field, _compute_centroid)

provides:
  - place_words_multi_centric(sdf, mask, words, seed) -> MultiCentricResult public function
  - MultiCentricResult Pydantic model (placements, dropped_words, stats, branch_count, words_per_branch)
  - _assign_words_to_branches() — proportional word-to-branch assignment with deterministic tiebreak
  - _build_sub_sdf() / _build_sub_mask() — Voronoi cell masking helpers
  - _compute_targets() / _distribute_evenly() / _fix_rounding_drift() — modular target computation
  - geometry/__init__.py exports: place_words_multi_centric, MultiCentricResult

affects:
  - 07-05 onwards (seam carving, Bezier export can consume MultiCentricResult)
  - 07-06/07-07 (any plan needing multi-branch word placement)

# Tech tracking
tech-stack:
  added: []  # no new dependencies — reuses existing geometry stack
  patterns:
    - TDD RED-GREEN: 3 test files committed before implementation (ImportError confirmed)
    - Proportional assignment: sdf_volume / total_volume * n_words with round() + rounding drift fix
    - Lexicographic branch_id tiebreak: all ambiguous cases sorted by branch_id ascending (Pitfall 4)
    - Voronoi sub-SDF: np.where(branch_map == bid, sdf, 0.0) — zero outside branch cell
    - D-14 fallback: single-branch MAT silently routes to direct placement pass
    - T-07-04-03 guard: empty sub_mask -> WARN + drop all branch words
    - Refactored _assign_words_to_branches to avoid PLR0912 (too-many-branches) via helper extraction

key-files:
  created:
    - packages/engine/src/aerocloud/geometry/multi_centric.py
    - packages/engine/tests/geometry/unit/test_multi_centric.py
    - packages/engine/tests/geometry/integration/test_multi_centric_integration.py
    - packages/engine/tests/geometry/determinism/test_multi_centric_determinism.py
  modified:
    - packages/engine/src/aerocloud/geometry/__init__.py (added place_words_multi_centric, MultiCentricResult exports)

key-decisions:
  - "place_words_multi_centric takes raw sdf+mask+words+seed — does not go through PlacementRequest/PNG path; calls placement internals (_place_one_word, _compute_centroid) directly for per-branch sub-SDF placement"
  - "MultiCentricResult uses strict=False + arbitrary_types_allowed=False — no numpy arrays in result model (all numpy stays internal); merged result is pure Pydantic"
  - "_assign_words_to_branches extracts three helpers (_compute_targets, _distribute_evenly, _fix_rounding_drift) to keep branch count below ruff PLR0912 limit (12)"
  - "D-14 fallback runs single placement pass on full sdf+mask when MAT returns 1 branch — transparent to caller, branch_count=1 in result"
  - "Each branch gets its own set_seed(seed) call at _place_words_on_arrays entry — same seed per branch ensures determinism when branches are processed sequentially"

patterns-established:
  - "Voronoi sub-SDF masking: np.where(branch_map == bid, sdf, 0.0) — zero outside branch cell, original sdf inside"
  - "Proportional word assignment: round(vol/total * n) with deterministic rounding drift fix via lex branch_id order"
  - "Multi-branch merge: all_placements.extend(b_placed) in branch_id order — no sorting of final merged list"
  - "Observability: structlog bound context geometry.phase + geometry.n_branches + geometry.words_per_branch"

requirements-completed:
  - GEO2-03

# Metrics
duration: 18min
completed: 2026-04-16
---

# Phase 07 Plan 04: Multi-Centric Placement Summary

**Multi-centric word placement partitions words by MAT branch SDF volume and runs per-branch spiral placement on Voronoi sub-SDFs, enabling concave shape filling (star arms, crescent tips, C-shape ends) via lexicographically deterministic branch assignment**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-04-16T01:30:00Z
- **Completed:** 2026-04-16T01:48:00Z
- **Tasks:** 2 (TDD RED + GREEN)
- **Files modified:** 5

## Accomplishments

- Implemented `place_words_multi_centric()`: full multi-branch pipeline from MAT branch extraction through Voronoi sub-SDF masking to per-branch spiral placement and result merging
- `MultiCentricResult` Pydantic model with placements + dropped_words + stats + branch_count + words_per_branch for observability
- Proportional word assignment (`_assign_words_to_branches`) with lexicographic branch_id tiebreak for Pitfall 4 determinism (T-07-04-02)
- D-14 single-branch fallback: transparent pass-through when MAT returns 1 branch
- T-07-04-03: empty sub_mask guard — WARN log + drop words instead of crashing
- 14 new tests (8 unit + 4 integration + 2 determinism) all GREEN
- 199 total geometry tests pass — zero regressions
- mypy --strict and ruff check clean

## Task Commits

1. **Task 1: RED — Multi-Centric tests (failing)** - `6de7f4b` (test)
2. **Task 2: GREEN — implement multi_centric.py** - `3a46eef` (feat)

## Files Created/Modified

- `packages/engine/src/aerocloud/geometry/multi_centric.py` — `place_words_multi_centric()`, `MultiCentricResult`, `_assign_words_to_branches()`, `_build_sub_sdf()`, `_build_sub_mask()`, `_place_words_on_arrays()`, `_compute_targets()`, `_distribute_evenly()`, `_fix_rounding_drift()`
- `packages/engine/src/aerocloud/geometry/__init__.py` — added `place_words_multi_centric` and `MultiCentricResult` to exports and import block
- `packages/engine/tests/geometry/unit/test_multi_centric.py` — 8 unit tests: proportional assignment, determinism, no-word-loss, single-branch fallback, sub-SDF masking, sub-mask correctness, result merge placements, result merge dropped
- `packages/engine/tests/geometry/integration/test_multi_centric_integration.py` — 4 integration tests: star/crescent/C-shape concave shapes + branch origins inside mask
- `packages/engine/tests/geometry/determinism/test_multi_centric_determinism.py` — 2 determinism tests: 10-run byte-identical + different-seed sanity check

## Decisions Made

- **Direct placement internals access:** `place_words_multi_centric` bypasses `PlacementRequest`/PNG decoding path and calls `_place_one_word` + `_compute_centroid` directly. This avoids the PNG encoding/decoding overhead and keeps the multi-centric pipeline purely in array space.
- **No numpy in MultiCentricResult:** All numpy arrays remain internal to `_place_words_on_arrays`. The merged result contains only Pydantic-native types (lists, tuples, ints, floats). This simplifies serialization for the determinism test's JSON comparison.
- **Same seed per branch:** `set_seed(seed)` is called at the start of each `_place_words_on_arrays` call with the same seed. This makes each branch's placement independently deterministic while keeping the overall result reproducible across 10 runs.
- **Helper extraction for ruff PLR0912:** `_assign_words_to_branches` exceeded 12 branches. Extracted `_compute_targets`, `_distribute_evenly`, and `_fix_rounding_drift` to keep each function within the complexity limit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mypy `targets` variable redefinition via forward declaration**
- **Found during:** Task 2 (GREEN — mypy step)
- **Issue:** `targets: list[int] = []` on the `else` branch and `targets = [...]` in the `if` branch caused `Name "targets" already defined` mypy error (no-redef)
- **Fix:** Added `targets: list[int]` as a forward declaration before the if/else block
- **Files modified:** packages/engine/src/aerocloud/geometry/multi_centric.py
- **Verification:** `mypy --strict` passes
- **Committed in:** 3a46eef (Task 2 commit)

**2. [Rule 1 - Bug] Fixed mypy no-any-return for np.where and boolean mask return**
- **Found during:** Task 2 (GREEN — mypy step)
- **Issue:** `np.where(...)` and `(arr == val) & mask` both return `np.ndarray[Any]` which mypy flags as returning Any from a typed function
- **Fix:** Wrapped both in `np.asarray(..., dtype=np.float32)` and `np.asarray(..., dtype=bool)` respectively
- **Files modified:** packages/engine/src/aerocloud/geometry/multi_centric.py
- **Verification:** `mypy --strict` passes with 0 errors
- **Committed in:** 3a46eef (Task 2 commit)

**3. [Rule 1 - Bug] Fixed ruff PLR0912 too-many-branches in _assign_words_to_branches**
- **Found during:** Task 2 (GREEN — ruff check step)
- **Issue:** `_assign_words_to_branches` had 16 branches (limit is 12 per ruff PLR0912)
- **Fix:** Extracted `_compute_targets`, `_distribute_evenly`, `_fix_rounding_drift` as standalone helpers
- **Files modified:** packages/engine/src/aerocloud/geometry/multi_centric.py
- **Verification:** `ruff check` passes with 0 errors
- **Committed in:** 3a46eef (Task 2 commit)

**4. [Rule 1 - Bug] Fixed ruff B905 zip() without strict=**
- **Found during:** Task 2 (GREEN — ruff check step)
- **Issue:** `zip(sorted_branches, assignment)` missing explicit `strict=` parameter
- **Fix:** Changed to `zip(sorted_branches, assignment, strict=True)` — lengths always equal by construction
- **Files modified:** packages/engine/src/aerocloud/geometry/multi_centric.py
- **Verification:** `ruff check` passes
- **Committed in:** 3a46eef (Task 2 commit)

**5. [Rule 1 - Bug] Fixed ruff B007 unused loop variables**
- **Found during:** Task 2 (GREEN — ruff check step)
- **Issue:** `for w, h, ww in branch_words:` — `h` and `ww` unused in loop body
- **Fix:** Renamed to `_h` and `_ww` per Python convention
- **Files modified:** packages/engine/src/aerocloud/geometry/multi_centric.py
- **Verification:** `ruff check` passes
- **Committed in:** 3a46eef (Task 2 commit)

---

**Total deviations:** 5 auto-fixed (all Rule 1 — static analysis bugs caught by mandatory mypy/ruff steps)
**Impact on plan:** All fixes necessary for correctness and code quality. No scope creep. Fixes driven by mypy strict mode and ruff complexity rules.

## Issues Encountered

None beyond the ruff/mypy issues above. The proportional assignment algorithm required careful handling of rounding drift (sum(round(p_i * n)) can be n±k due to floating-point rounding) — handled by `_fix_rounding_drift` with lexicographic branch_id tiebreak for Pitfall 4 compliance.

## Known Stubs

None — all multi-centric functionality is implemented and exercised by tests.

## Threat Surface Scan

No new network endpoints, auth paths, or trust boundary surface introduced. All new surface is pure Python in-process computation (multi_centric.py). Four STRIDE threats from the plan's threat register:

| Threat | Mitigation | Status |
|--------|-----------|--------|
| T-07-04-01 DoS: place_words called N times | N bounded by min_branch_radius (typically 2-8); per-word wallclock budget from D-42 | Accepted |
| T-07-04-02 Tampering: word assignment non-determinism | Lex branch_id tiebreak in _assign_words_to_branches; test_multi_centric_10run_identical GREEN | Implemented |
| T-07-04-03 DoS: degenerate sub_mask zero pixels | Empty sub_mask guard: log WARN, drop words to dropped list, skip branch | Implemented |
| T-07-04-04 Info disclosure: logs word list | Word text is not PII; no sensitive data in structlog output | Accepted |

## Next Phase Readiness

- `place_words_multi_centric()` is ready for consumption by Plans 07-05 through 07-07
- `MultiCentricResult` serializes to JSON cleanly via `.model_dump_json()` — determinism test confirmed
- Branch count is observable via `result.branch_count` and `result.words_per_branch`
- No blockers for remaining Phase 07 waves

## Self-Check: PASSED

| Item | Status |
|------|--------|
| packages/engine/src/aerocloud/geometry/multi_centric.py | FOUND |
| packages/engine/src/aerocloud/geometry/__init__.py | FOUND (exports added) |
| packages/engine/tests/geometry/unit/test_multi_centric.py | FOUND |
| packages/engine/tests/geometry/integration/test_multi_centric_integration.py | FOUND |
| packages/engine/tests/geometry/determinism/test_multi_centric_determinism.py | FOUND |
| .planning/phases/07-geometry-v2/07-04-SUMMARY.md | FOUND |
| commit 6de7f4b (RED test) | FOUND |
| commit 3a46eef (GREEN feat) | FOUND |

---
*Phase: 07-geometry-v2*
*Completed: 2026-04-16*

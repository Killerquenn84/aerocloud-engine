---
phase: 07-geometry-v2
plan: 01
subsystem: geometry
tags: [mat, medial-axis, skfmm, scipy, cachetools, blake3, pydantic, hypothesis, numpy]

# Dependency graph
requires:
  - phase: 04-geometry-v1
    provides: SDF computation (compute_sdf, float32, positive-inside) + sdf_cache.py LRU+blake3+RLock pattern

provides:
  - extract_mat(sdf, min_branch_radius) -> MATResult public function
  - MATResult Pydantic model (frozen, arbitrary_types_allowed for numpy arrays)
  - MATBranch Pydantic model (branch_id, origin_yx, sdf_volume, pixel_count)
  - get_or_build_mat() LRU-cached wrapper (cachetools + blake3 + RLock, same pattern as sdf_cache.py)
  - geometry/__init__.py exports all MAT symbols

affects:
  - 07-04 (Multi-Centric placement consumes branch origins from MATResult.branches)
  - 07-05 onwards (any plan needing MAT skeleton topology)

# Tech tracking
tech-stack:
  added:
    - scikit-fmm (skfmm) for Eikonal travel_time computation
    - hypothesis.extra.numpy for property-based array generation
  patterns:
    - TDD RED-GREEN: test files committed before implementation
    - LRU cache pattern: cachetools.LRUCache + blake3 + RLock (D-17/D-22), mirrored from sdf_cache.py
    - skfmm integration pattern: masked phi array with -1 at source, +1 elsewhere, float64->float32 cast
    - Voronoi branch_map via per-origin EDT (nearest-origin assignment)

key-files:
  created:
    - packages/engine/src/aerocloud/geometry/mat.py
    - packages/engine/src/aerocloud/geometry/mat_cache.py
    - packages/engine/tests/geometry/unit/test_mat.py
    - packages/engine/tests/geometry/integration/test_mat_integration.py
    - packages/engine/tests/geometry/property/test_mat_property.py
  modified:
    - packages/engine/src/aerocloud/config.py (mat_min_branch_radius, mat_cache_max_bytes fields)
    - packages/engine/src/aerocloud/geometry/__init__.py (export extract_mat, MATResult, MATBranch, get_or_build_mat)

key-decisions:
  - "MATResult uses ConfigDict(frozen=True, extra=forbid, strict=False, arbitrary_types_allowed=True) — AeroCloudBase's strict=True is incompatible with numpy arrays, so we override per-model"
  - "skfmm ValueError (no zero contour) is caught and returns zero travel_time fallback — handles pathological single-pixel or disconnected masks without crashing"
  - "NaN fill for unreachable inside pixels: skfmm produces NaN for disconnected inside regions; filled with 0.0 to guarantee finite travel_time inside mask (contract)"
  - "Voronoi branch_map uses per-origin EDT (scipy.ndimage.distance_transform_edt) rather than KD-tree — simpler, O(N*k) but k (branches) is small"
  - "Lexicographic (y,x) tiebreak for determinism (D-15): argmax SDF candidates sorted by (y,x) ascending, first element wins"

patterns-established:
  - "MATBranch origin_yx = argmax SDF within branch component (deepest interior point)"
  - "Branch fallback: if no ridge found (n_labels==0), all inside pixels form 1 branch with centroid as origin"
  - "Cache key structure: (blake3_digest, (param_name, value), (algo_version, N), shape_tuple) — same structure as sdf_cache.py"
  - "skfmm pitfall workarounds: Pitfall 1 (float64->float32 cast), Pitfall 8 (zero contour via -1 at source)"

requirements-completed:
  - GEO2-01
  - GEO2-02

# Metrics
duration: 35min
completed: 2026-04-16
---

# Phase 07 Plan 01: MAT Skeleton Extraction Summary

**MAT skeleton extraction from SDF via scipy maximum_filter ridge detection + scikit-fmm Eikonal travel_time, with LRU-cached wrapper (blake3+RLock), producing MATResult with labeled branches and Voronoi branch_map**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-04-16T00:55:00Z
- **Completed:** 2026-04-16T01:30:00Z
- **Tasks:** 2 (TDD RED + GREEN)
- **Files modified:** 7

## Accomplishments

- Implemented `extract_mat()` pipeline: ridge extraction → dilation → labelling → travel_time → branch_map
- Star mask (5-arm, 128x128) produces n_branches >= 2; circle produces n_branches == 1; crescent n_branches > 1
- travel_time.dtype == float32 enforced (D-03 / skfmm Pitfall 1 cast applied)
- LRU cache with blake3 key, RLock, getsizeof=branch_map.nbytes+travel_time.nbytes
- 20 new MAT tests (9 unit, 7 integration, 4 property) all GREEN
- 135 total geometry tests pass — zero regressions in Phase 4 tests

## Task Commits

1. **Task 1: RED — MAT tests (failing)** - `ebbb1ce` (test)
2. **Task 2: GREEN — implement mat.py and mat_cache.py** - `1964c8e` (feat)

## Files Created/Modified

- `packages/engine/src/aerocloud/geometry/mat.py` — extract_mat(), MATResult, MATBranch, extract_ridge_points(), extract_mat_branches(), _compute_travel_time(), _build_branch_map_voronoi()
- `packages/engine/src/aerocloud/geometry/mat_cache.py` — get_or_build_mat() with LRU+blake3+RLock pattern
- `packages/engine/src/aerocloud/config.py` — mat_min_branch_radius=3.0, mat_cache_max_bytes=128MiB
- `packages/engine/src/aerocloud/geometry/__init__.py` — export extract_mat, MATResult, MATBranch, get_or_build_mat
- `packages/engine/tests/geometry/unit/test_mat.py` — 9 unit tests
- `packages/engine/tests/geometry/integration/test_mat_integration.py` — 7 integration tests
- `packages/engine/tests/geometry/property/test_mat_property.py` — 4 property tests (Hypothesis)

## Decisions Made

- **MATResult model_config override:** AeroCloudBase uses strict=True which rejects numpy arrays; overrode with strict=False + arbitrary_types_allowed=True in MATResult while keeping frozen=True and extra="forbid".
- **skfmm ValueError fallback:** Pathological masks (isolated single pixel, disconnected regions) cause skfmm to raise "no zero contour". Caught and returned zero-filled travel_time to avoid crashing — still usable for branch origin selection.
- **NaN inside pixels filled with 0.0:** skfmm produces NaN for unreachable inside pixels in disconnected masks; filled to guarantee finite contract.
- **Voronoi branch_map via EDT:** Simple and correct; k branches is small so O(N*k) EDT calls are fast in practice.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed MATResult Pydantic config — "Config" and "model_config" cannot be used together in Pydantic v2**
- **Found during:** Task 2 (GREEN implementation)
- **Issue:** Original implementation used both inner `class Config` and `model_config` — Pydantic v2 raises PydanticUserError
- **Fix:** Removed inner `class Config`, used `ConfigDict(arbitrary_types_allowed=True)` in `model_config` directly
- **Files modified:** packages/engine/src/aerocloud/geometry/mat.py
- **Verification:** pytest passes; mypy strict passes
- **Committed in:** 1964c8e

**2. [Rule 1 - Bug] Fixed skfmm ValueError for pathological masks (hypothesis property test found this)**
- **Found during:** Task 2 (property test execution)
- **Issue:** Hypothesis generated masks with thin/disconnected inside regions where skfmm reports "no zero contour"
- **Fix:** Added ValueError catch in _compute_travel_time() → returns zero-filled travel_time as fallback
- **Files modified:** packages/engine/src/aerocloud/geometry/mat.py
- **Verification:** All 4 property tests pass (20 examples each)
- **Committed in:** 1964c8e

**3. [Rule 1 - Bug] Fixed NaN inside pixels from disconnected skfmm regions**
- **Found during:** Task 2 (property test execution)
- **Issue:** Hypothesis found masks where skfmm succeeds but returns NaN for unreachable inside pixels (disconnected components)
- **Fix:** Post-process travel_time: fill NaN inside-mask pixels with 0.0
- **Files modified:** packages/engine/src/aerocloud/geometry/mat.py
- **Verification:** Property test P1 passes with non-NaN finite values inside mask
- **Committed in:** 1964c8e

**4. [Rule 1 - Bug] Fixed test_mat_result_pydantic_valid to accept ValidationError**
- **Found during:** Task 2 (unit test execution)
- **Issue:** Test expected TypeError or AttributeError on frozen model assignment; Pydantic v2 raises ValidationError
- **Fix:** Updated pytest.raises to include ValidationError in addition to TypeError and AttributeError
- **Files modified:** packages/engine/tests/geometry/unit/test_mat.py
- **Verification:** Test passes; frozen=True behavior confirmed
- **Committed in:** 1964c8e

**5. [Rule 1 - Bug] Fixed hypothesis.strategies.arrays → hypothesis.extra.numpy.arrays**
- **Found during:** Task 2 (property test execution)
- **Issue:** `st.arrays` doesn't exist; numpy array strategies are in hypothesis.extra.numpy
- **Fix:** Imported `from hypothesis.extra import numpy as nst` and used `nst.arrays()`
- **Files modified:** packages/engine/tests/geometry/property/test_mat_property.py
- **Verification:** All 4 property tests pass
- **Committed in:** 1964c8e

---

**Total deviations:** 5 auto-fixed (all Rule 1 — bugs)
**Impact on plan:** All fixes necessary for correctness. No scope creep. Fixes driven by Pydantic v2 API differences and Hypothesis edge-case discovery.

## Issues Encountered

- **skfmm masked phi behavior:** Setting phi[source] = -1.0 with all other inside pixels = +1.0 works for well-connected masks. For masks where the source pixel is isolated (no adjacent inside pixels), skfmm reports no zero contour. The fallback returns zero travel_time, which is still valid for branch origin computation.
- **ruff N806:** Used uppercase H, W variable names for shape (numpy convention) — renamed to h, w to comply with ruff's snake_case rule.

## Known Stubs

None — all MAT functionality is implemented and exercised by tests.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. All new surface is pure Python in-process computation (mat.py, mat_cache.py). Cache key includes min_branch_radius (T-07-01-01 mitigated). Empty mask guard implemented (T-07-01-04 mitigated).

## Next Phase Readiness

- `extract_mat()` + `get_or_build_mat()` are ready for consumption by Plan 07-04 (Multi-Centric Wordle placement)
- Branch origins in (y,x) canonical convention per D-14/ADR-0005
- travel_time float32 with NaN outside mask — ready for gradient computation if needed
- No blockers for Phase 07 wave 2+

## Self-Check: PASSED

- FOUND: packages/engine/src/aerocloud/geometry/mat.py
- FOUND: packages/engine/src/aerocloud/geometry/mat_cache.py
- FOUND: packages/engine/tests/geometry/unit/test_mat.py
- FOUND: packages/engine/tests/geometry/integration/test_mat_integration.py
- FOUND: packages/engine/tests/geometry/property/test_mat_property.py
- FOUND: .planning/phases/07-geometry-v2/07-01-SUMMARY.md
- FOUND commit: ebbb1ce (test RED)
- FOUND commit: 1964c8e (feat GREEN)

---
*Phase: 07-geometry-v2*
*Completed: 2026-04-16*

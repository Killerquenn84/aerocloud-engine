---
phase: 11-outer-loop-v2
plan: 02
subsystem: optimizer
tags: [cqd, quality-diversity, monte-carlo, theta-sweep, sklearn, numpy, pydantic, tdd]

# Dependency graph
requires:
  - phase: 11-outer-loop-v2
    provides: ArchiveWrapper.data() with objective + measures arrays (Plan 11-01)

provides:
  - CQDResult Pydantic model (frozen, strict, extra-forbid) with cqd + theta_curve
  - compute_cqd() vectorized Monte-Carlo CQD over raw numpy arrays
  - compute_cqd_from_archive() thin wrapper extracting from ArchiveWrapper.data()

affects:
  - 11-03-pareto-front (CQD score feeds into BOP-Elites evaluation loop)

# Tech tracking
tech-stack:
  added:
    - sklearn.neighbors.NearestNeighbors (ball_tree algorithm for O(n log n) NN search)
  patterns:
    - TDD Red-Green-Commit cycle (failing test committed before implementation)
    - Vectorized omega matrix [n_samples, n_theta] via numpy broadcasting (single op)
    - Fixed-seed np.random.default_rng() for bit-exact reproducibility (OUTER2-05)
    - np.convolve(window=3, mode='same') for running-average theta-curve smoothing (D-07)

key-files:
  created:
    - packages/engine/src/aerocloud/outer_loop/cqd.py
    - packages/engine/tests/qd/test_cqd.py
  modified: []

key-decisions:
  - "Raw numpy arrays interface: compute_cqd() takes raw arrays (not ArchiveWrapper) for testability; compute_cqd_from_archive() is the thin wrapper"
  - "delta_max = sqrt(4) = 2.0 hardcoded: behavior space is always [0,1]^4 per Blueprint Teil VIII"
  - "Guard len(objectives) < 2 returns zeros: single elite has no diversity, empty archive is undefined"
  - "f_range = max(f_max - f_min, 1e-8): Pitfall 4 mitigation — identical fitness values must not cause div-by-zero"

patterns-established:
  - "CQD vectorization: f_norm[:, None] - thetas[None, :] * delta_norm[:, None] builds (n_samples, 51) omega in one broadcast op"
  - "Guard-and-return pattern for trivial archives: < 2 elites → immediate zero result, no NN search attempted"

requirements-completed:
  - OUTER2-03
  - OUTER2-04
  - OUTER2-05
  - OUTER2-06

# Metrics
duration: 3min
completed: 2026-04-21
---

# Phase 11 Plan 02: CQD Quality-Diversity Metric Summary

**Vectorized Monte-Carlo CQD metric with NearestNeighbors ball_tree NN, (n_samples x 51) omega broadcast, window=3 smoothed theta-curve, and bit-exact seeded reproducibility**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-21T22:31:16Z
- **Completed:** 2026-04-21T22:34:50Z
- **Tasks:** 2 (TDD: RED commit + GREEN commit)
- **Files modified:** 2 (1 created source, 1 created test)

## Accomplishments

- CQDResult Pydantic model inheriting AeroCloudBase (frozen, strict, extra-forbid) with field_validator ensuring finite float values in theta_curve
- compute_cqd() implements D-06 formula with sklearn NearestNeighbors ball_tree for efficient NN lookup, vectorized omega matrix via numpy broadcasting, D-07 theta-sweep (51 values smoothed with window=3 running average), and fixed-seed np.random.default_rng() for OUTER2-05 determinism
- compute_cqd_from_archive() thin wrapper extracts objective + measures from ArchiveWrapper.data() and delegates to compute_cqd()
- 22 tests pass covering all plan requirements; 193/193 qd tests pass (zero regressions); mypy --strict clean

## Task Commits

1. **RED phase: failing CQD tests** - `a78da46` (test)
2. **GREEN phase: cqd.py implementation + test fixture fix** - `3103c01` (feat)

## Files Created/Modified

- `packages/engine/src/aerocloud/outer_loop/cqd.py` — CQDResult model, compute_cqd(), compute_cqd_from_archive(); 161 lines
- `packages/engine/tests/qd/test_cqd.py` — 22 unit tests across 8 BDD scenarios; 458 lines

## Decisions Made

- Raw numpy arrays as primary interface: compute_cqd(objectives, measures, ...) operates on raw arrays, not ArchiveWrapper. This makes the metric testable without archive infrastructure and reusable in any context. The thin wrapper compute_cqd_from_archive() bridges to ArchiveWrapper.
- delta_max = sqrt(4) = 2.0 hardcoded: the behavior space is always [0,1]^4 (shape_fidelity, rotation_ratio, symmetry, semantic_clustering) per Blueprint Teil VIII. No configuration needed.
- Guard threshold at < 2 elites (not < 1): single elite has no behavioral diversity; distance from any ref point goes to that one elite, making the diversity dimension of CQD undefined/trivial. Plan specified this guard.
- sklearn NearestNeighbors over scipy.spatial.cKDTree: plan specified sklearn; both are fast for 500 elites. ball_tree is well-suited for 4D Euclidean and gives consistent sub-25ms results.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ArchiveConfig constructor in test missing required solution_dim field**
- **Found during:** GREEN phase (test_compute_cqd_from_archive_matches_raw)
- **Issue:** Test fixture created ArchiveConfig with max_words=10 but omitted solution_dim (a required field with no default). ValidationError raised on construction.
- **Fix:** Added solution_dim=40 (= max_words * 4 = 10 * 4) to the ArchiveConfig constructor call in the test.
- **Files modified:** packages/engine/tests/qd/test_cqd.py
- **Verification:** All 22 tests pass; no other tests affected.
- **Committed in:** 3103c01 (GREEN feat commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — test fixture bug)
**Impact on plan:** Fix was to test code only (missing required field value). Implementation was unaffected.

## Issues Encountered

None beyond the ArchiveConfig fixture fix documented above.

## Threat Model Coverage

| Threat ID | Status |
|-----------|--------|
| T-11-04 (DoS — compute_cqd empty archive) | MITIGATED — guard len(objectives) < 2 returns zeros immediately; no NN search or matrix allocation |
| T-11-05 (Tampering — CQD inputs) | ACCEPTED — internal engine metric, NaN/Inf from archive caught by archive clamp (Plan 11-01) |

## Known Stubs

None — compute_cqd() is fully implemented and wired to archive.data().

## Next Phase Readiness

- Plan 11-03 (Pareto-Front + Pareto-Slider): CQD score is ready to use. compute_cqd_from_archive() accepts any ArchiveWrapper, so Plan 11-03 can call it directly after each OuterLoop iteration.
- No blockers.

## Self-Check

Files created/exist:
- `packages/engine/src/aerocloud/outer_loop/cqd.py` — FOUND
- `packages/engine/tests/qd/test_cqd.py` — FOUND

Commits exist:
- `a78da46` test(11-02): add failing tests for CQD metric (RED phase) — FOUND
- `3103c01` feat(11-02): CQD metric — vectorized Monte-Carlo + theta-sweep (GREEN phase) — FOUND

## Self-Check: PASSED

---
*Phase: 11-outer-loop-v2*
*Completed: 2026-04-21*

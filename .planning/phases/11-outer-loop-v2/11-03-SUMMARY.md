---
phase: 11-outer-loop-v2
plan: 03
subsystem: optimizer
tags: [pareto, pymoo, non-dominated-sorting, hypervolume, cqd-hv, pareto-slider, quality-diversity, pydantic, tdd]

# Dependency graph
requires:
  - phase: 11-outer-loop-v2
    provides: ArchiveWrapper.data() with objective + measures + layout_coverage + space_saving (Plan 11-01)
  - phase: 11-outer-loop-v2
    provides: compute_cqd() and CQDResult (Plan 11-02)

provides:
  - ParetoFront Pydantic model (frozen, strict, extra-forbid) with indices, design_fidelity, packing_density
  - extract_pareto_front(): NonDominatedSorting on negated 2D objectives (D-11, Pitfall 6 compliant)
  - compute_cqd_hv(): per-cell hypervolume sum via pymoo HV (D-10, SC5 monotone)
  - pareto_slider(): nearest Pareto point at interpolated position (D-14, SC4)
  - extract_pareto_front_from_archive(): thin wrapper over ArchiveWrapper.data()

affects:
  - 12-production (Pareto-Slider exposed via FastAPI; CQD_HV logged per iteration)

# Tech tracking
tech-stack:
  added:
    - pymoo.util.nds.non_dominated_sorting.NonDominatedSorting (Pareto extraction)
    - pymoo.indicators.hv.HV (hypervolume computation, already in qd optional-dep group)
  patterns:
    - TDD Red-Green-Commit cycle (failing test committed before implementation)
    - Negated objectives for pymoo minimization framing (Pitfall 6)
    - Per-cell HV aggregation via floor(measure * bins_per_dim) cell assignment (D-10)
    - Linear interpolation + Euclidean nearest-neighbor for Pareto-Slider (D-14)
    - Pure function + thin wrapper pattern (matches CQD Plan 11-02 pattern)

key-files:
  created:
    - packages/engine/src/aerocloud/outer_loop/pareto.py
    - packages/engine/tests/qd/test_pareto.py
  modified: []

key-decisions:
  - "pymoo HV uses minimization framing: negate objectives before HV(), ref_point=[0,0] (Pitfall 6)"
  - "Cell assignment via floor(measure * bins_per_dim) clipped to [0, bins-1]: mirrors pyribs GridArchive internal binning"
  - "pareto_slider() sorts Pareto front by design_fidelity descending, then linear-interpolates target between extremes"
  - "empty Pareto front raises ValueError; 1-point front returns that single elite for any position"
  - "ParetoFront model uses strict=False for list[float] to allow numpy scalar coercion via .tolist()"

patterns-established:
  - "Pareto-Slider interpolation: target_df = max_df*(1-pos) + min_df*pos; nearest by Euclidean distance in 2D objective space"
  - "HV per-cell grouping: dict[tuple[int,...], list[int]] keyed by discrete cell ID"

requirements-completed:
  - OUTER2-07
  - OUTER2-08
  - OUTER2-09

# Metrics
duration: 4min
completed: 2026-04-21
---

# Phase 11 Plan 03: Pareto-Front + CQD_HV + Pareto-Slider Summary

**pymoo-powered Pareto-Front extraction with per-cell CQD_HV hypervolume sum (D-10) and design_fidelity/packing_density interpolating Pareto-Slider (D-14, SC4)**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-21T22:36:50Z
- **Completed:** 2026-04-21T22:41:22Z
- **Tasks:** 2 (TDD: RED commit + GREEN commit)
- **Files modified:** 2 (1 created source, 1 created test)

## Accomplishments

- ParetoFront Pydantic model (frozen, strict=False for tolist() coercion, extra-forbid) with indices + 2D objective lists
- extract_pareto_front() calls pymoo NonDominatedSorting on negated 2D objectives (design_fidelity=m0+m2, packing_density=lc+ss per D-11); handles empty archive with empty ParetoFront
- compute_cqd_hv() groups elites into grid cells via floor(measure*bins_per_dim), computes pymoo HV per cell with negated objectives, sums (D-10); hand-calculated reference 1.90 verified to 1e-6
- pareto_slider() clips position [0,1], sorts Pareto front by design_fidelity descending, interpolates target, returns nearest by Euclidean distance; handles 0-point (ValueError) and 1-point (return directly) degenerate fronts
- 15/15 tests pass; 208/208 qd tests pass (zero regressions); mypy --strict clean

## Task Commits

1. **RED phase: failing Pareto tests** - `3319908` (test)
2. **GREEN phase: pareto.py implementation + dominance-check bug fix** - `6dc653d` (feat)

## Files Created/Modified

- `packages/engine/src/aerocloud/outer_loop/pareto.py` — ParetoFront model, extract_pareto_front(), compute_cqd_hv(), pareto_slider(), extract_pareto_front_from_archive(); 255 lines
- `packages/engine/tests/qd/test_pareto.py` — 15 unit tests across 5 BDD scenarios; 470 lines

## Decisions Made

- pymoo HV requires minimization framing: negate all objective values, use ref_point=[0,0]. This is correct because after negation F_neg = -F ∈ (-∞, 0], and ref_point=[0,0] is dominated by all points (as pymoo requires). (Pitfall 6)
- Cell assignment mirrors pyribs GridArchive internal binning: `floor(measure * bins_per_dim)` clipped to `[0, bins_per_dim-1]`. This ensures compute_cqd_hv() cells are semantically identical to archive grid cells.
- ParetoFront model sets `strict=False` (overriding AeroCloudBase default). This is needed because `numpy_array.tolist()` produces Python floats and ints which pass strict=False coercion, but numpy scalar subtypes would fail strict=True int/float validation.
- pareto_slider() raises ValueError on empty front (not returns None) — consistent with Python stdlib conventions for "impossible operation" rather than silent fallback.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Dominance check in test_pareto_front_no_dominated_points used wrong column**
- **Found during:** GREEN phase (first test run)
- **Issue:** Test code wrote `pareto_df[a] >= pareto_pd[b]` (comparing df of a against pd of b) instead of `pareto_df[a] >= pareto_df[b]` — causing false-positive domination detection
- **Fix:** Corrected comparison to `pareto_df[a] >= pareto_df[b]`
- **Files modified:** packages/engine/tests/qd/test_pareto.py
- **Verification:** All 15 tests pass after fix; dominance check now logically correct
- **Committed in:** 6dc653d (GREEN feat commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — typo in test logic, no scope creep)
**Impact on plan:** Fix was to test code only. Implementation was correct on first run.

## Issues Encountered

None beyond the dominance check typo documented above.

## Threat Model Coverage

| Threat ID | Status |
|-----------|--------|
| T-11-06 (DoS — compute_cqd_hv) | MITIGATED — cell iteration is O(n_elites); pymoo HV is O(n log n) per cell; bounded by archive capacity |
| T-11-07 (Tampering — pareto_slider) | MITIGATED — position clipped to [0.0, 1.0] via np.clip(); empty and 1-point degenerate fronts handled |

## Known Stubs

None — all three functions are fully implemented and wired to archive.data().

## Next Phase Readiness

- Plan 11-04+ (if any): Pareto-Front + CQD_HV + Pareto-Slider are complete and ready
- Phase 12 (Production): extract_pareto_front_from_archive() and pareto_slider() can be called directly after each OuterLoop iteration; expose via FastAPI response model
- No blockers

## Self-Check

Files created/exist:
- `packages/engine/src/aerocloud/outer_loop/pareto.py` — FOUND
- `packages/engine/tests/qd/test_pareto.py` — FOUND

Commits exist:
- `3319908` test(11-03): add failing tests for Pareto-Front, CQD_HV, Pareto-Slider (RED phase) — FOUND
- `6dc653d` feat(11-03): Pareto-Front + CQD_HV + Pareto-Slider (GREEN phase) — FOUND

## Self-Check: PASSED

---
*Phase: 11-outer-loop-v2*
*Completed: 2026-04-21*

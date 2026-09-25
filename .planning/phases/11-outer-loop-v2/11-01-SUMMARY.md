---
phase: 11-outer-loop-v2
plan: 01
subsystem: optimizer
tags: [pyribs, bop-elites, bayesian-optimization, map-elites, quality-diversity, gp, sklearn, pydantic]

# Dependency graph
requires:
  - phase: 09-outer-loop-v1
    provides: ArchiveWrapper, GaussianEmitter, GridArchive, OuterLoop, QualityMetrics

provides:
  - CappedBOPEmitter subclass of BayesianOptimizationEmitter with history_cap trimming
  - ArchiveConfig extended with lower_bounds, upper_bounds, num_initial_samples, history_cap, emitter_type
  - ArchiveWrapper supporting both gaussian and bop emitter types via config
  - GridArchive always constructed with extra_fields layout_coverage + space_saving
  - OuterLoop.single_iteration() extracts and passes layout_coverage + space_saving to tell()

affects:
  - 11-02-cqd (CQD metric needs archive with extra_fields)
  - 11-03-pareto-front (Pareto-Slider needs layout_coverage + space_saving in archive.data())

# Tech tracking
tech-stack:
  added:
    - ribs.emitters.BayesianOptimizationEmitter (BOP-Elites EJIE, already installed)
    - ribs.schedulers.BayesianOptimizationScheduler (BOP scheduler)
  patterns:
    - TDD Red-Green-Commit cycle (failing test committed before implementation)
    - History-capped GP subclass pattern (trim _dataset to last N entries before super().tell())
    - extra_fields in GridArchive for persistent Pareto objectives per elite
    - Emitter factory via config.emitter_type literal ('gaussian'|'bop')

key-files:
  created:
    - packages/engine/src/aerocloud/outer_loop/bop_emitter.py
    - packages/engine/tests/qd/test_bop_emitter.py
  modified:
    - packages/engine/src/aerocloud/outer_loop/models.py
    - packages/engine/src/aerocloud/outer_loop/archive.py
    - packages/engine/src/aerocloud/outer_loop/scheduler.py
    - packages/engine/tests/qd/test_archive.py

key-decisions:
  - "GPyTorch NOT installed — D-02 fallback: history_cap via subclass trims _dataset to last 200 entries, keeping sklearn GP under 0.02s"
  - "GridArchive always includes extra_fields layout_coverage+space_saving (not only for BOP), so Pareto-Slider works with gaussian emitter too"
  - "tell() backwards compat: layout_coverage/space_saving default to zeros(batch_size) when None — existing callers unaffected"
  - "history_cap minimum is 10 (T-11-02 DoS mitigation, validated in CappedBOPEmitter constructor)"
  - "BayesianOptimizationEmitter requires num_initial_samples; no default — made required in CappedBOPEmitter and defaulted to 20 in ArchiveConfig"

patterns-established:
  - "Emitter factory pattern: config.emitter_type literal selects _build_gaussian_scheduler or _build_bop_scheduler"
  - "Extra fields clamping: T-11-01 mitigated by np.clip() in ArchiveWrapper.tell() for both measures and extra_fields"
  - "History capping: _trim_dataset() called inside overridden tell(), keeps last history_cap rows (FIFO drop)"

requirements-completed:
  - OUTER2-01
  - OUTER2-02

# Metrics
duration: 35min
completed: 2026-04-16
---

# Phase 11 Plan 01: BOP-Elites Emitter + ArchiveWrapper Upgrade Summary

**CappedBOPEmitter replacing GaussianEmitter with sklearn GP history-capping and GridArchive extra_fields (layout_coverage, space_saving) persisted per elite for Pareto-Slider**

## Performance

- **Duration:** 35 min
- **Started:** 2026-04-16T22:21:32Z
- **Completed:** 2026-04-16T22:56:42Z
- **Tasks:** 2 (each with TDD Red + Green cycle)
- **Files modified:** 6

## Accomplishments

- CappedBOPEmitter subclasses BayesianOptimizationEmitter with O(n^3) GP blowup prevention via `_trim_dataset()` capping to last `history_cap` entries (FIFO)
- ArchiveConfig extended with 5 new fields (lower_bounds, upper_bounds, num_initial_samples, history_cap, emitter_type) with full backwards compatibility (all default to Phase 9 gaussian behaviour)
- ArchiveWrapper factory selects emitter from config.emitter_type: gaussian → Scheduler, bop → BayesianOptimizationScheduler
- GridArchive always includes extra_fields={'layout_coverage': ..., 'space_saving': ...} regardless of emitter type — enables Pareto-Slider for Plans 11-02 and 11-03
- OuterLoop.single_iteration() now extracts metrics.layout_coverage and metrics.space_saving per solution and passes them to archive.tell()
- mypy --strict clean on all 4 modified source files; 171/171 qd tests pass (zero regressions)

## Task Commits

Each task committed atomically with TDD Red phase committed first:

1. **Task 1 RED: CappedBOPEmitter tests** - `59e2fcc` (test)
2. **Task 1 GREEN: CappedBOPEmitter + extended ArchiveConfig** - `0790078` (feat)
3. **Task 2 RED: ArchiveWrapper BOP + extra_fields tests** - `5819f19` (test)
4. **Task 2 GREEN: ArchiveWrapper BOP upgrade + OuterLoop tell()** - `0573050` (feat)

## Files Created/Modified

- `packages/engine/src/aerocloud/outer_loop/bop_emitter.py` — CappedBOPEmitter with history_cap + _trim_dataset()
- `packages/engine/src/aerocloud/outer_loop/models.py` — ArchiveConfig extended with BOP fields + model_config override for arbitrary_types_allowed
- `packages/engine/src/aerocloud/outer_loop/archive.py` — ArchiveWrapper with emitter factory, extra_fields in GridArchive, updated tell() signature
- `packages/engine/src/aerocloud/outer_loop/scheduler.py` — OuterLoop.single_iteration() collects layout_coverage + space_saving, passes to tell()
- `packages/engine/tests/qd/test_bop_emitter.py` — 14 new tests for CappedBOPEmitter + extended ArchiveConfig
- `packages/engine/tests/qd/test_archive.py` — 8 new tests for BOP emitter selection, extra_fields storage, OuterLoop integration

## Decisions Made

- GPyTorch is NOT installed in the venv — used D-02 fallback path: subclass BayesianOptimizationEmitter and trim `_dataset` dict to last `history_cap` rows before each GP training call. history_cap=200 keeps sklearn GP fit under 0.02s.
- GridArchive always has extra_fields regardless of emitter_type — this simplifies downstream Pareto-Slider code (Plans 11-02, 11-03) which only queries archive.data() without caring about emitter type.
- `tell()` backwards compat: `layout_coverage=None` and `space_saving=None` default to `np.zeros(batch_size)` — existing Phase 9/10 callers pass no extra args and still work.
- `history_cap` minimum enforced at 10 (T-11-02: prevents trivial DoS via 0-cap making GP useless).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test fixtures used max_words=8 below the ge=10 constraint**
- **Found during:** Task 2 (TestBOPEmitterSelection and OuterLoop integration test)
- **Issue:** Two test fixtures specified max_words=8, which fails ArchiveConfig validation (ge=10)
- **Fix:** Changed max_words=8 → max_words=10 and solution_dim=32 → solution_dim=40 in both fixtures
- **Files modified:** packages/engine/tests/qd/test_archive.py
- **Verification:** All 21 archive tests pass after fix
- **Committed in:** 0573050 (Task 2 feat commit)

**2. [Rule 1 - Bug] SaturationMonitor does not accept plateau_threshold kwarg**
- **Found during:** Task 2 (OuterLoop integration test)
- **Issue:** Test used SaturationMonitor(window=5, plateau_threshold=0.01) but the class only accepts window
- **Fix:** Removed plateau_threshold kwarg from SaturationMonitor constructor call
- **Files modified:** packages/engine/tests/qd/test_archive.py
- **Verification:** OuterLoop integration test passes
- **Committed in:** 0573050 (Task 2 feat commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — test fixture bugs, no scope creep)
**Impact on plan:** Fixes were to test code only (wrong constructor arg values). Implementation was unaffected.

## Issues Encountered

- BayesianOptimizationEmitter._dataset is typed as `dict[str, object]` internally — used `# type: ignore[assignment]` with a local typed alias `dict[str, np.ndarray]` for mypy to accept `len()` and indexing operations on dataset values.
- `_EXTRA_FIELDS` type annotation needed `dict[str, Any]` instead of `dict[str, tuple[tuple[()], type]]` because mypy's invariant dict constraint rejected the covariant value type from pyribs.

## Threat Model Coverage

| Threat ID | Status |
|-----------|--------|
| T-11-01 (Tampering — archive.tell() extra_fields) | MITIGATED — np.clip() applied to layout_coverage and space_saving in tell() |
| T-11-02 (DoS — CappedBOPEmitter) | MITIGATED — history_cap ge=10 validated in constructor; _trim_dataset() enforced on every tell() |
| T-11-03 (Info Disclosure — archive.data()) | ACCEPTED — internal engine state, not user-facing |

## Next Phase Readiness

- Plan 11-02 (CQD metric): archive.data() now returns layout_coverage + space_saving per elite — CQD can use objective field directly
- Plan 11-03 (Pareto-Front + Pareto-Slider): extra_fields in archive.data() provide the two Pareto objectives (layout_coverage + space_saving) needed for 2D Pareto front extraction via pymoo
- No blockers

## Self-Check

Files created/exist:
- `packages/engine/src/aerocloud/outer_loop/bop_emitter.py` — FOUND
- `packages/engine/tests/qd/test_bop_emitter.py` — FOUND

Commits exist:
- `59e2fcc` test(11-01): add failing tests for CappedBOPEmitter — FOUND
- `0790078` feat(11-01): CappedBOPEmitter + extended ArchiveConfig — FOUND
- `5819f19` test(11-01): add failing tests for ArchiveWrapper BOP — FOUND
- `0573050` feat(11-01): ArchiveWrapper BOP upgrade + extra_fields — FOUND

## Self-Check: PASSED

---
*Phase: 11-outer-loop-v2*
*Completed: 2026-04-16*

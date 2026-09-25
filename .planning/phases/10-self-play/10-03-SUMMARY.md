---
phase: 10-self-play
plan: "03"
subsystem: optimizer
tags: [self-play, kl-divergence, monitoring, celery, map-elites, tdd, numpy, scipy]

# Dependency graph
requires:
  - phase: 10-self-play/10-01
    provides: "SelfPlayConfig, SelfPlayRunResult, SelfPlayEvent, ReplayLogger, Celery task stub"
  - phase: 10-self-play/10-02
    provides: "structure_aware_mutate, uniform_crossover, sample_parents, AdversarialReviewer"
  - phase: 09-outer-loop-v1
    provides: "OuterLoop, ArchiveWrapper, ArchivePersistence, QualityMetrics, QualityWeights"
provides:
  - "compute_kl_divergence: 4 marginal 1D histograms over [0,1] (NOT joint 4D histogramdd)"
  - "check_distribution_shift: KL > threshold -> True + structlog warning"
  - "SelfPlayLoop: full mutation/crossover -> evaluate -> adversarial review -> dominance -> tell"
  - "SelfPlayLoop.build_from_env(): wires archive + persistence + replay_logger from env"
  - "SelfPlayLoop.flush_and_finalize(): graceful SoftTimeLimitExceeded exit with partial results"
  - "self_play_nightly task: replaces stub with SelfPlayLoop.build_from_env().run()"
  - "17 unit tests green (9 monitoring + 8 loop)"
affects: [10-04, 10-05, 12-production-v1]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Marginal KL pattern: 4 independent np.histogram 1D per BD dimension, sum KL values (NOT histogramdd)"
    - "Strict dominance: fitness_new > baseline + margin (not >=); boundary 0.72>0.72=False"
    - "Reviewer injection: loop._reviewer is a real AdversarialReviewer instance set in __init__; tests replace it with MagicMock directly"
    - "build_from_env: top-level imports at module level (not inside classmethod) to satisfy ruff PLC0415"
    - "Placeholder evaluate_fn: module-level function with _solution prefix to satisfy ARG001"

key-files:
  created:
    - packages/engine/src/aerocloud/self_play/monitoring.py
    - packages/engine/src/aerocloud/self_play/loop.py
    - packages/engine/tests/self_play/unit/test_monitoring.py
    - packages/engine/tests/self_play/unit/test_loop.py
  modified:
    - apps/worker/src/aerocloud_worker/tasks/self_play.py

key-decisions:
  - "Marginal 1D histograms (not joint 4D): joint 4D on uniform gives KL~11.5 (false alarm); marginal gives KL~0.0 (correct)"
  - "Strict > dominance (D-08): 0.72 > 0.71+0.01=False; boundary test encodes this invariant"
  - "Reviewer stored as self._reviewer instance (not patching class): tests replace instance attribute directly"
  - "build_from_env imports at module top level: satisfies ruff PLC0415; _placeholder_evaluate_fn extracted to module scope for ARG001"
  - "First night KL=None (no prior histogram): first run has no previous descriptor histogram to compare against"

patterns-established:
  - "Pattern 7: KL monitoring = 4 marginal 1D histograms, eps smoothing, scipy.special.rel_entr, sum 4 values"
  - "Pattern 8: SelfPlayLoop reviewer test setup = replace loop._reviewer with MagicMock (not patch class)"

requirements-completed: [SP-04, SP-05, SP-07]

# Metrics
duration: 8min
completed: 2026-04-21
---

# Phase 10 Plan 03: SelfPlayLoop Orchestrator + Monitoring Summary

**SelfPlayLoop wrapping OuterLoop with mutation/review/dominance and KL distribution-shift monitoring, fully wired Celery nightly task**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-21T21:27:49Z
- **Completed:** 2026-04-21T21:35:55Z
- **Tasks:** 2
- **Files modified:** 5 (4 created + 1 modified)

## Accomplishments

- `compute_kl_divergence`: 4 marginal 1D histograms over [0,1] using `np.histogram` + `scipy.special.rel_entr`; eps=1e-8 smoothing; sums 4 per-dimension KL values. No-drift KL < 0.1, severe collapse KL > 0.5. CRITICAL: NOT joint 4D histogramdd (would give ~11.5 for identical uniform distributions).
- `check_distribution_shift`: strict KL > threshold comparison with structlog warning on alert.
- `SelfPlayLoop.__init__`: stores all dependencies, builds `AdversarialReviewer` from archive solutions.
- `SelfPlayLoop.single_iteration`: mutation (rng < ratio) or crossover path; evaluate; adversarial review; strict dominance check (STRICT >); archive.tell() on accept.
- `SelfPlayLoop.run(n)`: generates run_id, inserts replay record, loads previous histogram, runs n iterations, computes KL, stores histogram, finalizes run record.
- `SelfPlayLoop.flush_and_finalize`: graceful SoftTimeLimitExceeded exit preserving partial results.
- `SelfPlayLoop.build_from_env`: wires ArchiveWrapper + ArchivePersistence + ReplayLogger from `DATABASE_URL` env var; loads frozen baseline.
- `self_play_nightly` task: full wiring with `SelfPlayLoop.build_from_env().run()` + SoftTimeLimitExceeded handling.
- 17 unit tests green; mypy --strict 0 errors; ruff clean.

## Task Commits

Each task was committed atomically:

1. **Task 1: KL divergence distribution-shift monitor** - `d4d55af` (feat)
2. **Task 2: SelfPlayLoop orchestrator + wire Celery task** - `1067dea` (feat)

## Files Created/Modified

- `packages/engine/src/aerocloud/self_play/monitoring.py` — compute_kl_divergence (4 marginal 1D histograms), check_distribution_shift
- `packages/engine/src/aerocloud/self_play/loop.py` — SelfPlayLoop class with single_iteration, run, flush_and_finalize, build_from_env, _get_bin_id, _compute_kl_and_finalize
- `packages/engine/tests/self_play/unit/test_monitoring.py` — 9 unit tests (identical->0, no-drift<0.1, severe>0.5, output type, single-dim collapse, shift true/false, marginal-not-joint)
- `packages/engine/tests/self_play/unit/test_loop.py` — 8 unit tests (mutation path, crossover path, reviewer reject, dominance pass, boundary strict >, no baseline, run result, flush_and_finalize)
- `apps/worker/src/aerocloud_worker/tasks/self_play.py` — replaced stub with full SelfPlayLoop.build_from_env().run() + SoftTimeLimitExceeded handling

## Decisions Made

- **Marginal 1D histograms (not joint 4D):** Joint 4D `np.histogramdd` on two identical uniform distributions produces KL ~11.5 (false alarm). 4 independent 1D marginal histograms correctly produce KL ~0.0 for no-drift case. This was the key research correction from 10-RESEARCH.md Pattern 6.
- **Strict > dominance (D-08):** The boundary case `0.72 > 0.71 + 0.01 = False` is encoded in `test_single_iteration_dominance_fails_at_boundary`. Uses `not (fitness_new > threshold)` (not `<=`) to make the intent explicit.
- **Reviewer instance replacement in tests:** `loop._reviewer` is built in `__init__` with a real `AdversarialReviewer`. Patching `aerocloud.self_play.loop.AdversarialReviewer` class has no effect on an already-constructed instance. Tests must replace `loop._reviewer` with a `MagicMock()` directly after construction.
- **Module-level imports in build_from_env:** Ruff PLC0415 forbids imports inside methods. Moved `os`, `ArchiveWrapper`, `ArchiveConfig`, `QualityWeights`, `ArchivePersistence`, `ReplayLogger` to module top-level imports.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed TDD reviewer mock: patching class had no effect on existing instance**
- **Found during:** Task 2 (TDD Green phase, test 3 failure)
- **Issue:** Tests patched `aerocloud.self_play.loop.AdversarialReviewer` class but `loop._reviewer` was already a real `AdversarialReviewer` instance built in `__init__`. The class patch did not affect the existing instance, so the real reviewer ran (causing OOD rejection instead of the mocked "degenerate_layout" rejection).
- **Fix:** Changed all tests to replace `loop._reviewer` directly with `MagicMock()` after `SelfPlayLoop(...)` construction. Added `_force_rng()` helper and `_make_loop()` that pre-installs a mock reviewer.
- **Files modified:** `packages/engine/tests/self_play/unit/test_loop.py`
- **Verification:** All 8 tests green
- **Committed in:** `1067dea`

**2. [Rule 1 - Bug] Fixed ruff PLC0415 (imports inside classmethod) + ERA001 (section headers)**
- **Found during:** Task 2 (post-green ruff check)
- **Issue:** `build_from_env` had local imports (`import os`, `from aerocloud...`); section comment headers like `# Public: single_iteration` were flagged as ERA001 (commented-out code); long lines (E501); `solution_flat` unused (B007); `solution` arg unused in placeholder (ARG001); `timezone.utc` deprecated (UP017).
- **Fix:** Moved all imports to module top-level; removed section comment headers; split long f-string reject_reason; renamed `solution_flat` to `_solution_flat`; extracted `_placeholder_evaluate_fn` to module scope with `_solution` parameter; used `datetime.UTC` alias.
- **Files modified:** `packages/engine/src/aerocloud/self_play/loop.py`
- **Verification:** `ruff check` clean, `mypy --strict` 0 errors
- **Committed in:** `1067dea`

---

**Total deviations:** 2 auto-fixed (Rule 1 bug in test approach, Rule 1 ruff compliance issues)
**Impact on plan:** No scope changes. Core behavior identical; only test infrastructure and code style corrected.

## Known Stubs

- `SelfPlayLoop.single_iteration`: `measures = np.array([[0.5, 0.5, 0.5, 0.5]])` is a placeholder BD for `archive.tell()`. In production the real BD from `evaluate_fn` return value (`_bd`) would be used. This is a known simplification — the archive stores the solution at a fixed placeholder bin. Wiring real BD measures to `tell()` is a Plan 04 (integration) responsibility.
- `SelfPlayLoop.build_from_env`: `_placeholder_evaluate_fn` returns static metrics. Real InnerLoop injection happens via dependency injection in production (Phase 12).

## Threat Flags

No new threat surface beyond what was analyzed in the plan's threat model.

Threat mitigations confirmed:
- T-10-07 (DoS): `soft_time_limit=28800` + `time_limit=28900` in Celery task decorator; `SoftTimeLimitExceeded` handler calls `flush_and_finalize`.
- T-10-08 (Tampering): Strict `>` dominance in `single_iteration`; boundary test `test_single_iteration_dominance_fails_at_boundary` verifies `0.72 > 0.72 = False`.
- T-10-09 (Repudiation): Both accepted and rejected events passed to `replay_logger.insert_event()` in `run()`.

## Self-Check: PASSED

Files created:
- `packages/engine/src/aerocloud/self_play/monitoring.py` — FOUND
- `packages/engine/src/aerocloud/self_play/loop.py` — FOUND
- `packages/engine/tests/self_play/unit/test_monitoring.py` — FOUND
- `packages/engine/tests/self_play/unit/test_loop.py` — FOUND

Commits:
- `d4d55af` — FOUND (feat(10-03): KL divergence distribution-shift monitor)
- `1067dea` — FOUND (feat(10-03): SelfPlayLoop orchestrator + wired Celery task)

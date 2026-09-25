---
phase: 10-self-play
plan: "02"
subsystem: infra
tags: [numpy, mutation, crossover, self-play, adversarial-reviewer, map-elites, tdd]

# Dependency graph
requires:
  - phase: 10-self-play/10-01
    provides: "SelfPlayConfig (sigma_xy, sigma_scale, sigma_theta, crossover_p), AeroCloudBase frozen model"
  - phase: 09-outer-loop-v1
    provides: "QualityMetrics, QualityWeights, combined_fitness, ArchiveWrapper.data() schema"
provides:
  - "structure_aware_mutate: reshape to (N,4), per-column Gaussian noise [sigma_xy, sigma_xy, sigma_scale, sigma_theta]"
  - "uniform_crossover: per-element np.where(mask, parent_a, parent_b) with configurable p"
  - "sample_parents: uniform random from archive_data['solution'] via rng.integers"
  - "AdversarialReviewer: 4-rule reward-hacking detection with priority order (degenerate -> OOD -> gaming -> hacking)"
  - "18 unit tests green (9 mutation + 9 reviewer); mypy --strict 0 errors; ruff clean"
affects: [10-03, 10-04, 10-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Structure-aware mutation: flat (dim,) -> reshape (N,4) -> per-column sigma broadcast -> flatten back"
    - "AdversarialReviewer rule priority: cheapest/critical first (degenerate_layout < OOD < gaming < reward_hacking)"
    - "Archive z-score OOD check: |solution - archive_mean| / (archive_std + 1e-8) > 3.0"
    - "TDD reviewer test setup: arithmetic-verified metric values ensure correct rule isolation"

key-files:
  created:
    - packages/engine/src/aerocloud/self_play/mutation.py
    - packages/engine/src/aerocloud/self_play/reviewer.py
    - packages/engine/tests/self_play/unit/test_mutation.py
    - packages/engine/tests/self_play/unit/test_reviewer.py
  modified: []

key-decisions:
  - "Rule priority order: degenerate_layout (Rule 3) -> OOD (Rule 2) -> gaming (Rule 4) -> reward_hacking (Rule 1) — cheapest checks first, most critical violations caught first per D-10"
  - "archive_std uses +1e-8 epsilon in __init__ to prevent divide-by-zero on uniform archive dimensions"
  - "sample_parents uses rng.integers(0, n_elites, size=2) — may return same index twice when n_elites=1 (correct behavior)"
  - "Test arithmetic for reward-hacking: must ensure combined_new > combined_baseline explicitly (equal-weight arithmetic verified per test)"

patterns-established:
  - "Pattern 5: AdversarialReviewer — instantiate with archive mean/std, call review() per candidate, returns (bool, str)"
  - "Pattern 6: TDD reviewer tests — verify arithmetic in docstring comment, use borderline values to isolate each rule"

requirements-completed: [SP-02, SP-03, SP-06]

# Metrics
duration: 20min
completed: 2026-04-21
---

# Phase 10 Plan 02: Mutation Operators + Adversarial Reviewer Summary

**Gaussian/crossover mutation operators + 4-rule adversarial reviewer for MAP-Elites self-play candidate validation**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-21T21:14:56Z
- **Completed:** 2026-04-21T21:19:44Z
- **Tasks:** 2
- **Files modified:** 4 (all created)

## Accomplishments

- `structure_aware_mutate` reshapes flat solution to (N,4) and applies per-column Gaussian noise using [sigma_xy, sigma_xy, sigma_scale, sigma_theta] from SelfPlayConfig; deterministic with seeded Generator
- `uniform_crossover` selects per-element from parent_a/parent_b via `np.where(mask, parent_a, parent_b)` with configurable p; p=0.0 returns parent_b entirely, p=1.0 returns parent_a entirely
- `sample_parents` does uniform random selection from `archive_data["solution"]` via `rng.integers(0, n_elites, size=2)`; correctly returns same elite twice when n_elites=1
- `AdversarialReviewer` implements all 4 rules in priority order: degenerate_layout (LC < 0.1) → OOD parameters (z_score > 3.0) → gaming_aspect_ratio (AR > 50% of combined) → reward_hacking (combined up + >=2 metrics down)
- 18 unit tests green; mypy --strict 0 errors on both source files; ruff clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Mutation operators — Gaussian + crossover + Monte-Carlo sampling** - `5960574` (feat)
2. **Task 2: AdversarialReviewer — rule-based reward-hacking detection** - `268785e` (feat)

## Files Created/Modified

- `packages/engine/src/aerocloud/self_play/mutation.py` — structure_aware_mutate, uniform_crossover, sample_parents (pure functions, O(N), typed)
- `packages/engine/src/aerocloud/self_play/reviewer.py` — AdversarialReviewer class with 4-rule evaluation, archive z-score OOD detection
- `packages/engine/tests/self_play/unit/test_mutation.py` — 9 unit tests covering shape, determinism, per-column sigma, crossover edge cases, single-elite sampling
- `packages/engine/tests/self_play/unit/test_reviewer.py` — 9 unit tests covering accept, degenerate, OOD, gaming, reward_hacking, baseline skipping, rule priority, borderline LC, exact-2 decrease

## Decisions Made

- Rule priority order (degenerate -> OOD -> gaming -> reward_hacking) follows cheapest/most-critical-first principle per D-10
- `archive_std + 1e-8` epsilon prevents divide-by-zero on archive dimensions with zero variance
- `rng.integers(0, n_elites, size=2)` may return duplicate indices when n_elites=1; this is correct behavior — same elite returned twice per plan spec

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_mutation.py: dict type annotation in sample_parents**
- **Found during:** Task 1 (mypy --strict post-green check)
- **Issue:** `archive_data: dict` without type args caused mypy `type-arg` error
- **Fix:** Changed parameter type to `dict[str, np.ndarray]`
- **Files modified:** `packages/engine/src/aerocloud/self_play/mutation.py`
- **Verification:** mypy --strict 0 errors
- **Committed in:** `77d249b` (Task 1 commit)

**2. [Rule 1 - Bug] Fixed test_reject_gaming_aspect_ratio: layout_coverage=0.0 triggered Rule 3 before Rule 4**
- **Found during:** Task 2 (TDD green phase, test 4 failure)
- **Issue:** Test set layout_coverage=0.0 which triggers degenerate_layout (Rule 3) before gaming_aspect_ratio (Rule 4), making the assertion fail since Rule 3 fires first. This is actually correct behavior — but the test intended to isolate Rule 4.
- **Fix:** Changed layout_coverage from 0.0 to 0.1 (borderline-accepted by Rule 3, strict < not <=) so Rule 4 is reached. Added arithmetic comment verifying AR ratio ≈ 90.9% > 50%.
- **Files modified:** `packages/engine/tests/self_play/unit/test_reviewer.py`
- **Verification:** Test passes, Rule 4 correctly triggered
- **Committed in:** `073c85e` (Task 2 commit)

**3. [Rule 1 - Bug] Fixed test_reject_reward_hacking + test_exactly_2_metrics_decrease_triggers: combined_new did not exceed combined_baseline**
- **Found during:** Task 2 (TDD green phase, tests 5 and 9 failure)
- **Issue:** Initial metric values produced combined_new < combined_baseline (e.g., (1/7)*(0.1+0.1+0.1+0.5+1.0+0.5+0.5) = 0.4 < 0.5), so Rule 1 never fired.
- **Fix:** Test 5: used 4 metrics at 1.0 and 3 at 0.1 → combined_new ≈ 0.614 > 0.5. Test 9: used 5 metrics at 1.0 and 2 at 0.1 → combined_new ≈ 0.743 > 0.5. Added arithmetic verification in test docstrings.
- **Files modified:** `packages/engine/tests/self_play/unit/test_reviewer.py`
- **Verification:** Both tests pass; reward_hacking correctly detected
- **Committed in:** `073c85e` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (3 Rule 1 bugs — 1 in source, 2 in tests)
**Impact on plan:** All fixes necessary for mypy strict compliance and correct test isolation. No scope creep. Core implementations unchanged.

## Issues Encountered

- Test arithmetic for reward_hacking rules requires careful manual calculation of combined_fitness with equal weights (1/7 each) to ensure combined_new > combined_baseline. Added inline arithmetic comments to each affected test.

## Known Stubs

None — both mutation.py and reviewer.py are fully implemented with no stubs or placeholders.

## Threat Flags

No new threat surface beyond what was analyzed in the plan's threat model (T-10-05, T-10-06). Both mitigations confirmed:
- T-10-05: No bounds clamping in mutation.py; archive tell() handles clamping (existing)
- T-10-06: mutation is O(N); N bounded by max_words * 4 = 800

## Next Phase Readiness

- Plan 03 (SelfPlayLoop core) can import `structure_aware_mutate`, `uniform_crossover`, `sample_parents` from `aerocloud.self_play.mutation`
- Plan 03 can import `AdversarialReviewer` from `aerocloud.self_play.reviewer`
- Plan 04 (integration tests) can validate the >5% rejection rate criterion (D-12) using AdversarialReviewer against real archive data

---
*Phase: 10-self-play*
*Completed: 2026-04-21*

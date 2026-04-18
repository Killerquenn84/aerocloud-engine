---
phase: 08-semantic-vector-space
plan: 03
subsystem: nlp
tags: [sinkhorn, optimal-transport, POT, adaptive-epsilon, hypothesis, doubly-stochastic, pydantic]

# Dependency graph
requires:
  - phase: 08-01
    provides: "TransportPlan Pydantic model, SemanticError hierarchy, SinkhornNonConvergenceError, config (sinkhorn_eps_init, sinkhorn_max_iter)"
  - phase: 08-02
    provides: "cosine_similarity_matrix() returning (N,N) float32 cost matrix for transport input"

provides:
  - "compute_transport(cost_matrix, eps_init, max_iter) -> TransportPlan with (N,N) doubly stochastic matrix"
  - "Adaptive epsilon: halves if niter<10, doubles if niter>500, clamped to [1e-4, 1.0]"
  - "Log-space Sinkhorn via ot.sinkhorn(method='sinkhorn_log') — no NaN on degenerate inputs"
  - "Hypothesis property test: doubly stochastic invariant for N in [2,20], 50 examples"
  - "compute_transport exported from aerocloud.semantic.__init__"

affects:
  - "08-04-semantic-placement (consumes compute_transport output TransportPlan)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Log-space Sinkhorn: ot.sinkhorn(..., method='sinkhorn_log') avoids underflow on degenerate distributions"
    - "Adaptive epsilon with module-level thresholds: _FAST_CONVERGE_THRESHOLD=10, _SLOW_CONVERGE_THRESHOLD=500"
    - "Epsilon clamped to [_EPS_MIN=1e-4, _EPS_MAX=1.0] before Sinkhorn call, then adapted from clamped value"
    - "TransportPlan.eps_used carries the adapted epsilon for warmup reuse by downstream callers"
    - "TDD RED commit (test(08-03)) before GREEN implementation commit (feat(08-03))"

key-files:
  created:
    - "packages/engine/src/aerocloud/semantic/transport.py"
    - "packages/engine/tests/semantic/unit/test_transport.py"
    - "packages/engine/tests/semantic/property/__init__.py"
    - "packages/engine/tests/semantic/property/test_transport_hypothesis.py"
  modified:
    - "packages/engine/src/aerocloud/semantic/__init__.py (added compute_transport import and __all__ entry)"

key-decisions:
  - "ot.sinkhorn method=sinkhorn_log chosen over sinkhorn_stabilized: log-space arithmetic is POT's recommended approach for degenerate distributions (D-07)"
  - "eps_used in TransportPlan carries the ADAPTED epsilon, not the input eps: downstream callers (08-04 warm-start) can reuse it without re-tuning"
  - "Adaptation thresholds (10 / 500) match plan spec D-09; module-level constants make them grep-able and testable"
  - "Unused type: ignore comments removed from ot import — POT has stubs available in this environment"

# Metrics
duration: 4min
completed: "2026-04-18"
---

# Phase 8 Plan 03: Sinkhorn-Knopp Optimal Transport Summary

**Log-space Sinkhorn-Knopp with adaptive epsilon regularization via POT library, producing doubly stochastic (N,N) TransportPlan for word-to-canvas-position mapping**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-04-18T04:22:00Z
- **Completed:** 2026-04-18T04:29:40Z
- **Tasks:** 1 (TDD: RED commit + GREEN commit)
- **Files modified:** 5 (4 created, 1 modified)

## Accomplishments

- `compute_transport()` returns a `TransportPlan` with `(N, N)` doubly stochastic transport matrix via `ot.sinkhorn(method='sinkhorn_log')` for numerical stability on degenerate distributions
- Uniform marginals `a = b = ones(N)/N` implement the word-to-position 1:1 mapping prior (D-08)
- Adaptive epsilon (D-09): halves when Sinkhorn converges in < 10 iterations, doubles when > 500 iterations; initial eps clamped to `[1e-4, 1.0]` before call; adapted eps returned in `TransportPlan.eps_used`
- `SinkhornNonConvergenceError` raised when output contains NaN; error message includes eps + niter only (T-08-06 — no user data leakage)
- `compute_transport` added to `aerocloud.semantic.__init__` exports
- 13 tests green: 12 unit tests (shape, marginals, non-negative mass, degenerate input, adaptive eps halving/doubling, clamping) + 1 hypothesis property test (50 examples, N in [2, 20])
- mypy --strict 0 errors

## Task Commits

TDD workflow — two commits:

1. **RED — failing tests (import error on missing transport module)** - `fa02f20` (test(08-03))
2. **GREEN — implementation** - `8c1ab1b` (feat(08-03))

## Files Created/Modified

- `packages/engine/src/aerocloud/semantic/transport.py` - Sinkhorn-Knopp transport implementation with adaptive epsilon
- `packages/engine/src/aerocloud/semantic/__init__.py` - Added `compute_transport` import and `__all__` entry
- `packages/engine/tests/semantic/unit/test_transport.py` - 12 unit tests covering all behaviors
- `packages/engine/tests/semantic/property/__init__.py` - Package marker for property test directory
- `packages/engine/tests/semantic/property/test_transport_hypothesis.py` - Hypothesis property test for doubly stochastic invariant

## Decisions Made

- `ot.sinkhorn(method='sinkhorn_log')` chosen: POT's log-space implementation avoids underflow on near-degenerate distributions (identity cost, zero-variance cost matrices)
- `TransportPlan.eps_used` carries the ADAPTED epsilon (not the input `eps_init`): the 08-04 semantic placement warm-start can reuse this for iterative refinement without re-tuning
- Module-level constants `_EPS_MIN`, `_EPS_MAX`, `_FAST_CONVERGE_THRESHOLD`, `_SLOW_CONVERGE_THRESHOLD` make thresholds grep-able and testable vs. inline magic numbers
- `type: ignore[import-untyped]` removed after confirming POT has stubs in this environment (mypy passes without it)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused `type: ignore` annotations**
- **Found during:** Task 1 (mypy --strict check after GREEN implementation)
- **Issue:** Plan template included `# type: ignore[import-untyped]` on the `ot` import and `# type: ignore[call-overload]` on `ot.sinkhorn` call; both caused `unused-ignore` mypy errors because POT has type stubs available in this environment
- **Fix:** Removed both `type: ignore` comments; mypy passes cleanly with 0 errors
- **Files modified:** `packages/engine/src/aerocloud/semantic/transport.py`
- **Commit:** `8c1ab1b` (GREEN commit, inline fix)

None beyond the type annotation cleanup above. Plan executed as designed.

## Runtime Warnings (Expected)

Two POT runtime warnings appear in tests — these are expected and acceptable:
1. `UserWarning: Sinkhorn did not converge` — appears for tiny epsilon (1e-5 clamped to 1e-4) and difficult cost matrices; Sinkhorn still returns a valid (non-NaN) result in these cases
2. `RuntimeWarning: overflow encountered in exp` — POT internal log-domain arithmetic overflow on extreme inputs; result is still numerically valid after log-sum-exp stabilization

Both warnings indicate tests are exercising edge-case epsilon values as required by the plan (Tests 7 and 8). No action needed.

## Known Stubs

None — `compute_transport()` is fully implemented. `TransportPlan` is returned with real computed values from Sinkhorn.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes beyond what the plan's threat model covers. T-08-05 (DoS via max_iter cap) and T-08-06 (error message contains only eps+niter) are both implemented and tested.

## Next Phase Readiness

- `compute_transport()` is ready for 08-04 (semantic warm-start / placement integration)
- `TransportPlan.transport_matrix` is `(N, N)` doubly stochastic — 08-04 can directly use `argmax` along columns to get word-to-position assignment
- `TransportPlan.eps_used` supports adaptive warmup for iterative refinement in 08-04
- Property test database will support regression detection when 08-04 integrates the full pipeline

## Self-Check: PASSED

- `packages/engine/src/aerocloud/semantic/transport.py` — FOUND
- `packages/engine/tests/semantic/unit/test_transport.py` — FOUND
- `packages/engine/tests/semantic/property/__init__.py` — FOUND
- `packages/engine/tests/semantic/property/test_transport_hypothesis.py` — FOUND
- `packages/engine/src/aerocloud/semantic/__init__.py` (modified, compute_transport exported) — FOUND
- Commit `fa02f20` (RED) — FOUND
- Commit `8c1ab1b` (GREEN) — FOUND
- 13 tests pass (12 unit + 1 hypothesis) — VERIFIED

---
*Phase: 08-semantic-vector-space*
*Completed: 2026-04-18*

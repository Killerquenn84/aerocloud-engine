# Phase 6 Inner Loop-v1 — 3-KI Consensus

**Date:** 2026-04-14
**Ratified by:** Jens (Architekt)

## Review Verdicts

| Reviewer | Initial Verdict | After Fixes |
|----------|----------------|-------------|
| Claude | APPROVED (9 low-severity) | APPROVED |
| Codex (gpt-5.4) | BLOCKED (6 must-fix) | APPROVED |
| Gemini (2.5 Pro) | BLOCKED (4 must-fix) | APPROVED |

## Findings Disposition

### Fixed in Phase 6 (commit b252c45)

| # | Finding | Source | Fix |
|---|---------|--------|-----|
| F-1 | No outside-penalty in L_wmse | Gemini+Codex | Added `outside_penalty = mean((clamp(-sdf,0) * density)^2)` |
| F-2 | Forced-square canvas distortion | Codex | Aspect ratio preserved via proportional scaling |
| F-4 | OptimizationResult.params alias | Codex | `.detach().clone()` |
| F-5 | sprites/params count mismatch | Gemini+Codex | ValueError guard in compute_additive_density |
| F-6 | ref_weights shape mismatch | Gemini+Codex | ValueError guard in InnerLoop.__init__ |
| F-7 | No minimum resolution guard | Gemini | `_MIN_RESOLUTION = 8` enforced in schedule |
| F-8 | Convergence scale formula | Codex | `max(abs(max_val), abs(min_val), 1e-8)` |

### Deferred (3-KI unanimous)

| # | Finding | Defer To | Rationale |
|---|---------|----------|-----------|
| F-3 | Double forward pass (~2x overhead) | Phase 7/12 | Performance only; requires renderer API change (dual-mode output). Phase 7 extends renderer anyway. |
| F-9 | Thread-safety (shared renderer) | Phase 12 | v1 Celery worker is single-threaded (concurrency=1). Document as Known Limit. |
| F-10 | Private coupling in compute_additive_density | Phase 7 | Resolved automatically when F-3 is fixed (function deleted). |

## Anti-Sycophancy Self-Check

- Claude initially deferred F-1. Codex + Gemini provided concrete counter-argument: L_overlap only constrains sprite-to-sprite overlap, not silhouette boundary. Claude accepted override (2:1 vote).
- F-3 remained 1:2 (only Gemini wanted fix-now). Jens ratified defer.
- All deferrals have concrete Phase 7/12 mitigation paths documented.

## Test Results After Fixes

- 58/58 optimizer tests green
- mypy --strict: 0 errors
- ruff check + format: clean
- Prior phase tests (geometry + renderer): no regressions

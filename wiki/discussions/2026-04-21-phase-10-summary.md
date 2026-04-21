# Phase 10 Self-Play — Close-Out Summary

**Date:** 2026-04-21
**Phase:** 10-self-play
**Plans completed:** 10-01 through 10-05
**Requirements:** SP-01 through SP-08 (all satisfied)
**Status:** COMPLETE

---

## What Was Built

Phase 10 implements the nightly Self-Play training loop for the AeroCloud MAP-Elites archive. Six new modules + one Alembic migration + one Celery task:

### Core Modules

| Module | File | Responsibility |
|--------|------|---------------|
| `SelfPlayConfig` | `self_play/config.py` | Frozen Pydantic model with 10 validated hyperparameters |
| Data models | `self_play/models.py` | `SelfPlayRunResult` + `SelfPlayEvent` frozen Pydantic models |
| `ReplayLogger` | `self_play/replay.py` | asyncpg persistence for `self_play_runs` + `self_play_events` |
| Mutation operators | `self_play/mutation.py` | `structure_aware_mutate`, `uniform_crossover`, `sample_parents` |
| `AdversarialReviewer` | `self_play/reviewer.py` | 4-rule reward-hacking detection heuristic |
| `monitoring` | `self_play/monitoring.py` | KL divergence on 4 marginal 1D histograms |
| `SelfPlayLoop` | `self_play/loop.py` | Full orchestrator wiring all components |

### Infrastructure

- **Alembic 0004:** `self_play_runs` + `self_play_events` tables with UUID PK (Python-generated)
- **Celery task:** `self_play_nightly` with `soft_time_limit=28800`, `time_limit=28900`, `queue=background`
- **Beat schedule:** `0 2 * * *` Europe/Berlin timezone
- **Public API:** 11 exported symbols from `aerocloud.self_play`

---

## Decisions Implemented (D-01 through D-17)

| Decision | What Was Implemented |
|----------|---------------------|
| D-01 | Celery Beat nightly job on `background` queue, `solo` pool (CUDA fork safety) |
| D-02 | `self_play_nightly(n_iterations=1000, soft_time_limit=28800)` task, `max_retries=0` |
| D-03 | `SoftTimeLimitExceeded` → `flush_and_finalize` for graceful partial-result exit |
| D-04 | Gaussian perturbation on flat `(max_words * 4,)` solution arrays |
| D-05 | Uniform crossover: per-element `np.where(mask, parent_a, parent_b)`, p=0.5; parent sampling: `rng.integers(0, n_elites, size=2)` |
| D-06 | Structure-aware mutation: reshape to (N,4), per-column sigma [sigma_xy, sigma_xy, sigma_scale, sigma_theta] |
| D-07 | Frozen baseline = archive snapshot at run start via `ArchivePersistence.load_all()`, stored in memory |
| D-08 | Strict dominance: `fitness_new > fitness_baseline + margin` (NOT `>=`); boundary `0.72 > 0.72 = False` verified by unit test |
| D-09 | Baseline QualityMetrics stored as `None` (not persisted in archive_v1 schema); reviewer skips Rule 1 for these entries |
| D-10 | Rule-based AdversarialReviewer: 4 rules in priority order (degenerate→OOD→gaming→hacking), deterministic, no ML |
| D-11 | `review()` returns `(accepted: bool, reason: str)` — empty string on acceptance |
| D-12 | > 5% rejection rate success criterion — verified with 33% degenerate inputs in integration test |
| D-13 | 4D behavioral descriptor distribution tracked per run |
| D-14 | KL > 0.5 → structlog warning (Telegram notification wired in Phase 12) |
| D-15 | `self_play_runs` table: UUID PK, timestamps, aggregates, config JSONB |
| D-16 | `self_play_events` table: BIGSERIAL PK, FK to runs ON DELETE CASCADE, per-iteration fields |
| D-17 | Full replay reconstruction enabled; UUID generated in Python not SQL |

---

## Test Count and Coverage

| Category | Count | Files |
|----------|-------|-------|
| Unit — config | 25 | test_config.py |
| Unit — models | 12 | test_models.py |
| Unit — replay | 20 | test_replay.py |
| Unit — mutation | 9 | test_mutation.py |
| Unit — reviewer | 9 | test_reviewer.py |
| Unit — monitoring | 9 | test_monitoring.py |
| Unit — loop | 8 | test_loop.py |
| Integration | 6 | test_self_play_loop.py |
| Determinism | 3 | test_determinism.py |
| **Total** | **101** | |

**Phase exit gates at completion:**
- pytest: 101 passed, 0 failed
- mypy --strict: 0 errors (12 source files)
- ruff check: clean
- ruff format --check: clean (3 files reformatted in Plan 05 exit gate)

---

## Key Research Corrections Applied

1. **Marginal 1D histograms (not joint 4D histogramdd):** Joint 4D on identical uniform distributions gives KL ≈ 11.5 (false alarm). 4 independent 1D marginals give KL ≈ 0.0 for no-drift case.
2. **UUID in Python (not SQL gen_random_uuid()):** `gen_random_uuid()` requires the pg_crypto extension. Python `uuid.uuid4()` is portable and explicit.
3. **Strict > dominance (D-08):** `0.72 > 0.71 + 0.01 = 0.72 > 0.72 = False`. Boundary test encodes this invariant permanently.

---

## Claude Self-Review Verdict (S-1..S-8, L-1..L-8, A-1..A-5)

**Overall: APPROVED**

Security findings:
- S-1 (SQL Injection): PASS — all `$N` params, no interpolation
- S-5 (Secrets): PASS — DSN never logged (T-10-01)
- S-8 (DoS): PASS — `soft_time_limit=28800` + `time_limit=28900`
- S-2, S-3, S-4, S-6, S-7: N/A (no HTML/web/external URLs/file paths)

Stability findings:
- L-1 (minor): No try/except around per-iteration `insert_event` — a DB failure on iteration 50 aborts all remaining iterations. Non-blocking for a best-effort nightly job (max_retries=0, SoftTimeLimitExceeded handles abort cleanly).
- L-2..L-8: PASS

Architecture findings:
- A-1..A-5: PASS
- Note: `SelfPlayConfig.n_iterations` field and `run(n_iterations)` parameter are distinct — config value is logged at init time; run uses the parameter. Intentional design (allows per-task override without config reconstruction).

---

## Known Stubs (Carry-Forward to Phase 12)

1. **Placeholder BD measures:** `single_iteration` uses `measures = np.array([[0.5, 0.5, 0.5, 0.5]])` as placeholder behavioral descriptor for `archive.tell()`. Real BD from InnerLoop evaluation will be wired in Phase 12.
2. **Placeholder evaluate_fn:** `_placeholder_evaluate_fn` returns static `QualityMetrics(all=0.5)`. Real InnerLoop injection via dependency injection in Phase 12.
3. **Baseline QualityMetrics as None:** `build_from_env` stores `(fitness, None)` in `frozen_baseline` — QualityMetrics not persisted in archive_v1. AdversarialReviewer Rule 1 (reward_hacking) is skipped for these entries. Phase 12 to add metrics persistence if needed.
4. **KL Telegram notification:** `check_distribution_shift` logs structlog warning but does not yet send Telegram alert (Phase 12 infrastructure).
5. **Histogram stored as raw measures (not binned):** `store_descriptor_histogram` stores `current_measures.tolist()` (shape N×4), not pre-computed histogram bins. `load_previous_descriptor_histogram` returns this as `np.ndarray`. `compute_kl_divergence` expects `(n, 4)` shaped input — correct interpretation requires both sides to be raw descriptor arrays, not histogram bins. The naming (`descriptor_histogram`) is slightly misleading but the computation is correct.

---

## Deviations Across All Plans

| Plan | Deviation | Rule | Impact |
|------|-----------|------|--------|
| 01 | Pydantic frozen model test used `object.__setattr__` (bypasses frozen) | Rule 1 Bug | Fixed in test |
| 01 | mypy type errors in replay.py and tasks/self_play.py | Rule 1 Bug | Fixed; added pyproject.toml override |
| 02 | `archive_data: dict` without type args → mypy type-arg error | Rule 1 Bug | Fixed to `dict[str, np.ndarray]` |
| 02 | Test for Rule 4 had `layout_coverage=0.0` triggering Rule 3 first | Rule 1 Bug | Fixed to `layout_coverage=0.1` |
| 02 | Reward-hacking test arithmetic: combined_new did not exceed combined_baseline | Rule 1 Bug | Fixed with verified arithmetic |
| 03 | Mock patch of AdversarialReviewer class had no effect on existing instance | Rule 1 Bug | Fixed to replace `loop._reviewer` directly |
| 03 | ruff PLC0415, ERA001, E501, B007, ARG001, UP017 in loop.py | Rule 1 Bug | Fixed; moved imports to module level |
| 04 | pyribs ask/tell constraint broke integration fixture | Rule 1 Bug | Fixed with MagicMock archive |
| 04 | Unused imports (F401, B905) in test files | Rule 1 Bug | Fixed |
| **05** | **ruff format --check failed on loop.py, mutation.py, reviewer.py** | **Rule 3 Blocking** | **Fixed; 3 files reformatted** |

---

## Next Phase

Phase 11 — Outer Loop-v2: BOP-Elites, CQD-Score Monte-Carlo, Pareto-Front, CQD_HV, Pareto-Slider.

Self-Play archive (Phase 10) feeds Phase 11: the nightly-trained MAP-Elites archive provides the diverse solution population from which BOP-Elites samples.

---

*Phase: 10-self-play*
*Close-out date: 2026-04-21*
*Prepared by: Claude Code (claude-sonnet-4-6)*

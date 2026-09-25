# wiki/code/self-play-loop.md — SelfPlayLoop Orchestrator

**Phase:** 10-self-play
**Module:** `packages/engine/src/aerocloud/self_play/loop.py`
**Implements:** SelfPlayLoop — nightly self-play training orchestrator wrapping MAP-Elites archive with mutation, adversarial review, and frozen-baseline dominance checking.

---

## Overview

`SelfPlayLoop` is the top-level orchestrator for Phase 10 Self-Play training. It wires:
- `ArchiveWrapper` (archive data access + tell)
- `evaluate_fn` (injected fitness function — `_placeholder_evaluate_fn` in build_from_env)
- `ArchivePersistence` (frozen baseline loading + optional flush)
- `AdversarialReviewer` (rule-based reward-hacking detection, built from archive solutions)
- `ReplayLogger` (asyncpg persistence for replay tables)
- `SelfPlayConfig` (all hyperparameters)
- `np.random.Generator` (seeded, deterministic)
- Frozen baseline: `dict[str, tuple[float, QualityMetrics]]` loaded once at build time

The nightly evaluation pipeline per iteration:
```
archive.data() → sample parents → mutation OR crossover
→ evaluate_fn → compute fitness → lookup frozen baseline
→ AdversarialReviewer.review() → dominance check (STRICT >)
→ archive.tell() if accepted → replay_logger.insert_event()
```

---

## Type Alias

```python
EvaluateFn = Callable[[np.ndarray], tuple[QualityMetrics, Any, np.ndarray]]
```

The signature matches OuterLoop's `evaluate_fn`. Real InnerLoop injection happens via dependency injection in Phase 12.

---

## _placeholder_evaluate_fn

```python
def _placeholder_evaluate_fn(_solution: np.ndarray) -> tuple[QualityMetrics, Any, np.ndarray]:
```

Module-level placeholder used by `build_from_env`. Returns static `QualityMetrics(all=0.5)` and a zero 384-dim embedding. Leading underscore on `_solution` suppresses ARG001 (intentional unused arg).

---

## Class: SelfPlayLoop

```python
class SelfPlayLoop:
    def __init__(
        self,
        archive: Any,
        evaluate_fn: EvaluateFn,
        persistence: Any | None,
        quality_weights: QualityWeights,
        config: SelfPlayConfig,
        replay_logger: Any | None,
        rng: np.random.Generator,
        frozen_baseline: dict[str, tuple[float, QualityMetrics]] | None,
    ) -> None
```

`AdversarialReviewer` is built at `__init__` time from `archive.data()["solution"]`. Run counters (`_n_accepted`, `_n_rejected`) are reset in `run()` before each nightly invocation.

---

## Methods

### single_iteration(iteration: int) -> SelfPlayEvent

Execute one self-play iteration: mutate/crossover → evaluate → adversarial review → dominance → tell.

**Steps:**
1. Get `archive.data()["solution"]`
2. Choose operator: `rng.random() < mutation_ratio` → mutation path; else crossover
3. **Mutation path:** `sample_parents` (1 used) → `structure_aware_mutate`
4. **Crossover path:** `sample_parents` (both used) → `uniform_crossover`
5. `evaluate_fn(candidate)` → `QualityMetrics, _bd, _emb`
6. `fitness_new = metrics.combined_fitness(quality_weights)`
7. Lookup `frozen_baseline.get(bin_id)` → `baseline_fitness, metrics_baseline`
8. `self._reviewer.review(candidate, metrics_new, metrics_baseline)` → `(accepted, reason)`
9. If rejected: increment `_n_rejected`, return `SelfPlayEvent(accepted=False)`
10. Dominance check: `fitness_new > baseline_fitness + dominance_margin` (STRICT >, D-08)
    - Boundary: `0.72 > 0.71 + 0.01 = 0.72 > 0.72 = False` (verified by unit test)
11. If accepted: `archive.tell(objectives, measures=[0.5,0.5,0.5,0.5])`, increment `_n_accepted`

Returns: `SelfPlayEvent` (frozen Pydantic model).

**Known stub:** `measures = np.array([[0.5, 0.5, 0.5, 0.5]])` is a placeholder BD. Real BD from `evaluate_fn` return value `_bd` would be used in Phase 12.

### run(n_iterations: int) -> SelfPlayRunResult

Run self-play for `n_iterations`, logging every event.

**Steps:**
1. Generate `run_id = uuid.uuid4()`, record `started_at`
2. Reset `_n_accepted`, `_n_rejected` counters
3. `replay_logger.insert_run(run_id, config.model_dump())` if logger available
4. `replay_logger.load_previous_descriptor_histogram()` → `_prev_histogram`
5. Main loop: `single_iteration(i)` → `replay_logger.insert_event(run_id, event)`
6. `_compute_kl_and_finalize(n_done, "completed")`
7. Return `SelfPlayRunResult`

### flush_and_finalize(n_done: int, exit_reason: str = "soft_timeout") -> SelfPlayRunResult

Graceful shutdown after `SoftTimeLimitExceeded` (D-03). Calls `_compute_kl_and_finalize` then returns partial `SelfPlayRunResult` with the given `exit_reason`.

Called from Celery task `except SoftTimeLimitExceeded` block:
```python
n_done = loop._n_accepted + loop._n_rejected
result = loop.flush_and_finalize(n_done=n_done, exit_reason="soft_timeout")
```

### build_from_env() -> SelfPlayLoop (classmethod)

Factory that wires all dependencies from environment variables:
- `SELF_PLAY_MAX_WORDS` (default 200) → `ArchiveConfig.solution_dim`
- `DATABASE_URL` → asyncpg DSN for `ArchivePersistence` + `ReplayLogger`
- Frozen baseline loaded via `asyncio.run(persistence.load_all())`; QualityMetrics stored as `None` (not persisted in archive_v1)
- `evaluate_fn = _placeholder_evaluate_fn` (Phase 12 will inject real InnerLoop)

---

## Internal Helpers

### _get_bin_id(solution, archive_solutions) -> str

Computes a bin ID for a solution by finding the nearest archive elite via L2 distance.

Returns `f"bin_{nearest_idx}"`. This is a simplified mapping — production would use the GridArchive bin index from BD measures.

**Edge case:** Empty archive returns `"bin_0"`.

### _compute_kl_and_finalize(n_done, exit_reason) -> float | None

Consolidates KL divergence computation, histogram storage, and replay logger finalization:
1. `archive.data().get("measures", empty)` — current descriptor measures
2. If `_prev_histogram` exists and data available: `compute_kl_divergence()` + `check_distribution_shift()`
3. `replay_logger.store_descriptor_histogram(run_id, current_measures.tolist())`
4. `replay_logger.finalize_run(run_id, n_done, n_accepted, n_rejected, kl_divergence)`
5. Logs `self_play.loop.finalized`

Broad `except Exception` on `archive.data()` is defensive: ensures KL skip never crashes finalization.

---

## asyncio.run() Pattern

All async DB operations use `asyncio.run()` in a sync context — same pattern as `OuterLoop._flush_archive()`. Celery's `solo` pool ensures no existing event loop. Multiple `asyncio.run()` calls are sequential, not nested.

**Anti-pattern avoided:** No `asyncio.run()` inside another `asyncio.run()`. DB calls in the main iteration loop are sequential per-iteration.

---

## Design Decisions

| Decision | Detail |
|----------|--------|
| D-03 | `SoftTimeLimitExceeded` → `flush_and_finalize` for graceful exit |
| D-07 | Frozen baseline loaded once at build time from `ArchivePersistence.load_all()` |
| D-08 | Strict `>` dominance; boundary `0.72 > 0.72 = False` |
| D-09 | Baseline QualityMetrics stored as `None` (not in archive_v1 schema) — reviewer skips Rule 1 |

---

## Threat Register

| ID | Category | Status |
|----|----------|--------|
| T-10-07 | DoS — runaway loop | Mitigated: `soft_time_limit=28800` + `time_limit=28900` in Celery decorator |
| T-10-08 | Tampering — weak mutations enter archive | Mitigated: STRICT `>` dominance; boundary test verifies `0.72 > 0.72 = False` |
| T-10-09 | Repudiation — unreproducible runs | Mitigated: both accepted and rejected events logged to `self_play_events` |

---

## Tests

- `test_loop.py`: 8 unit tests (mutation path, crossover path, reviewer reject, dominance pass, boundary strict >, no baseline, run result, flush_and_finalize)
- `test_self_play_loop.py`: 6 integration tests (full run, rejection rate > 5%, dominance rejection, event count, KL=None first night, soft timeout)
- `test_determinism.py`: 3 determinism tests (same seed → identical events, different seeds differ, mutation deterministic)

---

*Module: packages/engine/src/aerocloud/self_play/loop.py*
*Phase: 10-self-play*
*Updated: 2026-04-21*

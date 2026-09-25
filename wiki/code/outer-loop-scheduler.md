# wiki/code/outer-loop-scheduler.md — OuterLoop Orchestrator

**Phase:** 09-outer-loop-v1
**Module:** `packages/engine/src/aerocloud/outer_loop/scheduler.py`
**Implements:** OuterLoop class — full MAP-Elites evaluation pipeline (D-15) wiring all Phase 9 components

---

## Overview

`OuterLoop` is the top-level orchestrator for Phase 9. It wires:
- `ArchiveWrapper` (ask/tell)
- `evaluate_fn` (injected fitness function)
- `ArchivePersistence` (PostgreSQL flush, optional)
- `NoveltyGaussianEmitter` (novelty scoring)
- `SaturationMonitor` (plateau detection)
- `QualityWeights` (combined fitness computation)

The evaluation pipeline per iteration (D-15):
```
ask() → evaluate_fn per solution → combined_fitness + BD → tell() → saturation.record()
→ optional flush_batch (every flush_every_n evals)
→ optional reeval_elites (every reeval_every_n evals)
```

---

## OuterLoopResult (Pydantic)

```python
class OuterLoopResult(AeroCloudBase):
    final_coverage: float        # archive cells filled [0, 1]
    num_elites: int              # total elites at run end
    best_fitness: float          # highest fitness observed
    total_evaluations: int       # total solutions evaluated
    reeval_results: list[ReEvalResult]  # last reeval pass
    saturation_plateaued: bool   # True if SaturationMonitor declared plateau
```

---

## Class: OuterLoop

```python
class OuterLoop:
    def __init__(
        self,
        archive: Any,                           # ArchiveWrapper
        evaluate_fn: EvaluateFn,               # (solution) -> (QualityMetrics, BD, emb_384)
        persistence: Any | None,               # ArchivePersistence or None
        novelty_emitter: NoveltyGaussianEmitter,
        saturation_monitor: SaturationMonitor,
        quality_weights: QualityWeights,
        flush_every_n: int = 100,
        reeval_every_n: int = 200,
    ) -> None
```

### EvaluateFn type

```python
EvaluateFn = Callable[[np.ndarray], tuple[QualityMetrics, BehaviorDescriptor, np.ndarray]]
```

The caller is responsible for wiring the full InnerLoop pipeline inside `evaluate_fn`:
`semantic_warm_start → DifferentiableRenderer → InnerLoop.optimize → compute_all_metrics → compute_descriptors`

Kept sync to avoid asyncio/Celery anti-pattern (CLAUDE.md constraint).

---

## Methods

### single_iteration() -> int

Execute one MAP-Elites ask/evaluate/tell cycle.

**Steps:**
1. `ask()` — get batch of candidates `(batch_size, solution_dim)`
2. For each solution: `evaluate_fn(solution)` → `QualityMetrics, BehaviorDescriptor, embedding`
3. Compute `objective = metrics.combined_fitness(quality_weights)` per solution
4. Build `measures` array `(batch_size, 4)` from BD scalars
5. `archive.tell(objectives, measures)` — update archive
6. `saturation_monitor.record(archive.coverage)`
7. `total_evaluations += batch_size`
8. If `total_evaluations % flush_every_n == 0` and persistence: `_flush_archive()`
9. If `total_evaluations % reeval_every_n == 0`: `_run_reeval()`
10. Log iteration stats

Returns: `batch_size` (number of solutions evaluated).

### run(n_iterations) -> OuterLoopResult

Run the full MAP-Elites loop for `n_iterations` iterations.

```python
result = outer_loop.run(n_iterations=500)
```

After all iterations, computes best_fitness from archive data (D-11 completion).

**T-09-11 note:** Unconditional final flush is NOT in `run()`. Callers needing guaranteed persistence of remaining elites must call `_flush_archive()` explicitly after `run()`.

Returns: `OuterLoopResult`.

---

## Internal Helpers

### _flush_archive() -> None

Builds `ArchiveFlushEntry` list from `archive.data()` and calls `persistence.flush_batch()` via `asyncio.run()`.

```
archive.data()
  → objectives + measures arrays
  → build ArchiveFlushEntry per row
  → asyncio.run(persistence.flush_batch(entries))
```

**Known stub:** `params_bytes=b"\x00"` placeholder — production callers must wire real `params_to_bytes(params_tensor)`. See F-01 in code review.

No-op if archive is empty or persistence is None.

### _run_reeval() -> None

Wraps sync `evaluate_fn` into async, calls `reeval_elites()` via `asyncio.run()`.

```python
async def _async_eval(solution) -> (float, measures):
    metrics, bd, _ = evaluate_fn(solution)
    return combined_fitness, measures_array

results = asyncio.run(reeval_elites(archive, _async_eval, top_n=10, drift_threshold=0.1))
self._last_reeval_results = results
```

---

## asyncio.run() Pattern

`_flush_archive()` and `_run_reeval()` both use `asyncio.run()` to call async functions from a sync context. This is intentional:

- `OuterLoop` is a sync orchestrator designed for Celery task boundary
- `asyncio.run()` creates a new event loop per call — correct for Celery (no existing loop)
- FastAPI async callers must spawn OuterLoop in a thread pool executor (Phase 12 concern)

---

## Determinism

`OuterLoop` is deterministic when:
1. `evaluate_fn` is deterministic (seeded InnerLoop)
2. `ArchiveWrapper` is initialized with fixed seed
3. numpy random state is seeded via `set_seed()` before `run()`

Verified by `tests/qd/test_determinism.py` — two runs with `seed=42` produce identical coverage and best_fitness.

---

## Threat Register

| ID | Category | Status |
|----|----------|--------|
| T-09-10 | Data loss (asyncio.run nesting) | Documented — Celery task boundary only |
| T-09-11 | Archive state loss on exit | Mitigated by periodic flush; callers handle final flush |

---

*Module: packages/engine/src/aerocloud/outer_loop/scheduler.py*
*Phase: 09-outer-loop-v1*
*Updated: 2026-04-18*

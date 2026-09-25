# Phase 9 Outer Loop-v1: Design Knowledge

**Phase:** 09-outer-loop-v1
**Completed:** 2026-04-18
**Plans:** 09-01 through 09-06 (6 plans, Wave 5 of Phase 9)
**Tests:** 149 qd tests green

---

## What Was Built

Phase 9 implements MAP-Elites Quality-Diversity for word cloud layout exploration. It builds on Phase 6 (InnerLoop) and Phase 8 (Semantic Vector Space) to produce an archive of diverse, high-quality word cloud layouts.

### Component Map

```
outer_loop/
├── errors.py       — Error hierarchy (4 exception types)
├── models.py       — Pydantic models (QualityMetrics, QualityWeights, ArchiveConfig,
│                     ReEvalResult, ArchiveFlushEntry, OuterLoopResult)
├── archive.py      — ArchiveWrapper: pyribs GridArchive + GaussianEmitter ask/tell
├── descriptors.py  — compute_descriptors(): 4D BD from post-optimization layout
├── metrics.py      — 7 quality metric functions (5 geometric + 2 semantic)
├── persistence.py  — ArchivePersistence: asyncpg flush_batch + load_all
├── emitter.py      — NoveltyGaussianEmitter, SaturationMonitor, reeval_elites
└── scheduler.py    — OuterLoop orchestrator: full evaluation pipeline
```

---

## Key Design Decisions

### GaussianEmitter, not MapElitesBaselineEmitter (D-03 correction)

**Decision:** Use pyribs `GaussianEmitter` with `x0=zeros(solution_dim)` as the baseline emitter.

**Why:** `MapElitesBaselineEmitter` does not exist in pyribs 0.10.0. The plan referenced a class that was renamed or merged. `GaussianEmitter` provides the same functionality (Gaussian perturbation around archive elites) and is the canonical baseline emitter in pyribs 0.10.0.

**Additional fix:** pyribs 0.10.0 `Scheduler.tell()` uses `objective=` (singular), not `objectives=` (plural). Found during GREEN phase of Plan 09-01.

### pyribs 0.10.0 API

Pinned version: `ribs>=0.10.0` in `[qd]` extras of `pyproject.toml`.

Key API differences from pyribs < 0.10.0:
- `GaussianEmitter` requires `x0` parameter (initial solution centre)
- `Scheduler.tell()` uses `objective=` singular
- `GridArchive.cells` for total capacity (not `.capacity` in older versions)

### GridArchive: 4D Behavior Grid

```
dims: [bins_per_dim, bins_per_dim, bins_per_dim, bins_per_dim]
ranges: [(0.0, 1.0)] * 4
axes: [shape_fidelity, rotation_ratio, symmetry, semantic_clustering]
```

Default: 10 bins/dim → 10,000 cells total. Configurable via `AeroCloudSettings.archive_bins_per_dim`.

### Novelty via BallTree k-NN (D-12)

sklearn `NearestNeighbors(algorithm="ball_tree", metric="euclidean")` for descriptor-space novelty computation.

Key design choices:
- BallTree built **once per batch** (not per solution) — anti-pattern avoidance
- Returns `float("inf")` when archive has fewer than k entries (everything novel)
- k=15 default (configurable via `AeroCloudSettings.novelty_k`)

### Saturation Monitor + Sigma Boost (D-13)

`SaturationMonitor` tracks coverage history with a sliding window. Plateau = coverage growth < 1% over `window` readings. When plateaued, `NoveltyGaussianEmitter` returns `base_sigma * sigma_boost` (default 2x boost).

**Known issue:** `is_plateaued` logs a warning on every check once plateau is declared (not just first occurrence). Minor log spam — deferred to Phase 10 cleanup.

### Distortion Formula Correction (Plan 09-02)

The plan's distortion formula `score = 1 - mean/max` was semantically inverted: it returns 0.0 for a perfectly proportional layout (mean == max). Corrected to Coefficient of Variation:

```
cv = std(ratios) / (mean(ratios) + eps)
score = 1 - clamp(cv, 0, 1)
```

CV = 0 for perfect proportionality (all ratios equal) → score = 1.0.

### asyncio.run() at Sync/Async Boundary

`OuterLoop` is a **synchronous** orchestrator (compatible with Celery task boundary per CLAUDE.md). Its persistence and reeval dependencies are async. `asyncio.run()` is used as the sync/async bridge in `_flush_archive()` and `_run_reeval()`.

**Constraint:** This pattern only works when no event loop is running. FastAPI async callers must use `loop.run_in_executor()` or `asyncio.get_event_loop().run_in_executor()` to run OuterLoop in a thread pool (Phase 12 concern).

### evaluate_fn Injection Pattern

```python
EvaluateFn = Callable[[np.ndarray], tuple[QualityMetrics, BehaviorDescriptor, np.ndarray]]
```

The caller wires the entire evaluation pipeline inside `evaluate_fn`. OuterLoop has no direct dependency on InnerLoop, DifferentiableRenderer, or semantic modules — it only depends on the result types. This keeps OuterLoop testable with mock functions and decoupled from GPU code.

### ON CONFLICT Fitness Guard (D-10)

```sql
ON CONFLICT (bin_id) DO UPDATE
    SET fitness = EXCLUDED.fitness, ...
    WHERE EXCLUDED.fitness > archive_v1.fitness
```

This implements the MAP-Elites "keep best" property at the database level. Concurrent flushes from multiple workers cannot corrupt the archive — each write only succeeds if it improves the stored fitness.

### Params Bytes Placeholder (Known Stub)

`_flush_archive()` in `scheduler.py` uses `params_bytes=b"\x00"` as a placeholder for the real safetensors-serialized params tensor. Production callers must construct `ArchiveFlushEntry` objects with real `params_to_bytes(params_tensor)` bytes. This stub is documented in 09-05-SUMMARY.md "Known Stubs" and is a Phase 12 integration task.

---

## Behavioral Descriptor Computation

`compute_descriptors()` in `descriptors.py`:

| Dimension | Formula | Notes |
|-----------|---------|-------|
| `shape_fidelity` | `lc_metric` directly | Per RESEARCH BD table: LC metric = shape fidelity |
| `rotation_ratio` | `mean(|theta| > pi/4)` | Fraction of words rotated beyond 45 degrees |
| `symmetry` | `1 - |mirrored_mean_x - mean_right_x| / canvas_w` | Horizontal reflection score |
| `semantic_clustering` | `1 - clamp(distortion)` | Inverted spatial/embedding distance ratio |

All dimensions clamped to [0.0, 1.0] before constructing BehaviorDescriptor.

---

## Test Coverage Summary

| Test File | Tests | Coverage |
|-----------|-------|---------|
| test_models.py | (from 09-01) | QualityMetrics, QualityWeights, ArchiveConfig, ReEvalResult |
| test_errors.py | (from 09-01) | OuterLoopError hierarchy |
| test_config.py | (from 09-01) | AeroCloudSettings archive fields |
| test_archive.py | (from 09-01) | ArchiveWrapper ask/tell, coverage, capacity |
| test_descriptors.py | (from 09-01) | compute_descriptors(), symmetry, semantic_clustering |
| test_metrics.py | 37 | All 7 metric functions + edge cases |
| test_persistence.py | 17 | flush_batch, load_all, params_to_bytes/bytes_to_params |
| test_emitter.py | 20 | compute_novelty, SaturationMonitor, NoveltyGaussianEmitter, reeval_elites |
| test_scheduler.py | 24 | single_iteration, run, flush, saturation, reeval |
| test_determinism.py | 2 | Seed-stable archive state |
| **Total** | **149** | All passing |

---

## Phase 10 Integration Path

`OuterLoop.run()` is ready for Phase 10 Self-Play training:

```python
def real_evaluate_fn(solution: np.ndarray) -> tuple[QualityMetrics, BehaviorDescriptor, np.ndarray]:
    # 1. semantic_warm_start(params=solution.reshape(max_words, 4), ...)
    # 2. DifferentiableRenderer(params_n4, sprites, device)
    # 3. result = InnerLoop.optimize(renderer, ...)
    # 4. metrics = compute_all_metrics(density, sdf_mask, ...)
    # 5. bd = compute_descriptors(result.params, lc_metric, ...)
    return metrics, bd, embedding

outer_loop = OuterLoop(
    archive=ArchiveWrapper(config),
    evaluate_fn=real_evaluate_fn,
    persistence=ArchivePersistence(dsn),
    ...
)
result = outer_loop.run(n_iterations=1000)
```

---

## Phase Exit Gate Results (2026-04-18)

| Gate | Result |
|------|--------|
| `pytest packages/engine/tests/ -q` | 149 passed, 0 failed |
| `mypy packages/engine/src/aerocloud/outer_loop/ --strict` | Success: no issues found in 9 source files |
| `ruff check packages/engine/src/aerocloud/outer_loop/` | All checks passed |
| `ruff format --check packages/engine/src/aerocloud/outer_loop/` | All files formatted (1 auto-fix applied to persistence.py) |
| Wiki pages for all modules | Created |
| 3-KI review: Claude APPROVED | PASS (see discussions/2026-04-18-phase-09-codereview.md) |

---

*Phase: 09-outer-loop-v1*
*Knowledge captured: 2026-04-18*

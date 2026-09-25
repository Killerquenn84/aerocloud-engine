---
phase: 09-outer-loop-v1
plan: "01"
subsystem: outer-loop
tags: [map-elites, pyribs, quality-diversity, behavioral-descriptors, archive]
dependency_graph:
  requires:
    - "08-semantic: BehaviorDescriptor model, BERT embeddings interface"
    - "06-inner-loop: OptimizationResult with params tensor"
  provides:
    - "ArchiveWrapper: pyribs GridArchive + GaussianEmitter ask/tell cycle"
    - "compute_descriptors(): 4D behavioral descriptor from post-optimization layout"
    - "QualityMetrics + QualityWeights: 7-metric composite fitness"
    - "OuterLoopError hierarchy"
    - "Settings archive fields: archive_bins_per_dim, novelty_k, flush_every_n, reeval_every_n"
  affects:
    - "09-02+: plans consuming ArchiveWrapper and compute_descriptors"
tech_stack:
  added:
    - "ribs==0.10.0 (pyribs) — GridArchive, GaussianEmitter, Scheduler"
    - "pymoo==0.6.1.6 — pulled in as qd extras dependency"
  patterns:
    - "pyribs ask/tell cycle via Scheduler (RoundRobin with single emitter)"
    - "AeroCloudBase frozen+strict+extra=forbid for all outer-loop models"
    - "np.clip for measure clamping (Pitfall 5, T-09-01)"
    - "n_words parameter to handle padded solution tensors (Pitfall 3)"
key_files:
  created:
    - "packages/engine/src/aerocloud/outer_loop/__init__.py"
    - "packages/engine/src/aerocloud/outer_loop/errors.py"
    - "packages/engine/src/aerocloud/outer_loop/models.py"
    - "packages/engine/src/aerocloud/outer_loop/archive.py"
    - "packages/engine/src/aerocloud/outer_loop/descriptors.py"
    - "packages/engine/tests/qd/__init__.py"
    - "packages/engine/tests/qd/conftest.py"
    - "packages/engine/tests/qd/test_models.py"
    - "packages/engine/tests/qd/test_errors.py"
    - "packages/engine/tests/qd/test_config.py"
    - "packages/engine/tests/qd/test_archive.py"
    - "packages/engine/tests/qd/test_descriptors.py"
  modified:
    - "packages/engine/src/aerocloud/config.py — added 7 archive/outer-loop Settings fields"
    - "packages/engine/pyproject.toml — ribs>=0.10.0 pinned in [qd] extras"
decisions:
  - "GaussianEmitter with x0=zeros (not MapElitesBaselineEmitter which does not exist in pyribs 0.10.0)"
  - "solution_dim = max_words * 4 per D-16 (flattened (N,4) params tensor)"
  - "Scheduler.tell() uses objective= (singular) not objectives= in pyribs 0.10.0"
  - "GaussianEmitter requires x0 parameter in pyribs 0.10.0 (not documented in PLAN)"
  - "Behavioral descriptor computation deferred to post-optimization (D-17)"
  - "shape_fidelity = LC metric directly (per RESEARCH BD computation table)"
metrics:
  duration_minutes: 11
  completed_date: "2026-04-18"
  tasks_completed: 2
  tasks_total: 2
  tests_added: 49
  files_created: 12
  files_modified: 2
---

# Phase 9 Plan 01: Outer Loop Scaffolding + pyribs Archive Wrapper Summary

**One-liner:** pyribs 0.10.0 GridArchive + GaussianEmitter wrapper with 4D behavioral descriptor computation and 7-metric quality model (49 tests green).

## What Was Built

The outer_loop Python package providing:

1. **Error hierarchy** (`errors.py`): `OuterLoopError`, `ArchiveSaturationError`, `EliteDriftError`, `SolutionDimMismatchError`.

2. **Pydantic models** (`models.py`):
   - `QualityWeights`: 7 unnormalized float weights (w_lc through w_distortion), all >= 0.
   - `QualityMetrics`: 7 quality metric fields bounded [0.0, 1.0] with `combined_fitness()` method.
   - `ArchiveConfig`: bins_per_dim, solution_dim (required), sigma, batch_size, max_words.
   - `ReEvalResult`: elite re-evaluation result with drift detection.

3. **Settings fields** (`config.py`): 7 new fields — archive_bins_per_dim (ge=2, le=50), archive_sigma, archive_batch_size, archive_max_words, novelty_k, flush_every_n, reeval_every_n.

4. **pyribs dependency** (`pyproject.toml`): Pinned ribs>=0.10.0 in [qd] extras, installed successfully.

5. **ArchiveWrapper** (`archive.py`): wraps GridArchive + GaussianEmitter + Scheduler. ask/tell cycle with np.clip measure clamping (Pitfall 5). solution_dim = max_words * 4 (D-16).

6. **compute_descriptors()** (`descriptors.py`): 4D behavioral descriptor from post-optimization layout:
   - shape_fidelity = lc_metric value (per RESEARCH BD table)
   - rotation_ratio = fraction of words with |theta| > pi/4
   - symmetry = horizontal reflection score via mirrored mean positions
   - semantic_clustering = inverted spatial/embedding distance distortion ratio

7. **Test infrastructure** (`tests/qd/`): conftest with 3 fixtures + 5 test modules with 49 tests total (all green).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] pyribs 0.10.0 GaussianEmitter requires x0 parameter**
- **Found during:** Task 2, GREEN phase — `ValueError: Either x0 or initial_solutions must be provided`
- **Issue:** PLAN and RESEARCH doc did not mention that pyribs 0.10.0 GaussianEmitter requires `x0` (initial solution centre)
- **Fix:** Added `x0=np.zeros(self._solution_dim)` — neutral zero vector (archive starts empty)
- **Files modified:** `packages/engine/src/aerocloud/outer_loop/archive.py`
- **Commit:** f82c7e7

**2. [Rule 1 - Bug] pyribs 0.10.0 Scheduler.tell() uses objective= not objectives=**
- **Found during:** Task 2, GREEN phase — `TypeError: Scheduler.tell() missing 1 required positional argument: 'objective'`
- **Issue:** PLAN used `objectives=` (plural) but pyribs API uses `objective=` (singular)
- **Fix:** Changed `self._scheduler.tell(objectives=..., ...)` to `self._scheduler.tell(objective=..., ...)`
- **Files modified:** `packages/engine/src/aerocloud/outer_loop/archive.py`
- **Commit:** f82c7e7

**3. [Rule 2 - Cleanup] ruff + mypy issues fixed inline**
- **Found during:** Final verification pass
- **Issues:** Unused import (F401), unsorted imports (I001), commented-out code (ERA001), unnecessary return assignments (RET504), Unicode characters in docstring (RUF002), unused type: ignore comments
- **Fix:** Applied all ruff/mypy fixes; mypy --strict clean; ruff clean
- **Files modified:** archive.py, descriptors.py, models.py
- **Commit:** 1b5f7b6

## Threat Surface Scan

No new security-relevant surface introduced:
- No network endpoints
- No auth paths
- No file access
- No schema changes (config fields only, no DB migration in this plan)

T-09-01 (measure clamping) mitigated via `np.clip` in `ArchiveWrapper.tell()`.
T-09-02 (solution_dim validation) partially mitigated: `solution_dim` computed from config, pyribs validates shape at tell() boundary.

## Self-Check: PASSED

Files exist:
- packages/engine/src/aerocloud/outer_loop/__init__.py: FOUND
- packages/engine/src/aerocloud/outer_loop/errors.py: FOUND
- packages/engine/src/aerocloud/outer_loop/models.py: FOUND
- packages/engine/src/aerocloud/outer_loop/archive.py: FOUND
- packages/engine/src/aerocloud/outer_loop/descriptors.py: FOUND
- packages/engine/tests/qd/ (5 test files): FOUND

Commits exist:
- 238c338: feat(09-01): scaffold outer_loop package
- f82c7e7: feat(09-01): GridArchive wrapper + GaussianEmitter + behavioral descriptor computation
- 1b5f7b6: refactor(09-01): fix ruff + mypy issues

Tests: 49 passed, 0 failed.

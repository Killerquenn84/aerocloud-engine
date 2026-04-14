---
phase: 06-inner-loop-v1
plan: "02"
subsystem: optimizer
tags: [inner-loop, coarse-to-fine, adam, gradient-clipping, convergence, tdd, integration-tests]
dependency_graph:
  requires:
    - "06-01 (compute_l_wmse, compute_l_overlap, compute_l_fidelity, compute_l_temporal, compute_total_loss, compute_additive_density, check_convergence, LossWeights, InnerLoopConfig, OptimizationResult)"
    - "05-renderer-v1 (DifferentiableRenderer.params, .forward(), ._sprites, ._device)"
  provides:
    - "InnerLoop class with optimize() -> OptimizationResult"
    - "_build_stage_schedule helper"
    - "_downsample_sdf helper"
  affects:
    - "Phase 9 MAP-Elites (consumes InnerLoop.optimize() API)"
tech_stack:
  added: []
  patterns:
    - "type: ignore[no-untyped-call] for torch.Tensor.backward() in strict mypy"
    - "Ruff SIM102: combined nested if into single if ... and ... for convergence check"
decisions:
  - "type: ignore[no-untyped-call] on l_total.backward() — torch stubs do not type Tensor.backward() in strict mypy"
  - "_build_stage_schedule filters out resolutions >= target (Assumption A2): [8,32,128] + target=16 -> [8,16]"
  - "Fresh Adam optimizer created per stage; params carry over from previous stage (warm-start)"
key_files:
  created:
    - packages/engine/src/aerocloud/optimizer/inner_loop.py
    - packages/engine/tests/optimizer/integration/__init__.py
    - packages/engine/tests/optimizer/integration/test_coarse_to_fine.py
  modified:
    - packages/engine/src/aerocloud/optimizer/__init__.py
metrics:
  duration_minutes: 4
  completed_date: "2026-04-14"
  tasks_completed: 1
  files_created: 3
  files_modified: 1
  tests_added: 5
---

# Phase 6 Plan 02: InnerLoop Coarse-to-Fine Pipeline Summary

**One-liner:** InnerLoop class orchestrating 4-part composite loss + Adam optimizer + gradient clipping + SDF-downsampled Coarse-to-Fine stages + rolling-window convergence detection — 5 integration tests, mypy strict clean, ruff clean.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 RED | 5 integration tests for InnerLoop (import error — InnerLoop DNE) | 5ec3ce1 | tests/optimizer/integration/* |
| 1 GREEN | InnerLoop class + __init__.py export | 143184e | src/aerocloud/optimizer/inner_loop.py + __init__.py |

## Verification Results

```
uv run pytest packages/engine/tests/optimizer/ -v
43 passed in 1.82s  (38 unit + 5 integration)

uv run mypy packages/engine/src/aerocloud/optimizer/ --strict
Success: no issues found in 4 source files

uv run ruff check packages/engine/src/aerocloud/optimizer/
All checks passed!
```

## Acceptance Criteria

- [x] `class InnerLoop` in inner_loop.py
- [x] `def optimize` in inner_loop.py
- [x] `OptimizationResult` in inner_loop.py
- [x] `torch.optim.Adam` in inner_loop.py
- [x] `clip_grad_norm_` in inner_loop.py
- [x] `F.interpolate` in inner_loop.py
- [x] `empty_cache` in inner_loop.py
- [x] `zero_grad(set_to_none=True)` in inner_loop.py
- [x] `lr=config.lr` in inner_loop.py
- [x] `InnerLoop` in optimizer __init__.py
- [x] >= 5 integration tests: **5 collected and passing**

## Implementation Notes

### InnerLoop Class

**Constructor:** Accepts `DifferentiableRenderer`, SDF (numpy or torch), `ref_weights`, and optional `InnerLoopConfig`. Converts numpy SDF to torch `(1,1,H,W)` float32, moves to `renderer._device`. Stores ref_weights detached on device.

**`_build_stage_schedule(base_resolutions, target)`:** Filters `base_resolutions` to keep only values strictly < target, then appends target. If `target=16` and `base=[8,32,128]`, schedule becomes `[8,16]`. If `target<=base[0]`, returns `[target]`.

**`_downsample_sdf(sdf_full, h, w)`:** Returns input unchanged if already matching. Otherwise `F.interpolate(mode='bilinear', align_corners=False)`.

**`optimize()`:**
1. Builds stage schedule from `config.stage_resolutions` + `max(target_h, target_w)`
2. Per stage: downsample SDF, snapshot `params_initial`, create fresh Adam
3. Per epoch: `zero_grad(set_to_none=True)` → forward → additive density → 4 losses → total loss → `backward()` → `clip_grad_norm_` → `step()` → record `.detach().item()`
4. Convergence check active after `min_epochs_before_convergence` epochs
5. After stage: `torch.cuda.empty_cache()` if CUDA available
6. Returns `OptimizationResult(params=renderer.params.detach(), ...)`

### Integration Tests

| Test | What it verifies |
|------|-----------------|
| `test_coarse_to_fine_converges_8px` | Loss[0] > Loss[-1] after 50 epochs at 8px |
| `test_stage_schedule_filters_large_resolutions` | 16px target with [8,32,128] -> 2 stages |
| `test_warm_start_carries_params` | Final params differ from initial params |
| `test_determinism_two_runs` | Same seed → identical loss histories |
| `test_optimize_returns_valid_result` | params.shape, list[list[float]], list[bool], wall_clock_s > 0 |

### Key Decision: Deviations

**D-13 (mypy):** `l_total.backward()` requires `# type: ignore[no-untyped-call]` because PyTorch type stubs do not annotate `Tensor.backward()` in a way mypy strict accepts. This is a well-known limitation of torch-stubs, not a code quality issue.

**Ruff SIM102:** Combined nested `if epoch >= ... / if check_convergence(...)` into single `if epoch >= ... and check_convergence(...)` per ruff's SIM102 rule.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Quality] mypy strict `no-untyped-call` on `backward()`**
- **Found during:** GREEN phase mypy check
- **Issue:** `torch.Tensor.backward()` is not typed in torch stubs under strict mode
- **Fix:** Added `# type: ignore[no-untyped-call]` comment — standard pattern for torch strict mypy
- **Files modified:** packages/engine/src/aerocloud/optimizer/inner_loop.py
- **Commit:** 143184e

**2. [Rule 2 - Quality] ruff import sort + SIM102**
- **Found during:** GREEN phase ruff check
- **Issue:** Import block sort violation (numpy before stdlib) + nested if pattern
- **Fix:** `uv run ruff check --fix` auto-sorted imports; combined convergence if-if into if-and
- **Files modified:** packages/engine/src/aerocloud/optimizer/inner_loop.py
- **Commit:** 143184e

## Known Stubs

None — InnerLoop.optimize() is fully implemented and wired. All exported functions are tested.

## Threat Flags

No new security-relevant surface introduced. InnerLoop operates entirely within the existing optimizer/renderer trust boundary. No network endpoints, auth paths, file access, or schema changes.

## Self-Check: PASSED

Files exist:
- packages/engine/src/aerocloud/optimizer/inner_loop.py — FOUND
- packages/engine/tests/optimizer/integration/__init__.py — FOUND
- packages/engine/tests/optimizer/integration/test_coarse_to_fine.py — FOUND
- packages/engine/src/aerocloud/optimizer/__init__.py (modified) — FOUND

Commits:
- 5ec3ce1 (RED: integration test files) — FOUND
- 143184e (GREEN: InnerLoop implementation) — FOUND

Test count: 43 total (38 unit from Plan 01 + 5 integration from Plan 02) — PASSED
Integration tests: 5 (>= 5 required) — PASSED
mypy strict: 0 errors — PASSED
ruff: 0 errors — PASSED

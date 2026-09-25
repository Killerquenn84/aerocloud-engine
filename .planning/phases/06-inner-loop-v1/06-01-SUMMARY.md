---
phase: 06-inner-loop-v1
plan: "01"
subsystem: optimizer
tags: [inner-loop, loss-functions, pydantic, tdd, convergence]
dependency_graph:
  requires:
    - "05-renderer-v1 (DifferentiableRenderer._sprites, .params, ._device)"
    - "02-datenmodell (AeroCloudBase)"
  provides:
    - "compute_l_wmse, compute_l_overlap, compute_l_fidelity, compute_l_temporal"
    - "compute_total_loss, compute_additive_density"
    - "check_convergence"
    - "LossWeights, InnerLoopConfig, OptimizationResult"
  affects:
    - "06-02-PLAN.md (InnerLoop class consumes all exports)"
tech_stack:
  added: []
  patterns:
    - "TYPE_CHECKING guard for DifferentiableRenderer import in loss.py"
    - "softplus scale clamp replicated from renderer to maintain gradient parity"
    - "Pydantic arbitrary_types_allowed=True for torch.Tensor in OptimizationResult"
key_files:
  created:
    - packages/engine/src/aerocloud/models/optimizer.py
    - packages/engine/src/aerocloud/optimizer/__init__.py
    - packages/engine/src/aerocloud/optimizer/loss.py
    - packages/engine/src/aerocloud/optimizer/convergence.py
    - packages/engine/tests/optimizer/__init__.py
    - packages/engine/tests/optimizer/conftest.py
    - packages/engine/tests/optimizer/unit/__init__.py
    - packages/engine/tests/optimizer/unit/test_loss_wmse.py
    - packages/engine/tests/optimizer/unit/test_loss_overlap.py
    - packages/engine/tests/optimizer/unit/test_loss_fidelity.py
    - packages/engine/tests/optimizer/unit/test_loss_temporal.py
    - packages/engine/tests/optimizer/unit/test_loss_total.py
    - packages/engine/tests/optimizer/unit/test_convergence.py
    - packages/engine/tests/optimizer/unit/test_grad_clipping.py
  modified: []
decisions:
  - "TYPE_CHECKING guard used in loss.py to import DifferentiableRenderer — avoids circular import while keeping full type safety"
  - "compute_additive_density replicates renderer's softplus + rotation clamping exactly to ensure mathematical parity with forward()"
  - "LossWeights uses Annotated[float, Field(...)] pattern for ge= constraints with strict=True Pydantic base"
metrics:
  duration_minutes: 5
  completed_date: "2026-04-14"
  tasks_completed: 1
  files_created: 14
  files_modified: 0
  tests_added: 38
---

# Phase 6 Plan 01: Inner Loop Scaffolding Summary

**One-liner:** 4-part composite loss (L_wmse + L_overlap + L_fidelity + L_temporal) with SUM-compositing overlap helper, rolling-window convergence detection, and Pydantic models — 38 unit tests, mypy strict clean, ruff clean.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 RED | Failing unit tests (7 files, 38 tests) | a3fed9c | tests/optimizer/unit/* |
| 1 GREEN | Pydantic models + loss functions + convergence | b8c7971 | src/aerocloud/optimizer/* + models/optimizer.py |

## Verification Results

```
uv run pytest packages/engine/tests/optimizer/unit/ -v
38 passed in 0.22s

uv run mypy packages/engine/src/aerocloud/optimizer/ --strict
Success: no issues found in 3 source files

uv run mypy packages/engine/src/aerocloud/models/optimizer.py --strict
Success: no issues found in 1 source file

uv run ruff check packages/engine/src/aerocloud/optimizer/
All checks passed!
```

## Acceptance Criteria

- [x] `def compute_l_wmse` in loss.py
- [x] `def compute_l_overlap` in loss.py
- [x] `def compute_l_fidelity` in loss.py
- [x] `def compute_l_temporal` in loss.py
- [x] `def compute_total_loss` in loss.py
- [x] `def compute_additive_density` in loss.py
- [x] `def check_convergence` in convergence.py
- [x] `class LossWeights` in models/optimizer.py
- [x] `class InnerLoopConfig` in models/optimizer.py
- [x] `class OptimizationResult` in models/optimizer.py
- [x] `arbitrary_types_allowed=True` in OptimizationResult
- [x] `alpha=1.0` default in LossWeights
- [x] `beta=10.0` default in LossWeights
- [x] `sdf.clamp(min=0.0)` in L_wmse
- [x] `F.relu` in L_overlap
- [x] `F.cosine_similarity` in L_fidelity
- [x] >= 18 unit tests: **38 tests pass**

## Implementation Notes

### Loss Functions

**compute_l_wmse:** `mean((clamp(sdf, min=0) * (1 - density))^2)` — exterior pixels (sdf < 0) contribute exactly 0 via the clamp, interior coverage is rewarded by squeezing the penalized gap toward zero.

**compute_l_overlap:** `mean(ReLU(density - 1.0)^2)` — squared ReLU provides a smooth, differentiable penalty that is exactly 0 at density <= 1.0.

**compute_l_fidelity:** `1 - cosine_similarity(s_ref.unsqueeze(0), s_current.unsqueeze(0))` — operates on batched 1D vectors via unsqueeze, result is scalar in ~[0, 2].

**compute_l_temporal:** `mean((current[:, :2] - initial[:, :2])^2)` — only y/x columns (indices 0, 1) contribute; scale/rotation drift is intentionally excluded.

**compute_total_loss:** `alpha * L_wmse + beta * L_overlap + gamma * L_fidelity + lambda_ * L_temporal` — default lambda_=0.0 disables temporal term for static word clouds.

**compute_additive_density:** Replicates `DifferentiableRenderer.forward()` affine warp logic (same softplus scale clamp, same rotation clamping, same NDC convention) but uses additive SUM instead of alpha-over compositing. This intentionally allows values > 1.0 at overlapping pixels. Accesses renderer._sprites, renderer.params, renderer._device.

### Convergence Detection

**check_convergence:** Returns False if history length < window. Computes `(max - min) / max(|max|, 1e-8)` over the last `window` entries. Returns True if relative range < epsilon (0.001 default).

### Pydantic Models

**LossWeights:** Frozen, strict, extra=forbid. All four weights annotated with `ge=0.0`. Defaults: alpha=1.0, beta=10.0, gamma=0.1, lambda_=0.0.

**InnerLoopConfig:** Frozen, strict, extra=forbid. Uses `default_factory=LossWeights` for the weights field. Stage resolutions default to [8, 32, 128] for coarse-to-fine pipeline.

**OptimizationResult:** Overrides base model_config with `strict=False, arbitrary_types_allowed=True` to allow `torch.Tensor` as a field type while inheriting frozen + extra=forbid behavior.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all exported functions are fully implemented and tested.

## Threat Flags

No new security-relevant surface introduced. All tensors flow through existing DifferentiableRenderer (trusted internal boundary per T-06-03). No network endpoints, auth paths, or file access patterns.

## Self-Check: PASSED

Files exist:
- packages/engine/src/aerocloud/optimizer/loss.py — FOUND
- packages/engine/src/aerocloud/optimizer/convergence.py — FOUND
- packages/engine/src/aerocloud/optimizer/__init__.py — FOUND
- packages/engine/src/aerocloud/models/optimizer.py — FOUND

Commits:
- a3fed9c (RED: test files) — FOUND
- b8c7971 (GREEN: implementation) — FOUND

Test count: 38 (>= 18 required) — PASSED

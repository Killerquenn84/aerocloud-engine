# wiki/code/optimizer-inner-loop.md

> Module: `packages/engine/src/aerocloud/optimizer/inner_loop.py`
> Phase: 06-inner-loop-v1
> Created: 2026-04-14

---

## Overview

`InnerLoop` is the central class of the Phase 6 optimizer module. It orchestrates the complete Coarse-to-Fine differentiable optimization pipeline, consuming a `DifferentiableRenderer` (Phase 5) and producing an `OptimizationResult`.

**Architecture position:** InnerLoop sits between the DifferentiableRenderer (Phase 5) and the MAP-Elites outer loop (Phase 9). Phase 9 calls `InnerLoop.optimize()` thousands of times during evolutionary search.

---

## Public API

### `class InnerLoop`

**Module path:** `aerocloud.optimizer.inner_loop.InnerLoop`
**Also importable from:** `aerocloud.optimizer.InnerLoop`

#### Constructor

```python
InnerLoop(
    renderer: DifferentiableRenderer,
    sdf: np.ndarray | torch.Tensor,
    ref_weights: torch.Tensor,
    config: InnerLoopConfig | None = None,
)
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `renderer` | `DifferentiableRenderer` | Phase 5 renderer. Its `.params` (N, 4) will be optimized in-place. |
| `sdf` | `np.ndarray` or `torch.Tensor` | Signed distance field of the target silhouette. Shape: `(H, W)`, `(1, H, W)`, or `(1, 1, H, W)`. Positive values = inside shape, negative = outside. float32 or float64 (converted to float32 internally). |
| `ref_weights` | `torch.Tensor` | (N,) float32 reference scale distribution from Phase 3 TF-IDF. Used in L_fidelity to prevent artificial scale inflation. Detached during construction. |
| `config` | `InnerLoopConfig \| None` | Optimization hyperparameters. Defaults to `InnerLoopConfig()` with Blueprint defaults. |

**Side effects:** Moves SDF and ref_weights to `renderer._device`.

#### `optimize() -> OptimizationResult`

Runs the full Coarse-to-Fine optimization pipeline.

**Algorithm:**

1. Build resolution schedule: `_build_stage_schedule(config.stage_resolutions, max(H, W))`
   - Default: `[8, 32, 128, target]` (coarser stages filtered if target is small)
2. For each stage resolution:
   a. Downsample SDF via bilinear interpolation
   b. Snapshot `params_initial` for L_temporal
   c. Create fresh Adam optimizer (`lr=config.lr, betas=(0.9, 0.999), eps=1e-8`)
   d. For each epoch (up to `max_epochs`):
      - Zero gradients (`set_to_none=True`)
      - Forward pass: alpha-over density + additive density (two passes)
      - Compute 4 losses: L_wmse, L_overlap, L_fidelity, L_temporal
      - Backward + gradient clipping (`max_norm=1.0`)
      - Adam step
      - Record loss (`.detach().item()`)
      - Check convergence after `min_epochs_before_convergence` epochs
   e. After stage: `torch.cuda.empty_cache()` if CUDA available
3. Return `OptimizationResult`

**Returns:** `OptimizationResult` — see Models section below.

---

## Helper Functions

### `_build_stage_schedule(base_resolutions, target) -> list[int]`

Builds the Coarse-to-Fine resolution schedule.

```python
_build_stage_schedule([8, 32, 128], 256)  # -> [8, 32, 128, 256]
_build_stage_schedule([8, 32, 128], 16)   # -> [8, 16]
_build_stage_schedule([8, 32, 128], 8)    # -> [8]
_build_stage_schedule([], 128)            # -> [128]  (single stage)
```

Rule: Keeps only resolutions strictly < target, then appends target.

### `_downsample_sdf(sdf_full, target_h, target_w) -> torch.Tensor`

Downsamples a `(1, 1, H, W)` SDF tensor to `(1, 1, target_h, target_w)` using bilinear interpolation (`align_corners=False`). Returns input unchanged if already matching size.

---

## Models

### `InnerLoopConfig`

Pydantic model for optimization hyperparameters.

| Field | Default | Constraint | Description |
|-------|---------|------------|-------------|
| `weights` | `LossWeights()` | — | Loss weight coefficients |
| `lr` | `0.001` | `> 0` | Adam learning rate (Blueprint Teil V) |
| `max_epochs` | `100` | `>= 1` | Max epochs per stage |
| `min_epochs_before_convergence` | `20` | `>= 0` | Warmup before convergence check |
| `convergence_window` | `10` | `>= 2` | Rolling window size for plateau detection |
| `convergence_epsilon` | `0.001` | `> 0` | Relative range threshold for convergence |
| `stage_resolutions` | `[8, 32, 128]` | — | Coarse-to-fine base resolutions |

### `LossWeights`

Pydantic model for loss weighting coefficients.

| Field | Default | Blueprint Reference |
|-------|---------|---------------------|
| `alpha` | `1.0` | D-06: L_wmse weight |
| `beta` | `10.0` | D-06: L_overlap weight (high = strong anti-overlap) |
| `gamma` | `0.1` | D-06: L_fidelity weight |
| `lambda_` | `0.0` | D-06: L_temporal weight (disabled in v1) |

All weights `>= 0.0`. Frozen, strict, extra=forbid.

### `OptimizationResult`

Frozen Pydantic model containing full optimization diagnostics.

| Field | Type | Description |
|-------|------|-------------|
| `params` | `torch.Tensor (N, 4)` | Final optimized parameters `[y, x, scale, rotation]` |
| `stage_loss_histories` | `list[list[float]]` | Per-stage per-epoch loss values (Python floats, not tensors) |
| `total_epochs` | `int` | Total epochs run across all stages |
| `convergence_flags` | `list[bool]` | Whether each stage converged before `max_epochs` |
| `wall_clock_s` | `float` | Total wall-clock time in seconds |

Note: `strict=False, arbitrary_types_allowed=True` allows `torch.Tensor` storage in Pydantic.

---

## Memory Hygiene (D-16..D-18)

| Practice | Implementation | Why |
|----------|---------------|-----|
| `zero_grad(set_to_none=True)` | Every epoch | Avoids accumulating zero tensors (D-18) |
| `.detach().item()` for loss logging | `loss_val = l_total.detach().item()` | Never retain computation graph (D-16) |
| `torch.cuda.empty_cache()` | After each stage | Release GPU cache between stages (D-17) |
| `params_initial = renderer.params.detach().clone()` | Per stage | Detached snapshot — no graph retained |

---

## Code Example

```python
from aerocloud.optimizer import InnerLoop, InnerLoopConfig, LossWeights
from aerocloud.renderer._renderer import DifferentiableRenderer
import torch
import numpy as np

# Setup (from Phase 4 + Phase 5)
renderer = DifferentiableRenderer(params_n4=params, sprites=sprites, device=device)
sdf_np = compute_sdf(mask)  # from Phase 4 geometry module

# Optional: custom config
config = InnerLoopConfig(
    weights=LossWeights(beta=5.0),  # less aggressive overlap penalty
    max_epochs=50,
    stage_resolutions=[8, 32],  # skip 128px coarse stage
)

# Run optimization
loop = InnerLoop(
    renderer=renderer,
    sdf=sdf_np,
    ref_weights=torch.from_numpy(tfidf_weights),
    config=config,
)
result = loop.optimize()

# Access results
final_params = result.params  # (N, 4) tensor
print(f"Converged: {result.convergence_flags}")
print(f"Stages: {len(result.stage_loss_histories)}")
print(f"Total epochs: {result.total_epochs}")
print(f"Wall clock: {result.wall_clock_s:.2f}s")
```

---

## Convergence Detection

Uses `check_convergence(loss_history, window=10, epsilon=0.001)`:

```
relative_range = (max(last 10) - min(last 10)) / max(|max(last 10)|, 1e-8)
converged = relative_range < 0.001
```

Active only after `min_epochs_before_convergence=20` epochs (warmup period).

---

## Known Limitations (v1)

| Limitation | Planned Fix |
|------------|-------------|
| No N upper bound guard | Phase 12: enforce N <= 200 at Celery task boundary |
| No wall-clock timeout | Phase 12: add absolute timeout to optimize() |
| CPU only (GPU path exists but untested) | Phase 12: CUDA test suite |
| stage_h == stage_w (square stages) | Phase 7: rectangular stage support for non-square masks |

---

## Dependencies

- `DifferentiableRenderer` from Phase 5 (`aerocloud.renderer._renderer`)
- `compute_additive_density`, all loss functions from Phase 6 (`aerocloud.optimizer.loss`)
- `check_convergence` from Phase 6 (`aerocloud.optimizer.convergence`)
- `InnerLoopConfig`, `OptimizationResult` from Phase 6 (`aerocloud.models.optimizer`)
- `structlog` for per-stage logging

---

*Source: packages/engine/src/aerocloud/optimizer/inner_loop.py — Phase 06-inner-loop-v1*

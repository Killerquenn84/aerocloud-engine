# Gemini Review Prompt — Phase 6 Inner Loop-v1

## Instructions for Gemini

```bash
gemini -p "$(cat .planning/phases/06-inner-loop-v1/06-3ki-review/gemini-review-prompt.md)"
```

Or paste this prompt directly into Gemini CLI / Gemini 2.5 Pro.

---

## REVIEW REQUEST: AeroCloud Engine — Phase 6 Inner Loop Optimizer

You are performing a code review for the AeroCloud Engine Phase 6 Inner Loop optimizer module. This is a **UX + Edge Cases + Numerical Stability** review.

**Role:** You are Gemini, the UX and edge-case reviewer. Focus on: user-facing error quality, numerical stability at extremes, and edge cases that could silently produce wrong results without raising errors.

**Review protocol:** Apply the CLAUDE.md anti-sycophancy protocol. "This looks fine" is NOT acceptable without specific analysis.

**Specific questions to answer:**

1. **Edge case: 1-word optimization (N=1)**
   - When N=1 (single word), `compute_l_fidelity` calls:
     `F.cosine_similarity(s_ref.unsqueeze(0), s_current.unsqueeze(0))` where both are `(1, 1)` tensors.
   - Is the cosine similarity of two scalar values well-defined? What happens when N=1 and both values are positive? When one is zero?
   - Does `compute_l_overlap` make sense for N=1? A single sprite can never overlap itself.
   - Does the optimization for N=1 converge correctly? What does "overlap penalty" mean in this case?
   - Is L_fidelity the primary driver for N=1? Does this cause instability?

2. **Edge case: target resolution smaller than 8px**
   - `InnerLoopConfig` default `stage_resolutions=[8, 32, 128]`. If `target=4` (SDF is 4x4), `_build_stage_schedule([8,32,128], 4)` returns `[4]` (all coarser stages filtered).
   - With a 4x4 canvas (16 pixels), can the optimizer meaningfully place words? The affine warp for a 4x4 sprite on a 4x4 canvas would always cover the entire canvas.
   - What is the behavior of `F.affine_grid` for 4x4 with sprites that are also 4x4? Does the grid degeneracy cause NaN gradients?
   - What guard should exist for minimum resolution?

3. **Loss function numerical stability at extreme scales**
   - `compute_l_wmse`: if `sdf` contains very large values (e.g., from a 4096x4096 mask where the SDF max is ~2048.0), then `sdf_positive = sdf.clamp(min=0.0)` could be up to 2048.0. With `(1 - density)` in [0, 1], the squared term is `(2048 * 1)^2 = 4,194,304`. Is this a problem for the Adam optimizer (exploding gradients)?
   - `compute_additive_density`: `inv_s = 1.0 / s_i`. If `s_i` approaches 0.01 (the softplus floor), `inv_s ≈ 100`. The affine matrix entries would be ~100x. Does `F.affine_grid` handle large affine values gracefully? What happens to `grid_sample` when the inverse scale is very large (sprite occupies only 1% of canvas)?
   - `compute_l_fidelity`: cosine similarity with PyTorch eps=1e-8. If both `s_ref` and `s_current` are near-zero (scales approaching 0.01), what is the behavior?

4. **Quality of error messages when things go wrong**
   - If `InnerLoop` is constructed with `sdf` of wrong dtype (e.g., int32), the `sdf.float()` call converts silently. Is this the right behavior? Should it warn the user?
   - If `ref_weights` has a different N than `renderer.params`, `compute_l_fidelity` will silently compute wrong cosine similarity (different-length vectors). The `.unsqueeze(0)` makes them `(1, N_ref)` and `(1, N_params)` — but `F.cosine_similarity` with `dim=1` on tensors of different width would raise a shape error. Does it? Or does broadcasting produce wrong results silently?
   - If `renderer._sprites` list length != `renderer.params.shape[0]`, what happens in `compute_additive_density`? It iterates `enumerate(renderer._sprites)` and uses `renderer.params[i]` — if `len(_sprites) < N`, it accesses fewer params than exist (silent truncation). If `len(_sprites) > N`, it would raise IndexError. Is this the right behavior?

5. **Convergence behavior analysis**
   - For the default 4-stage schedule [8, 32, 128, target], what is the expected loss trajectory?
     - Stage 1 (8px): How many epochs to converge? Is the 100-epoch budget sufficient at 8px?
     - Stage 2 (32px): After warm-start from 8px, does convergence happen faster or slower?
     - Stage 3 (128px): The 128px stage has 128*128=16,384 pixels. Does the loss scale by resolution? Does `min_epochs_before_convergence=20` need to be resolution-dependent?
   - The convergence check uses `max_val` in the divisor. If loss is 0.1 and oscillates by 0.0001, ratio = 0.001 = epsilon — right at the boundary. Should the check be strict (`<`) or inclusive (`<=`)?

---

## Source Code to Review

### packages/engine/src/aerocloud/optimizer/loss.py

```python
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import torch
import torch.nn.functional as F  # noqa: N812

if TYPE_CHECKING:
    from aerocloud.renderer._renderer import DifferentiableRenderer

from aerocloud.models.optimizer import LossWeights


def compute_l_wmse(density: torch.Tensor, sdf: torch.Tensor) -> torch.Tensor:
    sdf_positive = sdf.clamp(min=0.0)
    return ((sdf_positive * (1.0 - density)) ** 2).mean()


def compute_l_overlap(additive_density: torch.Tensor) -> torch.Tensor:
    return (F.relu(additive_density - 1.0) ** 2).mean()


def compute_l_fidelity(s_ref: torch.Tensor, params: torch.Tensor) -> torch.Tensor:
    s_current = params[:, 2]
    return 1.0 - F.cosine_similarity(
        s_ref.unsqueeze(0), s_current.unsqueeze(0)
    ).squeeze()


def compute_l_temporal(params_current: torch.Tensor, params_initial: torch.Tensor) -> torch.Tensor:
    return ((params_current[:, :2] - params_initial[:, :2]) ** 2).mean()


def compute_total_loss(
    weights: LossWeights,
    l_wmse: torch.Tensor,
    l_overlap: torch.Tensor,
    l_fidelity: torch.Tensor,
    l_temporal: torch.Tensor,
) -> torch.Tensor:
    return (
        weights.alpha * l_wmse
        + weights.beta * l_overlap
        + weights.gamma * l_fidelity
        + weights.lambda_ * l_temporal
    )


def compute_additive_density(renderer, canvas_h: int, canvas_w: int) -> torch.Tensor:
    additive = torch.zeros(1, 1, canvas_h, canvas_w, device=renderer._device, dtype=torch.float32)
    for i, sprite in enumerate(renderer._sprites):
        y_i, x_i, s_i, theta_i = renderer.params[i]
        theta_i = torch.remainder(theta_i + math.pi, 2 * math.pi) - math.pi
        s_i = torch.nn.functional.softplus(s_i - 0.01) + 0.01
        x_n = ((2.0 * x_i + 1.0) / canvas_w) - 1.0
        y_n = ((2.0 * y_i + 1.0) / canvas_h) - 1.0
        cos_t = torch.cos(theta_i)
        sin_t = torch.sin(theta_i)
        inv_s = 1.0 / s_i
        a11 = inv_s * cos_t
        a12 = inv_s * sin_t
        a21 = -inv_s * sin_t
        a22 = inv_s * cos_t
        tx = -(a11 * x_n + a12 * y_n)
        ty = -(a21 * x_n + a22 * y_n)
        theta_mat = torch.stack([a11, a12, tx, a21, a22, ty]).reshape(1, 2, 3)
        grid = F.affine_grid(theta_mat, [1, 1, canvas_h, canvas_w], align_corners=False)
        warped = F.grid_sample(sprite, grid, mode="bilinear", padding_mode="zeros", align_corners=False)
        additive = additive + warped
    return additive
```

### packages/engine/src/aerocloud/optimizer/convergence.py

```python
from __future__ import annotations


def check_convergence(loss_history: list[float], window: int = 10, epsilon: float = 0.001) -> bool:
    if len(loss_history) < window:
        return False
    window_vals = loss_history[-window:]
    max_val = max(window_vals)
    min_val = min(window_vals)
    range_val = max_val - min_val
    scale = max(abs(max_val), 1e-8)
    return (range_val / scale) < epsilon
```

### packages/engine/src/aerocloud/optimizer/inner_loop.py (key section)

```python
class InnerLoop:
    def __init__(
        self,
        renderer: DifferentiableRenderer,
        sdf: np.ndarray | torch.Tensor,
        ref_weights: torch.Tensor,
        config: InnerLoopConfig | None = None,
    ) -> None:
        self._renderer = renderer
        self._config = config if config is not None else InnerLoopConfig()
        if isinstance(sdf, np.ndarray):
            sdf_tensor = torch.from_numpy(sdf.astype(np.float32))
        else:
            sdf_tensor = sdf.float()
        if sdf_tensor.ndim == 2:
            sdf_tensor = sdf_tensor.unsqueeze(0).unsqueeze(0)
        elif sdf_tensor.ndim == 3:
            sdf_tensor = sdf_tensor.unsqueeze(0)
        self._sdf_full = sdf_tensor.to(renderer._device)
        self._ref_weights = ref_weights.detach().to(renderer._device)
        self._target_h = sdf_tensor.shape[-2]
        self._target_w = sdf_tensor.shape[-1]

    def optimize(self) -> OptimizationResult:
        wall_start = time.perf_counter()
        config = self._config
        renderer = self._renderer
        target = max(self._target_h, self._target_w)
        schedule = _build_stage_schedule(list(config.stage_resolutions), target)
        stage_loss_histories = []
        convergence_flags = []
        total_epochs = 0

        for stage_idx, res in enumerate(schedule):
            stage_h = stage_w = res
            sdf_stage = _downsample_sdf(self._sdf_full, stage_h, stage_w)
            params_initial = renderer.params.detach().clone()
            optimizer = torch.optim.Adam([renderer.params], lr=config.lr, betas=(0.9, 0.999), eps=1e-8)
            loss_history = []
            stage_converged = False

            for epoch in range(config.max_epochs):
                optimizer.zero_grad(set_to_none=True)
                density = renderer.forward(stage_h, stage_w)
                additive = compute_additive_density(renderer, stage_h, stage_w)
                l_wmse = compute_l_wmse(density, sdf_stage)
                l_overlap = compute_l_overlap(additive)
                l_fidelity = compute_l_fidelity(self._ref_weights, renderer.params)
                l_temporal = compute_l_temporal(renderer.params, params_initial)
                l_total = compute_total_loss(config.weights, l_wmse, l_overlap, l_fidelity, l_temporal)
                l_total.backward()
                clip_grad_norm_([renderer.params], max_norm=1.0)
                optimizer.step()
                loss_val = l_total.detach().item()
                loss_history.append(loss_val)
                total_epochs += 1
                if epoch >= config.min_epochs_before_convergence and check_convergence(
                    loss_history, window=config.convergence_window, epsilon=config.convergence_epsilon
                ):
                    stage_converged = True
                    break

            stage_loss_histories.append(loss_history)
            convergence_flags.append(stage_converged)
            logger.info("inner_loop.stage_complete", stage=stage_idx, resolution=res,
                        epochs=len(loss_history), converged=stage_converged,
                        final_loss=loss_history[-1] if loss_history else float("nan"))
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        wall_clock_s = time.perf_counter() - wall_start
        return OptimizationResult(
            params=renderer.params.detach(),
            stage_loss_histories=stage_loss_histories,
            total_epochs=total_epochs,
            convergence_flags=convergence_flags,
            wall_clock_s=wall_clock_s,
        )
```

### packages/engine/src/aerocloud/models/optimizer.py

```python
class LossWeights(AeroCloudBase):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    alpha: Annotated[float, Field(default=1.0, ge=0.0)] = 1.0
    beta: Annotated[float, Field(default=10.0, ge=0.0)] = 10.0
    gamma: Annotated[float, Field(default=0.1, ge=0.0)] = 0.1
    lambda_: Annotated[float, Field(default=0.0, ge=0.0)] = 0.0


class InnerLoopConfig(AeroCloudBase):
    weights: LossWeights = Field(default_factory=LossWeights)
    lr: Annotated[float, Field(default=0.001, gt=0.0)] = 0.001
    max_epochs: Annotated[int, Field(default=100, ge=1)] = 100
    min_epochs_before_convergence: Annotated[int, Field(default=20, ge=0)] = 20
    convergence_window: Annotated[int, Field(default=10, ge=2)] = 10
    convergence_epsilon: Annotated[float, Field(default=0.001, gt=0.0)] = 0.001
    stage_resolutions: list[int] = Field(default_factory=lambda: [8, 32, 128])


class OptimizationResult(AeroCloudBase):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=False, arbitrary_types_allowed=True)
    params: torch.Tensor
    stage_loss_histories: list[list[float]]
    total_epochs: Annotated[int, Field(ge=0)]
    convergence_flags: list[bool]
    wall_clock_s: Annotated[float, Field(ge=0.0)]
```

---

## Context

This module implements the "inner loop" of the AeroCloud Engine's dual-loop optimization architecture:
- **Phase 5** (DifferentiableRenderer): Produces density maps from word placement parameters
- **Phase 6** (InnerLoop, this module): Optimizes word placements via gradient descent on the 4-part composite loss
- **Phase 9** (MAP-Elites): Will call InnerLoop.optimize() thousands of times for evolutionary search

The optimizer runs on CPU in v1. GPU support (CUDA) is planned for Phase 12.

Target use case: 50-200 words placed in a silhouette shape (e.g., a butterfly outline). The optimization finds placement parameters (y, x, scale, rotation) that maximize coverage of the silhouette interior while minimizing word overlap.

---

## Expected Output Format

```
## Gemini Review: Phase 6 Inner Loop-v1

### Edge Case Analysis (Questions 1-4)
[Detailed analysis of each edge case]

### Numerical Stability Analysis (Question 3)
[Loss function stability at extremes]

### Convergence Analysis (Question 5)
[Expected loss trajectory + convergence robustness]

### Error Quality Assessment
[How helpful are the error messages?]

### S-1..S-8 (brief, focus on any not covered by Codex)
### L-1..L-8 (focus on graceful degradation + error quality)
### A-1..A-5 (focus on API usability + UX)

### Summary
[APPROVED / APPROVED-WITH-FIXES / BLOCKED with specific items]
```

---

*Prepared for Gemini review | Phase 06-inner-loop-v1 | 2026-04-14*

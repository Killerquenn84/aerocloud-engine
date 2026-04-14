# Codex Review Prompt — Phase 6 Inner Loop-v1

## Instructions for Codex

```bash
codex exec --skip-git-repo-check "$(cat .planning/phases/06-inner-loop-v1/06-3ki-review/codex-review-prompt.md)"
```

Or paste this prompt directly into Codex CLI.

---

## REVIEW REQUEST: AeroCloud Engine — Phase 6 Inner Loop Optimizer

You are performing a code review for the AeroCloud Engine Phase 6 Inner Loop optimizer module. This is a **Performance + Security + Correctness** review.

**Role:** You are Codex, the adversarial reviewer. Be critical. Find bugs, inefficiencies, and potential production failures. "This looks good" is NOT an acceptable output without specific evidence.

**Review protocol:** Apply the CLAUDE.md anti-sycophancy check for each finding:
- S-1..S-8: Security (Injection, XSS, CSRF, Auth, Secrets, SSRF, Path Traversal, DoS)
- L-1..L-8: Stability (Error Handling, Resource Leaks, Race Conditions, Timeouts, Memory, Retry Logic, Graceful Degradation, Logging)
- A-1..A-5: Architecture (SRP, DRY, Coupling, API Contract, Backwards Compatibility)

**Specific questions to answer:**

1. **Performance of compute_additive_density (second forward pass overhead):**
   - The optimizer calls `renderer.forward(stage_h, stage_w)` (alpha-over) AND `compute_additive_density(renderer, stage_h, stage_w)` (additive) EVERY epoch. This is 2 full forward passes per epoch instead of 1.
   - Is there a way to compute both compositing modes in a single pass? What is the actual overhead ratio?
   - At 128px canvas with N=200 sprites, estimate the GPU VRAM and wall-clock overhead of the double forward pass.

2. **Thread safety of InnerLoop (renderer mutation during optimize):**
   - `renderer.params` is an `nn.Parameter` that is mutated in-place by `optimizer.step()` on every epoch.
   - If two goroutines/threads share the same `renderer` instance (e.g., via Celery concurrency), is there a race condition?
   - The `compute_additive_density` function reads `renderer.params` while `optimizer.step()` writes it. On CUDA, are these operations atomic? On CPU?
   - What guard would you add to make InnerLoop thread-safe?

3. **Memory leak potential in stage transitions:**
   - After each stage, `torch.cuda.empty_cache()` is called IF cuda is available. On CPU, no cache clearing happens.
   - The `params_initial = renderer.params.detach().clone()` snapshot is created per stage. Does this retain any computation graph?
   - The `optimizer` (Adam) is recreated per stage. Does the old optimizer's first/second moment buffers (`state_dict()`) get garbage collected correctly?
   - Are there any subtle tensor lifetimes you see in the `for epoch in range(config.max_epochs)` loop that could accumulate?

4. **Correctness of the convergence formula:**
   - `scale = max(abs(max_val), 1e-8)`
   - If `max_val` is negative (loss can't be negative, but consider if the loss formula had a sign bug), what happens?
   - If `loss_history[-window:]` contains a mix of very large (e.g., 1e6) and very small values, does the relative range formula correctly detect non-convergence?
   - Is the `window=10` + `epsilon=0.001` combination robust to the typical loss landscape of the 4-part composite loss?

5. **SDF downsampling correctness:**
   - `F.interpolate(sdf_full, size=(target_h, target_w), mode='bilinear', align_corners=False)`
   - Is bilinear interpolation the correct mode for SDF downsampling? SDF values have physical meaning (distance). Does bilinear interpolation preserve the SDF zero-crossing accurately at low resolutions (8px)?
   - Could `mode='area'` (average pooling) be better for SDF downsampling to avoid aliasing?

---

## Source Code

### packages/engine/src/aerocloud/models/optimizer.py

```python
"""Pydantic models for the Inner Loop optimizer (Phase 6).

Provides LossWeights, InnerLoopConfig, and OptimizationResult models
per D-19, D-20, D-21 of the AeroCloud Blueprint.
"""

from __future__ import annotations

from typing import Annotated

import torch
from pydantic import ConfigDict, Field

from aerocloud.models.base import AeroCloudBase


class LossWeights(AeroCloudBase):
    """Weighting coefficients for the 4-part composite loss (D-06).

    L_total = alpha * L_wmse + beta * L_overlap + gamma * L_fidelity + lambda_ * L_temporal

    All weights are non-negative. The default lambda_=0.0 disables the
    temporal coherence term, which is only useful for live-feed word clouds
    where frame-to-frame stability matters.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    alpha: Annotated[float, Field(default=1.0, ge=0.0)] = 1.0
    """Weight for L_wmse (boundary fitness). Default 1.0."""

    beta: Annotated[float, Field(default=10.0, ge=0.0)] = 10.0
    """Weight for L_overlap (primitive overlap). Default 10.0."""

    gamma: Annotated[float, Field(default=0.1, ge=0.0)] = 0.1
    """Weight for L_fidelity (data fidelity). Default 0.1."""

    lambda_: Annotated[float, Field(default=0.0, ge=0.0)] = 0.0
    """Weight for L_temporal (temporal coherence). Default 0.0 (disabled)."""


class InnerLoopConfig(AeroCloudBase):
    """Full configuration for one inner-loop optimization run.

    Controls Adam learning rate, epoch budgets, convergence detection
    thresholds, and the coarse-to-fine resolution schedule.
    """

    weights: LossWeights = Field(default_factory=LossWeights)
    """Loss weight coefficients. Defaults to LossWeights()."""

    lr: Annotated[float, Field(default=0.001, gt=0.0)] = 0.001
    """Adam learning rate. Default 0.001 (Blueprint Teil V)."""

    max_epochs: Annotated[int, Field(default=100, ge=1)] = 100
    """Maximum number of optimization epochs per resolution stage."""

    min_epochs_before_convergence: Annotated[int, Field(default=20, ge=0)] = 20
    """Minimum epochs before convergence check is active."""

    convergence_window: Annotated[int, Field(default=10, ge=2)] = 10
    """Number of recent epochs used in plateau detection."""

    convergence_epsilon: Annotated[float, Field(default=0.001, gt=0.0)] = 0.001
    """Relative loss range threshold for convergence detection."""

    stage_resolutions: list[int] = Field(default_factory=lambda: [8, 32, 128])
    """Coarse-to-fine resolution stages in pixels. Default [8, 32, 128]."""


class OptimizationResult(AeroCloudBase):
    """Output record from a completed inner-loop run (D-21).

    Carries the final optimized parameters alongside per-stage diagnostics.
    Uses ``strict=False`` and ``arbitrary_types_allowed=True`` to permit
    torch.Tensor in a Pydantic model.
    """

    # Override base model_config to allow torch.Tensor
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=False,
        arbitrary_types_allowed=True,
    )

    params: torch.Tensor
    """Final (N, 4) parameter tensor [y, x, scale, rotation]."""

    stage_loss_histories: list[list[float]]
    """Per-stage list of per-epoch loss values."""

    total_epochs: Annotated[int, Field(ge=0)]
    """Total number of epochs run across all stages."""

    convergence_flags: list[bool]
    """Whether each stage converged before max_epochs."""

    wall_clock_s: Annotated[float, Field(ge=0.0)]
    """Total wall-clock time in seconds."""
```

### packages/engine/src/aerocloud/optimizer/loss.py

```python
"""Loss functions for the inner-loop optimizer (Phase 6).

Implements the 4-part composite loss per D-01..D-06 of the AeroCloud Blueprint:

    L_total = alpha * L_wmse + beta * L_overlap + gamma * L_fidelity + lambda_ * L_temporal

Also provides compute_additive_density, the SUM-based compositing helper
needed by L_overlap that allows per-pixel density to exceed 1.0.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import torch
import torch.nn.functional as F  # noqa: N812

if TYPE_CHECKING:
    from aerocloud.renderer._renderer import DifferentiableRenderer

from aerocloud.models.optimizer import LossWeights


def compute_l_wmse(
    density: torch.Tensor,
    sdf: torch.Tensor,
) -> torch.Tensor:
    """Weighted Mean Squared Error loss (D-01).

    Penalizes uncovered interior pixels weighted by their SDF depth.
    Exterior pixels (sdf < 0) contribute zero via the clamp.

    Formula::

        L_wmse = mean((clamp(sdf, min=0) * (1 - density))^2)

    Args:
        density: (1, 1, H, W) float32 renderer output in [0, 1].
        sdf: (1, 1, H, W) float32 signed distance field.
            Positive inside the shape, negative outside.

    Returns:
        Scalar tensor.
    """
    sdf_positive = sdf.clamp(min=0.0)
    return ((sdf_positive * (1.0 - density)) ** 2).mean()


def compute_l_overlap(
    additive_density: torch.Tensor,
) -> torch.Tensor:
    """Primitive Overlap loss (D-03).

    Penalizes pixels where sprites overlap (additive density > 1.0).
    Uses squared ReLU so the penalty is smooth and differentiable.

    Formula::

        L_overlap = mean(ReLU(density - 1.0)^2)

    Args:
        additive_density: (1, 1, H, W) float32 SUM-composited density
            (may exceed 1.0 where sprites overlap).

    Returns:
        Scalar tensor.
    """
    return (F.relu(additive_density - 1.0) ** 2).mean()


def compute_l_fidelity(
    s_ref: torch.Tensor,
    params: torch.Tensor,
) -> torch.Tensor:
    """Data Fidelity loss (D-04).

    Prevents artificial scale inflation by penalising deviation between
    the reference scale distribution and the current scale parameters.
    Uses cosine similarity so only the *shape* of the distribution matters,
    not the absolute magnitudes.

    Formula::

        L_fidelity = 1 - cosine_similarity(s_ref, params[:, 2])

    Args:
        s_ref: (N,) float32 reference scale vector (from TF-IDF weights).
        params: (N, 4) float32 parameter tensor [y, x, scale, rotation].

    Returns:
        Scalar tensor in approximately [0, 2].
    """
    s_current = params[:, 2]
    return 1.0 - F.cosine_similarity(
        s_ref.unsqueeze(0), s_current.unsqueeze(0)
    ).squeeze()


def compute_l_temporal(
    params_current: torch.Tensor,
    params_initial: torch.Tensor,
) -> torch.Tensor:
    """Temporal Coherence loss (D-05).

    Penalises position drift between the current and initial parameters.
    Only (y, x) columns contribute; scale and rotation changes are ignored.
    Default weight lambda_=0.0 effectively disables this term for static
    word clouds.

    Formula::

        L_temporal = mean((params_current[:, :2] - params_initial[:, :2])^2)

    Args:
        params_current: (N, 4) float32 current parameter tensor.
        params_initial: (N, 4) float32 initial (reference) parameter tensor.

    Returns:
        Scalar tensor.
    """
    return ((params_current[:, :2] - params_initial[:, :2]) ** 2).mean()


def compute_total_loss(
    weights: LossWeights,
    l_wmse: torch.Tensor,
    l_overlap: torch.Tensor,
    l_fidelity: torch.Tensor,
    l_temporal: torch.Tensor,
) -> torch.Tensor:
    """Composite loss combining all four terms (D-06).

    Formula::

        L_total = alpha * L_wmse + beta * L_overlap
                + gamma * L_fidelity + lambda_ * L_temporal

    Args:
        weights: LossWeights instance with the four weighting scalars.
        l_wmse: Boundary-fitness loss scalar.
        l_overlap: Primitive-overlap loss scalar.
        l_fidelity: Data-fidelity loss scalar.
        l_temporal: Temporal-coherence loss scalar.

    Returns:
        Scalar tensor.
    """
    return (
        weights.alpha * l_wmse
        + weights.beta * l_overlap
        + weights.gamma * l_fidelity
        + weights.lambda_ * l_temporal
    )


def compute_additive_density(
    renderer: DifferentiableRenderer,
    canvas_h: int,
    canvas_w: int,
) -> torch.Tensor:
    """SUM-based sprite compositing for overlap detection (D-03 helper).

    Replicates the renderer's per-sprite warp logic (affine_grid +
    grid_sample with the same rotation clamping and scale softplus) but
    **sums** warped sprite contributions instead of using alpha-over.
    This means the output can exceed 1.0 wherever sprites overlap,
    which is exactly what L_overlap needs to detect.

    Accesses renderer private state:
        - renderer._sprites  (list of (1, 1, H_i, W_i) tensors)
        - renderer.params    (nn.Parameter, shape (N, 4))
        - renderer._device   (torch.device)

    Args:
        renderer: A DifferentiableRenderer instance (must have at least
            one sprite).
        canvas_h: Target canvas height in pixels.
        canvas_w: Target canvas width in pixels.

    Returns:
        (1, 1, canvas_h, canvas_w) float32 tensor. Values may exceed 1.0
        at pixels covered by more than one sprite.
    """
    additive = torch.zeros(
        1, 1, canvas_h, canvas_w,
        device=renderer._device,
        dtype=torch.float32,
    )

    for i, sprite in enumerate(renderer._sprites):
        y_i, x_i, s_i, theta_i = renderer.params[i]

        # Same rotation clamping as DifferentiableRenderer.forward() (D-09)
        theta_i = torch.remainder(theta_i + math.pi, 2 * math.pi) - math.pi

        # Same scale soft-clamp: softplus(s - 0.01) + 0.01 (Codex post-fix)
        s_i = torch.nn.functional.softplus(s_i - 0.01) + 0.01

        # NDC normalisation (align_corners=False convention, Codex Fix 2)
        x_n = ((2.0 * x_i + 1.0) / canvas_w) - 1.0
        y_n = ((2.0 * y_i + 1.0) / canvas_h) - 1.0

        cos_t = torch.cos(theta_i)
        sin_t = torch.sin(theta_i)
        inv_s = 1.0 / s_i

        # Target-to-source affine matrix (same as renderer forward, D-16)
        a11 = inv_s * cos_t
        a12 = inv_s * sin_t
        a21 = -inv_s * sin_t
        a22 = inv_s * cos_t
        tx = -(a11 * x_n + a12 * y_n)
        ty = -(a21 * x_n + a22 * y_n)

        theta_mat = torch.stack([a11, a12, tx, a21, a22, ty]).reshape(1, 2, 3)

        grid = F.affine_grid(
            theta_mat, [1, 1, canvas_h, canvas_w], align_corners=False,
        )
        warped = F.grid_sample(
            sprite, grid,
            mode="bilinear", padding_mode="zeros", align_corners=False,
        )

        # SUM instead of alpha-over — allows values to exceed 1.0
        additive = additive + warped

    return additive
```

### packages/engine/src/aerocloud/optimizer/convergence.py

```python
"""Convergence detection for the inner-loop optimizer (Phase 6).

Implements rolling-window plateau detection per D-14/D-15 of the
AeroCloud Blueprint.
"""

from __future__ import annotations


def check_convergence(
    loss_history: list[float],
    window: int = 10,
    epsilon: float = 0.001,
) -> bool:
    """Detect a loss plateau using a rolling window.

    Returns True if the relative range of the last ``window`` loss values
    is below ``epsilon``, indicating the optimizer has converged.

    The relative range is computed as::

        (max(window) - min(window)) / max(abs(max(window)), 1e-8)

    Args:
        loss_history: Recorded loss values, oldest first.
        window: Number of recent epochs to inspect.  Must be >= 2.
        epsilon: Convergence threshold for the relative range.

    Returns:
        True if converged, False if not enough data or range is too large.
    """
    if len(loss_history) < window:
        return False

    window_vals = loss_history[-window:]
    max_val = max(window_vals)
    min_val = min(window_vals)
    range_val = max_val - min_val
    scale = max(abs(max_val), 1e-8)
    return (range_val / scale) < epsilon
```

### packages/engine/src/aerocloud/optimizer/inner_loop.py

```python
"""InnerLoop: Coarse-to-Fine differentiable optimization pipeline (Phase 6).

Implements D-07..D-19 of the AeroCloud Blueprint:
- Adam optimizer with Blueprint parameters (INNER-06)
- Gradient clipping max_norm=1.0 (INNER-07)
- SDF downsampled per stage via bilinear interpolation (INNER-08)
- Convergence detection with early termination (INNER-09)
- Memory hygiene: detach for metrics, empty_cache, zero_grad set_to_none (INNER-10)
"""

from __future__ import annotations

import time

import numpy as np
import structlog
import torch
import torch.nn.functional as F  # noqa: N812
from torch.nn.utils import clip_grad_norm_

from aerocloud.models.optimizer import InnerLoopConfig, OptimizationResult
from aerocloud.optimizer.convergence import check_convergence
from aerocloud.optimizer.loss import (
    compute_additive_density,
    compute_l_fidelity,
    compute_l_overlap,
    compute_l_temporal,
    compute_l_wmse,
    compute_total_loss,
)
from aerocloud.renderer._renderer import DifferentiableRenderer

logger = structlog.get_logger(__name__)


def _downsample_sdf(
    sdf_full: torch.Tensor,
    target_h: int,
    target_w: int,
) -> torch.Tensor:
    """Downsample SDF tensor to target resolution.

    Returns the input unchanged if it already matches target_h x target_w.
    Otherwise uses bilinear interpolation (D-13).

    Args:
        sdf_full: (1, 1, H, W) float32 SDF tensor.
        target_h: Target height in pixels.
        target_w: Target width in pixels.

    Returns:
        (1, 1, target_h, target_w) float32 tensor.
    """
    if sdf_full.shape[-2] == target_h and sdf_full.shape[-1] == target_w:
        return sdf_full
    return F.interpolate(
        sdf_full,
        size=(target_h, target_w),
        mode="bilinear",
        align_corners=False,
    )


def _build_stage_schedule(
    base_resolutions: list[int],
    target: int,
) -> list[int]:
    """Build the Coarse-to-Fine resolution schedule (Assumption A2).

    Filters base_resolutions to only keep values strictly less than target,
    then appends target. If target is <= the smallest base resolution,
    returns [target] only.

    Args:
        base_resolutions: Candidate stage resolutions (e.g. [8, 32, 128]).
        target: Target (full) resolution.

    Returns:
        Ordered list of resolutions ending with target.
    """
    filtered = [r for r in base_resolutions if r < target]
    filtered.append(target)
    return filtered


class InnerLoop:
    """Coarse-to-Fine differentiable optimization loop (D-19).

    Ties together loss functions, convergence detection, and the
    DifferentiableRenderer into a complete optimization pipeline.

    The public API is ``optimize() -> OptimizationResult``, which is what
    Phase 9 MAP-Elites will consume.

    Args:
        renderer: DifferentiableRenderer instance to optimize. Its ``.params``
            is the optimization target.
        sdf: Signed distance field for the target silhouette. Can be a
            numpy array or a (1, 1, H, W) torch.Tensor. Positive inside,
            negative outside.
        ref_weights: (N,) float32 reference scale vector from Phase 3 NLP.
            Used in L_fidelity to prevent artificial scale inflation.
        config: Optimization configuration. Defaults to InnerLoopConfig().
    """

    def __init__(
        self,
        renderer: DifferentiableRenderer,
        sdf: np.ndarray[tuple[int, ...], np.dtype[np.float32]] | torch.Tensor,
        ref_weights: torch.Tensor,
        config: InnerLoopConfig | None = None,
    ) -> None:
        self._renderer = renderer
        self._config = config if config is not None else InnerLoopConfig()

        # Convert numpy SDF to torch (1, 1, H, W) float32 on renderer._device
        if isinstance(sdf, np.ndarray):
            sdf_tensor = torch.from_numpy(sdf.astype(np.float32))
        else:
            sdf_tensor = sdf.float()

        # Ensure shape is (1, 1, H, W)
        if sdf_tensor.ndim == 2:
            sdf_tensor = sdf_tensor.unsqueeze(0).unsqueeze(0)
        elif sdf_tensor.ndim == 3:
            sdf_tensor = sdf_tensor.unsqueeze(0)

        self._sdf_full: torch.Tensor = sdf_tensor.to(renderer._device)

        # Store ref_weights detached on renderer._device
        self._ref_weights: torch.Tensor = ref_weights.detach().to(renderer._device)

        # Target resolution from SDF shape
        self._target_h: int = sdf_tensor.shape[-2]
        self._target_w: int = sdf_tensor.shape[-1]

    def optimize(self) -> OptimizationResult:
        """Run the full Coarse-to-Fine optimization pipeline.

        Builds the stage schedule, runs Adam with gradient clipping at each
        stage, carries params between stages (warm-start), and detects
        convergence via rolling-window plateau detection.

        Returns:
            OptimizationResult with final params, per-stage loss histories,
            total epochs, convergence flags, and wall-clock time.
        """
        wall_start = time.perf_counter()
        config = self._config
        renderer = self._renderer

        # Build resolution schedule (Assumption A2: filter >= target)
        target = max(self._target_h, self._target_w)
        schedule = _build_stage_schedule(
            list(config.stage_resolutions),
            target,
        )

        stage_loss_histories: list[list[float]] = []
        convergence_flags: list[bool] = []
        total_epochs = 0

        for stage_idx, res in enumerate(schedule):
            stage_h = res
            stage_w = res

            # Downsample SDF for this stage
            sdf_stage = _downsample_sdf(self._sdf_full, stage_h, stage_w)

            # Snapshot initial params for L_temporal
            params_initial = renderer.params.detach().clone()

            # Create fresh Adam optimizer for this stage (warm-start: params carry over)
            optimizer = torch.optim.Adam(
                [renderer.params],
                lr=config.lr,
                betas=(0.9, 0.999),
                eps=1e-8,
            )

            loss_history: list[float] = []
            stage_converged = False

            for epoch in range(config.max_epochs):
                optimizer.zero_grad(set_to_none=True)

                # Forward pass: alpha-over density
                density = renderer.forward(stage_h, stage_w)

                # Additive density for overlap detection (D-03)
                additive = compute_additive_density(renderer, stage_h, stage_w)

                # Compute all 4 losses
                l_wmse = compute_l_wmse(density, sdf_stage)
                l_overlap = compute_l_overlap(additive)
                l_fidelity = compute_l_fidelity(self._ref_weights, renderer.params)
                l_temporal = compute_l_temporal(renderer.params, params_initial)

                l_total = compute_total_loss(
                    config.weights, l_wmse, l_overlap, l_fidelity, l_temporal
                )

                l_total.backward()  # type: ignore[no-untyped-call]

                # Gradient clipping (D-08)
                clip_grad_norm_([renderer.params], max_norm=1.0)

                optimizer.step()

                # Record loss (detached — never retain graph for logging)
                loss_val = l_total.detach().item()
                loss_history.append(loss_val)

                total_epochs += 1

                # Check convergence after min warmup epochs
                if epoch >= config.min_epochs_before_convergence and check_convergence(
                    loss_history,
                    window=config.convergence_window,
                    epsilon=config.convergence_epsilon,
                ):
                    stage_converged = True
                    break

            stage_loss_histories.append(loss_history)
            convergence_flags.append(stage_converged)

            logger.info(
                "inner_loop.stage_complete",
                stage=stage_idx,
                resolution=res,
                epochs=len(loss_history),
                converged=stage_converged,
                final_loss=loss_history[-1] if loss_history else float("nan"),
            )

            # Memory hygiene: release GPU cache between stage transitions (D-17)
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

---

## Expected Output Format

Please provide your review as:

```
## Codex Review: Phase 6 Inner Loop-v1

### Performance Analysis
[Answer questions 1-2]

### Memory Analysis
[Answer question 3]

### Correctness Analysis
[Answer questions 4-5]

### S-1..S-8: Security Checks
[Each check with verdict and reasoning]

### L-1..L-8: Stability Checks
[Each check with verdict and reasoning]

### A-1..A-5: Architecture Checks
[Each check with verdict and reasoning]

### Summary
[APPROVED / APPROVED-WITH-FIXES / BLOCKED with list of must-fix items]
```

---

*Prepared for Codex review | Phase 06-inner-loop-v1 | 2026-04-14*

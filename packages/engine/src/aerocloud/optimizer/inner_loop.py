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


_MIN_RESOLUTION: int = 8


def _build_stage_schedule(
    base_resolutions: list[int],
    target: int,
) -> list[int]:
    """Build the Coarse-to-Fine resolution schedule (Assumption A2).

    Filters base_resolutions to only keep values strictly less than target,
    then appends target. Enforces a minimum resolution of 8px to prevent
    optimizer collapse at ultra-low resolutions (F-7).

    Args:
        base_resolutions: Candidate stage resolutions (e.g. [8, 32, 128]).
        target: Target (full) resolution.

    Returns:
        Ordered list of resolutions ending with target.
    """
    safe_target = max(target, _MIN_RESOLUTION)
    filtered = [r for r in base_resolutions if r < safe_target]
    filtered.append(safe_target)
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

        # Validate ref_weights shape against renderer params (F-6)
        n_params = renderer.params.shape[0]
        if ref_weights.shape[0] != n_params:
            msg = (
                f"ref_weights length {ref_weights.shape[0]} does not match "
                f"renderer params count {n_params}. "
                "Must have one weight per word."
            )
            raise ValueError(msg)

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

        # Build resolution schedule preserving aspect ratio (F-2 fix)
        target_long = max(self._target_h, self._target_w)
        aspect = self._target_w / self._target_h if self._target_h > 0 else 1.0
        schedule = _build_stage_schedule(
            list(config.stage_resolutions),
            target_long,
        )

        stage_loss_histories: list[list[float]] = []
        convergence_flags: list[bool] = []
        total_epochs = 0

        for stage_idx, res in enumerate(schedule):
            # Preserve aspect ratio: scale both dims proportionally (F-2)
            if self._target_h >= self._target_w:
                stage_h = res
                stage_w = max(_MIN_RESOLUTION, round(res * aspect))
            else:
                stage_w = res
                stage_h = max(_MIN_RESOLUTION, round(res / aspect))

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

                # Single forward pass returns both alpha-over density and
                # additive density (D-20 / F-3 fix — no double forward pass)
                density, additive = renderer.forward(stage_h, stage_w, mode="both")

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
            params=renderer.params.detach().clone(),
            stage_loss_histories=stage_loss_histories,
            total_epochs=total_epochs,
            convergence_flags=convergence_flags,
            wall_clock_s=wall_clock_s,
        )

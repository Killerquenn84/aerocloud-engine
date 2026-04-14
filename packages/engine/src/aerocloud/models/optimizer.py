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

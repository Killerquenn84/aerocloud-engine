"""SelfPlayConfig: frozen Pydantic model for self-play hyperparameters (Phase 10, SP-01).

Design decisions:
    D-06: All mutation/dominance/monitoring parameters in a single frozen model.
    - Frozen + strict + extra=forbid prevents silent parameter drift at runtime.
    - Positive constraints on sigma fields prevent zero-variance mutations.
    - dominance_margin >= 0 allows zero-margin (accept any improvement).
    - kl_n_bins >= 2 required for meaningful KL-divergence estimation.

Security:
    T-10-01: DSN never stored here; config carries only algorithm hyperparameters.
    T-10-02: Config values are algorithmic scalars; no SQL construction here.
"""

from __future__ import annotations

from pydantic import Field

from aerocloud.models.base import AeroCloudBase


class SelfPlayConfig(AeroCloudBase):
    """Configuration for the nightly self-play training loop.

    All fields have validated defaults matching the AeroCloud Blueprint
    recommendations for MAP-Elites self-improvement (Phase 10, D-06).

    Fields:
        n_iterations: Number of mutation/evaluation iterations per nightly run.
        soft_time_limit: Celery soft time limit in seconds (8 hours default).
        dominance_margin: Minimum fitness improvement to accept a mutant
            (>=0; 0 means accept any strict improvement).
        sigma_xy: Gaussian mutation std for (x, y) position (>0 required).
        sigma_scale: Gaussian mutation std for word scale factor (>0 required).
        sigma_theta: Gaussian mutation std for rotation theta in radians (>0).
        crossover_p: Probability of crossover vs pure mutation in [0, 1].
        kl_threshold: KL-divergence threshold for distribution shift detection (>0).
        kl_n_bins: Number of histogram bins for KL-divergence estimation (>=2).
        mutation_ratio: Fraction of iterations using mutation vs crossover (0-1).
    """

    n_iterations: int = Field(default=1000, gt=0)
    soft_time_limit: int = Field(default=28800, gt=0)
    dominance_margin: float = Field(default=0.01, ge=0)
    sigma_xy: float = Field(default=0.05, gt=0)
    sigma_scale: float = Field(default=0.02, gt=0)
    sigma_theta: float = Field(default=0.1, gt=0)
    crossover_p: float = Field(default=0.5, ge=0.0, le=1.0)
    kl_threshold: float = Field(default=0.5, gt=0)
    kl_n_bins: int = Field(default=10, ge=2)
    mutation_ratio: float = Field(default=0.7, ge=0.0, le=1.0)

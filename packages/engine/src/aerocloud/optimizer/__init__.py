"""Inner Loop optimizer package (Phase 6).

Exports loss functions, convergence detection, and Pydantic models.
The InnerLoop class itself will be added in Plan 02.
"""

from aerocloud.models.optimizer import InnerLoopConfig, LossWeights, OptimizationResult
from aerocloud.optimizer.convergence import check_convergence
from aerocloud.optimizer.loss import (
    compute_additive_density,
    compute_l_fidelity,
    compute_l_overlap,
    compute_l_temporal,
    compute_l_wmse,
    compute_total_loss,
)

__all__ = [
    "InnerLoopConfig",
    "LossWeights",
    "OptimizationResult",
    "check_convergence",
    "compute_additive_density",
    "compute_l_fidelity",
    "compute_l_overlap",
    "compute_l_temporal",
    "compute_l_wmse",
    "compute_total_loss",
]

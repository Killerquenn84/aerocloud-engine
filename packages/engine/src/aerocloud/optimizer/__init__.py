"""Inner Loop optimizer package (Phase 6).

Exports loss functions, convergence detection, Pydantic models, and InnerLoop.
"""

from aerocloud.models.optimizer import InnerLoopConfig, LossWeights, OptimizationResult
from aerocloud.optimizer.convergence import check_convergence
from aerocloud.optimizer.inner_loop import InnerLoop
from aerocloud.optimizer.loss import (
    compute_additive_density,
    compute_l_fidelity,
    compute_l_overlap,
    compute_l_temporal,
    compute_l_wmse,
    compute_total_loss,
)

__all__ = [
    "InnerLoop",
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

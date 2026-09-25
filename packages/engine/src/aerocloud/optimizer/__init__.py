"""Inner Loop optimizer package (Phase 6 / Phase 7 D-21 refactor).

Exports loss functions, convergence detection, Pydantic models, and InnerLoop.

Phase 7 / D-21: ``compute_additive_density`` has been removed from loss.py
and from this public API.  The renderer now produces both density outputs in
a single forward pass via ``mode='both'`` (fixes F-3 and F-10).
"""

from aerocloud.models.optimizer import InnerLoopConfig, LossWeights, OptimizationResult
from aerocloud.optimizer.convergence import check_convergence
from aerocloud.optimizer.inner_loop import InnerLoop
from aerocloud.optimizer.loss import (
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
    "compute_l_fidelity",
    "compute_l_overlap",
    "compute_l_temporal",
    "compute_l_wmse",
    "compute_total_loss",
]

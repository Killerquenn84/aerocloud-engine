"""Sinkhorn-Knopp Optimal Transport with adaptive epsilon regularization (Phase 8, SEM-05, SEM-06).

Implements the word-to-canvas-position transport plan using the POT library
in log-space (method='sinkhorn_log') for numerical stability on degenerate
distributions (D-07).

Design decisions:
    D-07: Use ot.sinkhorn with method='sinkhorn_log' to avoid NaN on degenerate
        distributions. Log-space arithmetic prevents underflow.
    D-08: Uniform marginals a = b = ones(N)/N (each word maps to full mass,
        each position receives full mass). This encodes the word-to-position
        1:1 assignment prior.
    D-09: Adaptive epsilon:
        - Clamp initial eps to [1e-4, 1.0] before first call.
        - If Sinkhorn converges in < 10 iterations → eps_used = max(1e-4, eps/2)
          (eps was too large; halve for sharper transport on next call).
        - If Sinkhorn takes > 500 iterations → eps_used = min(1.0, eps*2)
          (eps was too small; double to improve convergence speed).
        - Otherwise eps_used = eps (no change).
    D-10: Convergence is O(log(1/eps)) independent of N (arXiv:2604.03787).
        max_iter caps worst-case runtime for T-08-05 DoS protection.
    T-08-05: max_iter bounds Sinkhorn compute time (DoS mitigation).
    T-08-06: SinkhornNonConvergenceError message contains eps + niter only,
        not user-provided data.

References:
    - .planning/phases/08-semantic-vector-space/08-03-PLAN.md
    - .planning/phases/08-semantic-vector-space/08-RESEARCH.md §D-07 to D-10
    - AeroCloud Blueprint Teil II §2.2 (Sinkhorn-Knopp)
"""

from __future__ import annotations

import numpy as np
import ot
import structlog

from aerocloud.config import settings
from aerocloud.models.semantic import TransportPlan
from aerocloud.semantic.errors import SemanticError, SinkhornNonConvergenceError

logger = structlog.get_logger(__name__)

# Epsilon regularization bounds (D-09).
_EPS_MIN: float = 1e-4
_EPS_MAX: float = 1.0

# Adaptive threshold boundaries (D-09).
_FAST_CONVERGE_THRESHOLD: int = 10  # halve eps if niter < this
_SLOW_CONVERGE_THRESHOLD: int = 500  # double eps if niter > this


def compute_transport(
    cost_matrix: np.ndarray,
    eps_init: float | None = None,
    max_iter: int | None = None,
) -> TransportPlan:
    """Compute optimal transport plan via Sinkhorn-Knopp in log-space (D-07).

    Uses uniform marginals: a = b = ones(N)/N (D-08 word-to-position 1:1 mapping).
    Adaptive epsilon per D-09: halve if niter < 10, double if niter > 500.
    Epsilon is clamped to [1e-4, 1.0] before the Sinkhorn call.

    Convergence guarantee: O(log(1/eps)) independent of dimension (D-10,
    arXiv:2604.03787). max_iter caps worst-case runtime (T-08-05 DoS protection).

    Args:
        cost_matrix: (N, N) float array of pairwise costs (e.g., 1 - cosine_similarity).
            Must be square with N >= 1.
        eps_init: Initial regularization epsilon. Defaults to settings.sinkhorn_eps_init.
            Clamped to [1e-4, 1.0] before use.
        max_iter: Maximum Sinkhorn iterations. Defaults to settings.sinkhorn_max_iter.
            Guards against infinite loops (T-08-05).

    Returns:
        TransportPlan with:
        - transport_matrix: (N, N) float64, doubly stochastic (rows/cols sum to 1/N)
        - eps_used: Adapted epsilon for the next call (caller can reuse for warmup)
        - iterations: Number of Sinkhorn iterations performed

    Raises:
        SemanticError: If cost_matrix is not a 2D square array with N > 0.
        SinkhornNonConvergenceError: If Sinkhorn output contains NaN after max_iter.

    Example:
        >>> import numpy as np
        >>> rng = np.random.default_rng(42)
        >>> cost = rng.uniform(0.0, 1.0, size=(5, 5))
        >>> plan = compute_transport(cost)
        >>> plan.transport_matrix.shape
        (5, 5)
        >>> np.allclose(plan.transport_matrix.sum(axis=1), np.ones(5) / 5, atol=1e-4)
        True
    """
    eps = eps_init if eps_init is not None else settings.sinkhorn_eps_init
    max_iter = max_iter if max_iter is not None else settings.sinkhorn_max_iter

    # Validate cost_matrix (SemanticError — not user data, just shape guard).
    if cost_matrix.ndim != 2 or cost_matrix.shape[0] != cost_matrix.shape[1]:
        raise SemanticError(f"cost_matrix must be square 2D (N, N), got shape {cost_matrix.shape}")
    n = cost_matrix.shape[0]
    if n == 0:
        raise SemanticError("cost_matrix must have N > 0, got empty matrix")

    # D-09: Clamp initial epsilon to valid range before any computation.
    eps = float(np.clip(eps, _EPS_MIN, _EPS_MAX))

    # D-08: Uniform marginals — each word and each canvas position has equal prior mass.
    a = np.ones(n, dtype=np.float64) / n
    b = np.ones(n, dtype=np.float64) / n
    m = cost_matrix.astype(np.float64)  # cost matrix (conventional M notation)

    # D-07: Log-space Sinkhorn avoids underflow on degenerate distributions.
    transport_mat, log_dict = ot.sinkhorn(
        a,
        b,
        m,
        reg=eps,
        method="sinkhorn_log",
        numItermax=max_iter,
        log=True,
    )

    niter: int = int(log_dict.get("niter", max_iter))

    # T-08-06: Error message contains eps + niter only, not cost_matrix values.
    if np.any(np.isnan(transport_mat)):
        raise SinkhornNonConvergenceError(
            f"Sinkhorn produced NaN after {niter} iterations with eps={eps:.2e}"
        )

    # D-09: Adaptive epsilon adjustment for caller's next call.
    eps_adapted = eps
    if niter < _FAST_CONVERGE_THRESHOLD:
        # Converged too quickly → eps was too large → halve it (sharper transport).
        eps_adapted = max(_EPS_MIN, eps / 2.0)
    elif niter > _SLOW_CONVERGE_THRESHOLD:
        # Converged too slowly → eps was too small → double it (faster convergence).
        eps_adapted = min(_EPS_MAX, eps * 2.0)

    logger.info(
        "semantic.transport.complete",
        n=n,
        eps_init=eps,
        eps_adapted=eps_adapted,
        niter=niter,
    )

    return TransportPlan(
        transport_matrix=transport_mat,
        eps_used=eps_adapted,
        iterations=niter,
    )

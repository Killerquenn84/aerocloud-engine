"""Distribution-shift monitoring via KL divergence (Plan 10-03, Task 1, SP-07).

Implements compute_kl_divergence using 4 marginal 1D histograms.

CRITICAL RESEARCH CORRECTION: Uses 4 INDEPENDENT 1D histograms, NOT a joint 4D
histogramdd. The joint 4D approach gives KL ~ 11.5 for identical uniform
distributions (a false alarm), while marginal 1D histograms correctly give
KL ~ 0.0.

Algorithm (Pattern 6 from 10-RESEARCH.md):
    For each of the 4 behavioral descriptor dimensions:
        1. Compute 1D histogram over range [0.0, 1.0] with n_bins bins.
        2. Add eps=1e-8 smoothing to prevent log(0).
        3. Normalize to obtain probability distribution p (prev) and q (curr).
        4. Compute KL(p || q) = sum(rel_entr(p, q)) using scipy.special.rel_entr.
    Sum the 4 per-dimension KL values.

Design decisions:
    D-07 (SP-07): KL threshold = 0.5 triggers structlog warning.
    D-06: kl_n_bins and kl_threshold come from SelfPlayConfig.

Security:
    T-10-09 (Repudiation): distribution shift logged as structlog warning, not silent.
"""

from __future__ import annotations

import numpy as np
import structlog
from scipy.special import rel_entr

logger = structlog.get_logger(__name__)

_EPS: float = 1e-8


def compute_kl_divergence(
    descriptors_prev: np.ndarray,
    descriptors_curr: np.ndarray,
    n_bins: int = 10,
) -> float:
    """Compute KL divergence between two sets of behavioral descriptors.

    Uses 4 marginal 1D histograms (one per BD dimension) over [0.0, 1.0].
    Sums the 4 per-dimension KL values to produce a scalar shift indicator.

    CRITICAL: Does NOT use np.histogramdd (joint 4D). Joint 4D histogram on
    uniform samples gives KL ~ 11.5 (false alarm); marginal gives ~ 0.0.

    Args:
        descriptors_prev: ndarray of shape (n, 4) — previous night's descriptors.
        descriptors_curr: ndarray of shape (m, 4) — current night's descriptors.
        n_bins: Number of histogram bins per dimension (default 10).

    Returns:
        Total KL divergence as a Python float (sum of 4 per-dimension KL values).
    """
    total_kl: float = 0.0

    for dim in range(4):
        # Extract 1D marginal for this dimension
        prev_dim = descriptors_prev[:, dim]
        curr_dim = descriptors_curr[:, dim]

        # Compute 1D histograms over [0.0, 1.0] range
        hist_prev, _ = np.histogram(prev_dim, bins=n_bins, range=(0.0, 1.0))
        hist_curr, _ = np.histogram(curr_dim, bins=n_bins, range=(0.0, 1.0))

        # Convert to float for arithmetic
        p = hist_prev.astype(np.float64) + _EPS
        q = hist_curr.astype(np.float64) + _EPS

        # Normalize to probability distributions
        p /= p.sum()
        q /= q.sum()

        # KL divergence: sum(p * log(p/q)) using scipy's numerically stable rel_entr
        kl_dim = float(rel_entr(p, q).sum())
        total_kl += kl_dim

    return float(total_kl)


def check_distribution_shift(
    kl_value: float,
    threshold: float = 0.5,
) -> bool:
    """Check whether KL divergence exceeds the distribution-shift threshold.

    Logs a structlog warning when a shift is detected (T-10-09 mitigation).

    Args:
        kl_value:  KL divergence value from compute_kl_divergence.
        threshold: Alert threshold (default 0.5 per SelfPlayConfig.kl_threshold).

    Returns:
        True if kl_value > threshold (shift detected), False otherwise.
    """
    alert = kl_value > threshold
    if alert:
        logger.warning(
            "self_play.monitoring.distribution_shift_detected",
            kl_value=kl_value,
            threshold=threshold,
        )
    return alert

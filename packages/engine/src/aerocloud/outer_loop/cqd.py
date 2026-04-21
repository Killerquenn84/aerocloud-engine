"""CQD (Continuous Quality-Diversity) score — vectorized Monte-Carlo computation.

The CQD metric evaluates the quality-diversity tradeoff across an entire archive
by integrating over uniformly-sampled reference points in the behavior space.

Mathematical definition (Blueprint Teil VIII, D-06):
    omega(x, G, theta) = f(x)/|f_max - f_min| - theta * delta(g(x), G) / delta_max
    CQD = (1/N*M) * sum_n sum_m omega(x^r, G_n, theta_m)

    where:
        x^r   = nearest archive elite to reference point G_n
        f(x)  = fitness of that elite (normalized to [0,1])
        delta = Euclidean distance from ref point to nearest elite
        delta_max = sqrt(4) = 2.0  (max diagonal in [0,1]^4 behavior space)
        theta = balance parameter in [0,1] (0=pure quality, 1=quality-penalized-by-distance)
        N     = n_samples (number of random reference points)
        M     = n_theta (number of theta values, default 51 per D-07)

Theta-sweep curve (D-07):
    51 evenly-spaced theta values in [0.0, 1.0], smoothed with a running-average
    window of 3 (np.convolve with kernel [1/3, 1/3, 1/3], mode='same').

Performance:
    sklearn NearestNeighbors(algorithm='ball_tree') for O(n log n) NN search.
    Vectorized omega matrix [n_samples, n_theta] for O(N*M) in one numpy op.
    Target: < 25ms for 500 elites x 10000 ref points (RESEARCH.md verified);
    contract: < 100ms (OUTER2-06).

Threat mitigations:
    T-11-04 (DoS): guard len(objectives) < 2 → return zeros immediately.
    Pitfall 4 (div-by-zero): f_range = max(f_max - f_min, 1e-8).

References:
    - .planning/phases/11-outer-loop-v2/11-02-PLAN.md
    - .planning/phases/11-outer-loop-v2/11-RESEARCH.md
    - D-06: CQD = (1/NM) * sum omega
    - D-07: 51 evenly-spaced theta, smoothed window=3
    - OUTER2-03, OUTER2-04, OUTER2-05, OUTER2-06
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from pydantic import field_validator
from sklearn.neighbors import NearestNeighbors

from aerocloud.models.base import AeroCloudBase

if TYPE_CHECKING:
    from aerocloud.outer_loop.archive import ArchiveWrapper


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Behavior space: [0, 1]^4 — maximum Euclidean distance is sqrt(4) = 2.0
_DELTA_MAX: float = math.sqrt(4.0)

# Running-average smoothing window size (D-07)
_SMOOTH_WINDOW: int = 3

# Default number of theta values (D-07: 51 evenly-spaced in [0.0, 1.0])
_DEFAULT_N_THETA: int = 51

# Default number of Monte-Carlo reference points
_DEFAULT_N_SAMPLES: int = 10_000

# Default reproducibility seed (OUTER2-05)
_DEFAULT_SEED: int = 42

# Minimum elites required for a non-trivial CQD (T-11-04 guard)
_MIN_ELITES: int = 2


# ---------------------------------------------------------------------------
# CQDResult Pydantic model
# ---------------------------------------------------------------------------


class CQDResult(AeroCloudBase):
    """Immutable result of a CQD computation.

    Attributes:
        cqd:         Aggregate CQD score. Positive = good quality-diversity tradeoff.
                     Can be negative when distance penalty dominates.
        theta_curve: 51-element list of per-theta CQD values, smoothed with
                     running-average window=3 (D-07). First element = theta=0.0
                     (pure quality), last element = theta=1.0 (full penalty).
    """

    cqd: float
    theta_curve: list[float]

    @field_validator("theta_curve")
    @classmethod
    def _validate_theta_curve(cls, v: list[float]) -> list[float]:
        """Validate that theta_curve elements are finite floats."""
        for val in v:
            if not math.isfinite(val):
                raise ValueError(f"theta_curve contains non-finite value: {val}")
        return v


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------


def compute_cqd(
    objectives: np.ndarray,
    measures: np.ndarray,
    n_samples: int = _DEFAULT_N_SAMPLES,
    n_theta: int = _DEFAULT_N_THETA,
    seed: int = _DEFAULT_SEED,
) -> CQDResult:
    """Compute the CQD metric over a set of archive elites.

    The function operates on raw numpy arrays so it can be tested and used
    independently of ArchiveWrapper. See ``compute_cqd_from_archive()`` for
    the thin wrapper that extracts data from an ArchiveWrapper.

    Args:
        objectives: 1D array of shape (n_elites,) with fitness values.
        measures:   2D array of shape (n_elites, 4) with behavioral descriptors
                    in [0, 1]^4.
        n_samples:  Number of random reference points drawn from Uniform([0,1]^4).
                    Default 10000. Cap at 100000 (T-11-04 soft guidance).
        n_theta:    Number of theta values in [0.0, 1.0]. Default 51 (D-07).
        seed:       RNG seed for reproducible Monte-Carlo sampling (OUTER2-05).
                    Same seed + same archive → bit-exact identical CQD.

    Returns:
        CQDResult with aggregate ``cqd`` score and 51-element ``theta_curve``.

    Notes:
        - If len(objectives) < 2, returns CQDResult(cqd=0.0, theta_curve=[0.0]*51).
          This is the T-11-04 / D-guard for empty or trivial archives.
        - Pitfall 4: f_range = max(f_max - f_min, 1e-8) prevents div-by-zero
          when all elites have identical fitness.
    """
    n_elites = len(objectives)
    zero_result = CQDResult(cqd=0.0, theta_curve=[0.0] * n_theta)

    # T-11-04 guard: trivial archives cannot produce meaningful diversity score
    if n_elites < _MIN_ELITES:
        return zero_result

    # ---- Normalize fitness ----
    f_min: float = float(np.min(objectives))
    f_max: float = float(np.max(objectives))
    f_range: float = max(f_max - f_min, 1e-8)  # Pitfall 4: prevent div-by-zero

    # ---- Sample random reference points in [0, 1]^4 ----
    # Fixed seed per OUTER2-05: np.random.default_rng is state-isolated
    rng = np.random.default_rng(seed)
    ref_points: np.ndarray = rng.uniform(0.0, 1.0, size=(n_samples, 4))

    # ---- Nearest-neighbor search (ball_tree for O(n log n) performance) ----
    nn = NearestNeighbors(n_neighbors=1, algorithm="ball_tree", metric="euclidean")
    nn.fit(measures)
    distances, indices = nn.kneighbors(ref_points)  # both shape (n_samples, 1)

    nearest_distances: np.ndarray = distances[:, 0]  # shape (n_samples,)
    nearest_indices: np.ndarray = indices[:, 0]  # shape (n_samples,)

    # ---- Normalized fitness and distance for each ref point's nearest elite ----
    nearest_objectives: np.ndarray = objectives[nearest_indices]  # (n_samples,)
    f_norm: np.ndarray = (nearest_objectives - f_min) / f_range  # (n_samples,)
    delta_norm: np.ndarray = nearest_distances / _DELTA_MAX  # (n_samples,)

    # ---- Vectorized omega matrix [n_samples, n_theta] ----
    # omega(x, G, theta) = f_norm(x) - theta * delta_norm(x)
    thetas: np.ndarray = np.linspace(0.0, 1.0, n_theta)  # shape (n_theta,)
    omega: np.ndarray = (
        f_norm[:, None] - thetas[None, :] * delta_norm[:, None]
    )  # shape (n_samples, n_theta)

    # ---- Aggregate CQD score (D-06): mean over all samples and all theta ----
    cqd_scalar: float = float(np.mean(omega))

    # ---- Theta-curve: mean over samples for each theta (D-07) ----
    theta_curve_raw: np.ndarray = np.mean(omega, axis=0)  # shape (n_theta,)

    # ---- Smooth with running average window=3 (D-07) ----
    kernel = np.ones(_SMOOTH_WINDOW) / _SMOOTH_WINDOW
    theta_curve_smoothed: np.ndarray = np.convolve(theta_curve_raw, kernel, mode="same")

    return CQDResult(cqd=cqd_scalar, theta_curve=theta_curve_smoothed.tolist())


# ---------------------------------------------------------------------------
# Thin wrapper for ArchiveWrapper
# ---------------------------------------------------------------------------


def compute_cqd_from_archive(
    archive: ArchiveWrapper,
    n_samples: int = _DEFAULT_N_SAMPLES,
    n_theta: int = _DEFAULT_N_THETA,
    seed: int = _DEFAULT_SEED,
) -> CQDResult:
    """Convenience wrapper that extracts data from an ArchiveWrapper and calls compute_cqd().

    Args:
        archive:  ArchiveWrapper instance (from archive.py). Must have a .data() method
                  returning a dict with 'objective' and 'measures' arrays.
        n_samples: Passed through to compute_cqd().
        n_theta:   Passed through to compute_cqd().
        seed:      Passed through to compute_cqd().

    Returns:
        CQDResult from compute_cqd() on the archive's current elites.
    """
    data = archive.data()
    objectives = np.asarray(data["objective"], dtype=np.float64)
    measures = np.asarray(data["measures"], dtype=np.float64)
    return compute_cqd(objectives, measures, n_samples=n_samples, n_theta=n_theta, seed=seed)

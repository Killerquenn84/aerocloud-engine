"""Novelty search emitter, saturation monitoring, and elite re-evaluation.

Implements OUTER-06 (novelty + saturation) and OUTER-07 (re-evaluation)
to prevent archive stagnation and detect elite drift.

References:
    - 09-04-PLAN.md Task 1 + Task 2
    - D-12: BallTree k-NN for novelty computation (sklearn NearestNeighbors)
    - D-13: SaturationMonitor with 1% growth threshold over window
    - D-14: reeval_elites drift detection at 10% fitness drop
    - T-09-09: evaluate_fn timeout is caller's responsibility (documented)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import numpy as np
import structlog
from sklearn.neighbors import NearestNeighbors

from aerocloud.outer_loop.models import ReEvalResult

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Public API exports
# ---------------------------------------------------------------------------

__all__ = [
    "NoveltyGaussianEmitter",
    "SaturationMonitor",
    "compute_novelty",
    "reeval_elites",
]


# ---------------------------------------------------------------------------
# Novelty computation (D-12)
# ---------------------------------------------------------------------------


def compute_novelty(
    descriptor: np.ndarray,
    archive_descriptors: np.ndarray,
    k: int = 15,
) -> float:
    """Compute novelty score for a descriptor relative to the archive.

    Novelty is the mean Euclidean distance to the k nearest neighbors in
    descriptor space (BallTree, euclidean metric per D-12).

    Args:
        descriptor:          1D array of shape (dims,) — the query point.
        archive_descriptors: 2D array of shape (n_elites, dims).
        k:                   Number of nearest neighbors (default 15).

    Returns:
        float("inf") if the archive has fewer than k entries (everything
        novel — no reference population yet).
        Otherwise, mean k-NN euclidean distance (finite positive float).
    """
    n_elites = archive_descriptors.shape[0]
    if n_elites < k:
        return float("inf")

    nn = NearestNeighbors(n_neighbors=k, algorithm="ball_tree", metric="euclidean")
    nn.fit(archive_descriptors)
    distances, _ = nn.kneighbors(descriptor.reshape(1, -1))
    return float(np.mean(distances))


# ---------------------------------------------------------------------------
# Saturation monitoring (D-13)
# ---------------------------------------------------------------------------


class SaturationMonitor:
    """Tracks archive coverage history and detects plateau stagnation (D-13).

    A plateau is declared when the coverage growth over the last ``window``
    evaluations is less than 1% (< 0.01 in [0.0, 1.0] units).

    Args:
        window: Number of past coverage readings to inspect.
    """

    def __init__(self, window: int = 100) -> None:
        self._window: int = window
        self._history: list[float] = []

    def record(self, coverage: float) -> None:
        """Append the current archive coverage fraction to history.

        Args:
            coverage: Fraction of archive cells that contain at least one
                      elite, in [0.0, 1.0].
        """
        self._history.append(coverage)

    @property
    def is_plateaued(self) -> bool:
        """Return True if archive coverage growth is below 1% over the window.

        Returns False if history is shorter than window (not enough data).
        Logs a structured warning on the first plateau detection.
        """
        if len(self._history) < self._window:
            return False
        recent = self._history[-self._window :]
        growth = recent[-1] - recent[0]
        plateaued = growth < 0.01
        if plateaued:
            logger.warning(
                "Archive saturation detected",
                coverage=recent[-1],
                growth=growth,
                window=self._window,
            )
        return plateaued


# ---------------------------------------------------------------------------
# Novelty Gaussian Emitter (D-12 + D-13)
# ---------------------------------------------------------------------------


class NoveltyGaussianEmitter:
    """Wraps an ArchiveWrapper with novelty scoring and sigma boosting.

    The emitter computes batch novelty scores using a BallTree (built once
    per batch, not per solution) and boosts the exploration sigma when the
    archive is plateaued (D-13).

    Args:
        archive_wrapper: ArchiveWrapper instance providing archive.data().
        base_sigma:      Baseline Gaussian perturbation std dev.
        novelty_k:       k for k-NN novelty computation (D-12).
        sigma_boost:     Multiplier applied to base_sigma when plateaued.
    """

    def __init__(
        self,
        archive_wrapper: Any,
        base_sigma: float = 0.1,
        novelty_k: int = 15,
        sigma_boost: float = 2.0,
    ) -> None:
        self._archive_wrapper = archive_wrapper
        self._base_sigma = base_sigma
        self._novelty_k = novelty_k
        self._sigma_boost = sigma_boost

    def compute_batch_novelty(self, measures: np.ndarray) -> np.ndarray:
        """Compute novelty scores for a batch of behavioral descriptors.

        BallTree is built once per batch call (anti-pattern avoidance:
        do NOT rebuild per solution — D-12, Test 8).

        Args:
            measures: 2D array of shape (batch_size, descriptor_dims).

        Returns:
            1D array of novelty scores, shape (batch_size,).
            Entries are float("inf") if archive is too small (< k elites).
        """
        archive_data = self._archive_wrapper.data()
        archive_descriptors: np.ndarray = archive_data["measures"]
        n_elites = archive_descriptors.shape[0]

        if n_elites < self._novelty_k:
            return np.full(measures.shape[0], float("inf"))

        # Build BallTree once for the entire batch
        nn = NearestNeighbors(
            n_neighbors=self._novelty_k,
            algorithm="ball_tree",
            metric="euclidean",
        )
        nn.fit(archive_descriptors)

        distances, _ = nn.kneighbors(measures)
        return np.mean(distances, axis=1)  # type: ignore[no-any-return]

    def should_boost_exploration(self, saturation_monitor: SaturationMonitor) -> bool:
        """Return True if archive is plateaued (saturation_monitor.is_plateaued)."""
        return saturation_monitor.is_plateaued

    def get_effective_sigma(self, saturation_monitor: SaturationMonitor) -> float:
        """Return the effective sigma for the next ask() batch.

        Returns base_sigma * sigma_boost when plateaued, else base_sigma.

        Args:
            saturation_monitor: SaturationMonitor with history.

        Returns:
            Effective sigma float.
        """
        if self.should_boost_exploration(saturation_monitor):
            return self._base_sigma * self._sigma_boost
        return self._base_sigma


# ---------------------------------------------------------------------------
# Elite re-evaluation (D-14, OUTER-07)
# ---------------------------------------------------------------------------

EvaluateFn = Callable[[np.ndarray], Awaitable[tuple[float, np.ndarray]]]


async def reeval_elites(
    archive_wrapper: Any,
    evaluate_fn: EvaluateFn,
    top_n: int = 10,
    drift_threshold: float = 0.1,
) -> list[ReEvalResult]:
    """Re-evaluate the top-N elites and detect fitness drift (D-14, OUTER-07).

    Every ``reeval_every_n`` evaluations (caller controls timing), this
    function re-runs the fitness evaluation on the top-N elites and compares
    the new fitness against the archived value.

    This function does NOT modify the archive — the caller decides what to do
    with drifted elites (remove, re-add with new fitness, etc.). This keeps
    the function pure and testable.

    Security (T-09-09): evaluate_fn may be slow or raise exceptions.
    Callers must enforce per-call timeouts externally (e.g., asyncio.wait_for).

    Args:
        archive_wrapper:  ArchiveWrapper (or mock) with data() returning
                          {"solution", "objective", "measures"} arrays.
        evaluate_fn:      Async callable: solution (np.ndarray) → (fitness, measures).
        top_n:            How many top-fitness elites to re-evaluate.
        drift_threshold:  Drift fraction threshold (default 0.1 = 10%).

    Returns:
        list[ReEvalResult] — one per re-evaluated elite.
        Empty list if archive is empty.
    """
    archive_data = archive_wrapper.data()
    objectives: np.ndarray = archive_data["objective"]
    solutions: np.ndarray = archive_data["solution"]

    n_elites = objectives.shape[0]
    if n_elites == 0:
        return []

    # Sort by fitness descending, take top_n
    actual_top_n = min(top_n, n_elites)
    sorted_indices = np.argsort(objectives)[::-1][:actual_top_n]

    results: list[ReEvalResult] = []

    for rank, idx in enumerate(sorted_indices):
        solution = solutions[idx]
        fitness_before = float(objectives[idx])

        # Re-run evaluation (caller must wrap with timeout if needed — T-09-09)
        fitness_after_raw, _new_measures = await evaluate_fn(solution)
        fitness_after = float(fitness_after_raw)

        # drift_pct = (before - after) / (before + eps) — D-14
        drift_pct = (fitness_before - fitness_after) / (fitness_before + 1e-8)
        drifted = drift_pct > drift_threshold

        if drifted:
            logger.warning(
                "Elite drift detected",
                rank=rank,
                fitness_before=fitness_before,
                fitness_after=fitness_after,
                drift_pct=drift_pct,
            )

        results.append(
            ReEvalResult(
                bin_id=str(idx),
                fitness_before=fitness_before,
                fitness_after=fitness_after,
                drifted=drifted,
                drift_pct=drift_pct,
            )
        )

    return results

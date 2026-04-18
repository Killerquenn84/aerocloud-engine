"""MAP-Elites archive wrapper using pyribs GridArchive + GaussianEmitter.

References:
    - .planning/phases/09-outer-loop-v1/09-01-PLAN.md (Task 2)
    - D-01: GridArchive with 4 behavioral descriptor dimensions
    - D-02: bins_per_dim configurable (default 10)
    - D-03 correction: GaussianEmitter is the correct baseline emitter in pyribs 0.10.0
    - D-16: solution_dim = max_words * 4 (flattened (N,4) params tensor)
    - Pitfall 5: clamp measures to [0.0, 1.0] before tell()
    - T-09-02: validate solution shape at wrapper boundary
"""

from __future__ import annotations

import structlog
import numpy as np
from ribs.archives import GridArchive
from ribs.emitters import GaussianEmitter
from ribs.schedulers import Scheduler

from aerocloud.outer_loop.errors import SolutionDimMismatchError
from aerocloud.outer_loop.models import ArchiveConfig

logger = structlog.get_logger(__name__)


class ArchiveWrapper:
    """Wraps pyribs GridArchive + GaussianEmitter + Scheduler for MAP-Elites.

    The archive maintains a 4D grid over behavioral descriptors:
        [shape_fidelity, rotation_ratio, symmetry, semantic_clustering]
    Each dimension is bounded [0.0, 1.0].

    Solution representation: flattened (max_words, 4) params tensor
    (y, x, scale, rotation per word) → 1D vector of length max_words * 4.

    Args:
        config: ArchiveConfig with bins_per_dim, sigma, batch_size, max_words.
        seed:   Deterministic seed passed to GridArchive and GaussianEmitter.
    """

    NUM_DESCRIPTOR_DIMS: int = 4  # shape_fidelity, rotation_ratio, symmetry, semantic_clustering

    def __init__(self, config: ArchiveConfig, seed: int = 42) -> None:
        self._config = config
        # D-16: solution_dim is always max_words * 4 (padded to fixed length)
        self._solution_dim: int = config.max_words * 4

        # --- GridArchive (pyribs 0.10.0 API) ---
        self._archive: GridArchive = GridArchive(
            solution_dim=self._solution_dim,
            dims=[config.bins_per_dim] * self.NUM_DESCRIPTOR_DIMS,
            ranges=[(0.0, 1.0)] * self.NUM_DESCRIPTOR_DIMS,
            seed=seed,
        )

        # --- GaussianEmitter (pyribs 0.10.0 baseline emitter — D-03 correction) ---
        # x0 is the initial solution centre for the Gaussian perturbation.
        # We use a zero vector (neutral starting point — archive starts empty).
        _x0 = np.zeros(self._solution_dim)
        self._emitter: GaussianEmitter = GaussianEmitter(
            archive=self._archive,
            sigma=config.sigma,
            x0=_x0,
            batch_size=config.batch_size,
            seed=seed,
        )

        # --- Scheduler (RoundRobin with single emitter — simplest for v1) ---
        self._scheduler: Scheduler = Scheduler(
            archive=self._archive,
            emitters=[self._emitter],
        )

        logger.info(
            "ArchiveWrapper initialized",
            solution_dim=self._solution_dim,
            bins_per_dim=config.bins_per_dim,
            capacity=self.capacity,
            sigma=config.sigma,
            batch_size=config.batch_size,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def solution_dim(self) -> int:
        """Expected solution dimensionality: max_words * 4."""
        return self._solution_dim

    @property
    def coverage(self) -> float:
        """Fraction of archive cells that contain at least one elite [0.0, 1.0]."""
        cells = self._archive.cells
        if cells == 0:
            return 0.0
        return float(len(self._archive)) / cells

    @property
    def capacity(self) -> int:
        """Total number of cells in the archive (bins_per_dim^4)."""
        return int(self._archive.cells)

    @property
    def num_elites(self) -> int:
        """Current number of elites stored in the archive."""
        return len(self._archive)

    # ------------------------------------------------------------------
    # Ask / Tell interface
    # ------------------------------------------------------------------

    def ask(self) -> np.ndarray:
        """Request a batch of candidate solutions from the emitter.

        Returns:
            numpy array of shape (batch_size, solution_dim).
        """
        solutions: np.ndarray = self._scheduler.ask()
        return solutions

    def tell(self, objectives: np.ndarray, measures: np.ndarray) -> None:
        """Inform the archive about the quality of the last ask() solutions.

        Pitfall 5 mitigation: measures are clamped to [0.0, 1.0] before
        passing to the archive to guard against NaN/Inf/out-of-range values
        from the optimizer output.

        T-09-02 mitigation: validates objectives / measures shapes.

        Args:
            objectives: 1D array of fitness values (one per solution).
            measures:   2D array (batch_size, NUM_DESCRIPTOR_DIMS) of
                        behavioral descriptor values.
        """
        # Clamp behavioral descriptors to valid range (Pitfall 5, T-09-01)
        measures_clamped = np.clip(measures, 0.0, 1.0)
        # pyribs 0.10.0 Scheduler.tell() uses keyword 'objective' (singular)
        self._scheduler.tell(objective=objectives, measures=measures_clamped)
        logger.debug(
            "Archive tell()",
            n_solutions=len(objectives),
            num_elites=self.num_elites,
            coverage=self.coverage,
        )

    # ------------------------------------------------------------------
    # Retrieval helpers
    # ------------------------------------------------------------------

    def retrieve(self, measures: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Retrieve elite solutions at the given measure points.

        Args:
            measures: 2D array (n, NUM_DESCRIPTOR_DIMS) of behavioral coordinates.

        Returns:
            Tuple of (elites, objectives, status) arrays from GridArchive.retrieve().
        """
        return self._archive.retrieve(measures)  # type: ignore[return-value]

    def data(self) -> dict:  # type: ignore[type-arg]
        """Return the archive data dict for external iteration.

        Returns:
            Dict with 'solution', 'objective', 'measures' etc.
        """
        return self._archive.data()  # type: ignore[return-value]

    def best_elite(self) -> dict:  # type: ignore[type-arg]
        """Return the elite with the highest fitness.

        Returns:
            Dict with 'solution', 'objective', 'measures', etc.

        Raises:
            IndexError: if the archive is empty.
        """
        return self._archive.best_elite  # type: ignore[return-value]

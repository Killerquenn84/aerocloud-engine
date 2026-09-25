"""MAP-Elites archive wrapper using pyribs GridArchive + configurable emitter.

Phase 9: GaussianEmitter + Scheduler (baseline).
Phase 11: CappedBOPEmitter + BayesianOptimizationScheduler (BOP-Elites).

The emitter is selected via ArchiveConfig.emitter_type:
  "gaussian" (default) → GaussianEmitter + Scheduler (backwards compatible)
  "bop"               → CappedBOPEmitter + BayesianOptimizationScheduler

GridArchive is always constructed with extra_fields for layout_coverage and
space_saving so that Phase 11 Pareto-Slider queries can access them.

References:
    - .planning/phases/09-outer-loop-v1/09-01-PLAN.md (Task 2)
    - .planning/phases/11-outer-loop-v2/11-01-PLAN.md (Task 2)
    - D-01: Replace GaussianEmitter with CappedBOPEmitter (BOP-Elites)
    - D-03: BOP-Elites compatible with existing GridArchive
    - D-16: solution_dim = max_words * 4 (flattened (N,4) params tensor)
    - Pitfall 5: clamp measures to [0.0, 1.0] before tell()
    - T-09-02: validate solution shape at wrapper boundary
    - T-11-01: clamp extra_fields (layout_coverage, space_saving) to [0.0, 1.0]
"""

from __future__ import annotations

from typing import Any

import numpy as np
import structlog
from ribs.archives import GridArchive
from ribs.emitters import GaussianEmitter
from ribs.schedulers import BayesianOptimizationScheduler, Scheduler

from aerocloud.outer_loop.bop_emitter import CappedBOPEmitter
from aerocloud.outer_loop.models import ArchiveConfig

logger = structlog.get_logger(__name__)

# Extra fields stored per elite for Pareto-Slider (Plan 11-03).
# pyribs GridArchive extra_fields type: dict[str, tuple[shape, dtype]]
# We use Any for the value type to satisfy mypy's invariant dict constraint.
_EXTRA_FIELDS: dict[str, Any] = {
    "layout_coverage": ((), np.float64),
    "space_saving": ((), np.float64),
}


class ArchiveWrapper:
    """Wraps pyribs GridArchive + emitter + scheduler for MAP-Elites.

    The archive maintains a 4D grid over behavioral descriptors:
        [shape_fidelity, rotation_ratio, symmetry, semantic_clustering]
    Each dimension is bounded [0.0, 1.0].

    Solution representation: flattened (max_words, 4) params tensor
    (y, x, scale, rotation per word) → 1D vector of length max_words * 4.

    The GridArchive always has extra_fields={'layout_coverage': ..., 'space_saving': ...}
    so that Pareto-Slider queries work regardless of emitter type.

    Args:
        config: ArchiveConfig with bins_per_dim, sigma, batch_size, max_words,
                emitter_type, and optional bounds/history_cap (Phase 11).
        seed:   Deterministic seed passed to GridArchive and emitter.
    """

    NUM_DESCRIPTOR_DIMS: int = 4  # shape_fidelity, rotation_ratio, symmetry, semantic_clustering

    def __init__(self, config: ArchiveConfig, seed: int = 42) -> None:
        self._config = config
        # D-16: solution_dim is always max_words * 4 (padded to fixed length)
        self._solution_dim: int = config.max_words * 4

        # --- GridArchive (pyribs 0.10.0 API) ---
        # Always include extra_fields for layout_coverage + space_saving (Plan 11-01, 11-03)
        self._archive: GridArchive = GridArchive(
            solution_dim=self._solution_dim,
            dims=[config.bins_per_dim] * self.NUM_DESCRIPTOR_DIMS,
            ranges=[(0.0, 1.0)] * self.NUM_DESCRIPTOR_DIMS,
            seed=seed,
            extra_fields=_EXTRA_FIELDS,
        )

        # --- Emitter + Scheduler selection ---
        # Typed as union so mypy accepts both Scheduler and BayesianOptimizationScheduler.
        # Both share the .ask() / .tell() interface used in ArchiveWrapper.
        self._scheduler: Scheduler | BayesianOptimizationScheduler
        if config.emitter_type == "bop":
            self._scheduler = self._build_bop_scheduler(config, seed)
        else:
            self._scheduler = self._build_gaussian_scheduler(config, seed)

        logger.info(
            "ArchiveWrapper initialized",
            solution_dim=self._solution_dim,
            bins_per_dim=config.bins_per_dim,
            capacity=self.capacity,
            sigma=config.sigma,
            batch_size=config.batch_size,
            emitter_type=config.emitter_type,
        )

    # ------------------------------------------------------------------
    # Emitter factory helpers
    # ------------------------------------------------------------------

    def _build_gaussian_scheduler(self, config: ArchiveConfig, seed: int) -> Scheduler:
        """Build the Phase 9 GaussianEmitter + Scheduler (backwards compat, D-03)."""
        _x0 = np.zeros(self._solution_dim)
        emitter = GaussianEmitter(
            archive=self._archive,
            sigma=config.sigma,
            x0=_x0,
            batch_size=config.batch_size,
            seed=seed,
        )
        return Scheduler(archive=self._archive, emitters=[emitter])

    def _build_bop_scheduler(
        self, config: ArchiveConfig, seed: int
    ) -> BayesianOptimizationScheduler:
        """Build CappedBOPEmitter + BayesianOptimizationScheduler (Phase 11, D-01).

        Bounds default to [0, 1]^solution_dim when not supplied in config.
        """
        lower_bounds: np.ndarray = (
            config.lower_bounds if config.lower_bounds is not None else np.zeros(self._solution_dim)
        )
        upper_bounds: np.ndarray = (
            config.upper_bounds if config.upper_bounds is not None else np.ones(self._solution_dim)
        )

        emitter = CappedBOPEmitter(
            archive=self._archive,
            lower_bounds=lower_bounds,
            upper_bounds=upper_bounds,
            num_initial_samples=config.num_initial_samples,
            batch_size=config.batch_size,
            history_cap=config.history_cap,
            seed=seed,
        )
        return BayesianOptimizationScheduler(archive=self._archive, emitters=[emitter])

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

    def tell(
        self,
        objectives: np.ndarray,
        measures: np.ndarray,
        layout_coverage: np.ndarray | None = None,
        space_saving: np.ndarray | None = None,
    ) -> None:
        """Inform the archive about the quality of the last ask() solutions.

        Pitfall 5 mitigation: measures are clamped to [0.0, 1.0] before
        passing to the archive to guard against NaN/Inf/out-of-range values
        from the optimizer output.

        T-11-01 mitigation: layout_coverage and space_saving are also clamped
        to [0.0, 1.0] before storage.

        T-09-02 mitigation: validates objectives / measures shapes.

        Args:
            objectives:       1D array of fitness values (one per solution).
            measures:         2D array (batch_size, NUM_DESCRIPTOR_DIMS) of
                              behavioral descriptor values.
            layout_coverage:  1D array (batch_size,) of layout coverage values
                              [0.0, 1.0]. None → np.zeros(batch_size).
            space_saving:     1D array (batch_size,) of space saving values
                              [0.0, 1.0]. None → np.zeros(batch_size).
        """
        batch_size = len(objectives)

        # Clamp behavioral descriptors to valid range (Pitfall 5, T-09-01)
        measures_clamped = np.clip(measures, 0.0, 1.0)

        # Build extra_fields with clamping (T-11-01)
        lc = np.clip(
            layout_coverage if layout_coverage is not None else np.zeros(batch_size),
            0.0,
            1.0,
        )
        ss = np.clip(
            space_saving if space_saving is not None else np.zeros(batch_size),
            0.0,
            1.0,
        )

        # pyribs 0.10.0 Scheduler.tell() uses keyword 'objective' (singular)
        # BayesianOptimizationScheduler.tell() accepts **fields for extra_fields
        self._scheduler.tell(
            objective=objectives,
            measures=measures_clamped,
            layout_coverage=lc,
            space_saving=ss,
        )
        logger.debug(
            "Archive tell()",
            n_solutions=batch_size,
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
            Dict with 'solution', 'objective', 'measures', 'layout_coverage',
            'space_saving', etc.
        """
        return self._archive.data()

    def best_elite(self) -> dict:  # type: ignore[type-arg]
        """Return the elite with the highest fitness.

        Returns:
            Dict with 'solution', 'objective', 'measures', etc.

        Raises:
            IndexError: if the archive is empty.
        """
        return self._archive.best_elite

"""CappedBOPEmitter — BayesianOptimizationEmitter with GP history capping.

Subclasses pyribs 0.10.0 BayesianOptimizationEmitter to prevent O(n^3) GP
blowup when GPyTorch is NOT installed (D-02 fallback path).

The cap trims the internal _dataset dict to the most recent history_cap entries
before each tell() call, keeping the sklearn dense GP training time bounded at
≈ 0.02s with cap=200 (per RESEARCH.md benchmark).

References:
    - 11-01-PLAN.md Task 1
    - RESEARCH.md: history_cap=200 keeps GP fit under 0.02s
    - T-11-02: history_cap validated in constructor (DoS mitigation, ge=10)
    - D-02: GPyTorch NOT installed — fallback to history-capped sklearn GP
"""

from __future__ import annotations

import numpy as np
import structlog
from ribs.emitters import BayesianOptimizationEmitter

logger = structlog.get_logger(__name__)

_HISTORY_CAP_MIN = 10  # T-11-02: minimum cap to prevent trivial DoS


class CappedBOPEmitter(BayesianOptimizationEmitter):
    """BayesianOptimizationEmitter with bounded GP training history.

    Wraps pyribs BayesianOptimizationEmitter and overrides tell() to trim the
    internal _dataset to the last `history_cap` entries before delegating to
    the parent class. This prevents O(n^3) GP matrix inversion blowup when
    accumulating thousands of evaluations without GPyTorch sparse GP.

    Args:
        archive:             GridArchive instance (passed to parent).
        history_cap:         Maximum number of data points kept in the GP
                             training set. Must be >= 10 (T-11-02).
        *args, **kwargs:     Forwarded to BayesianOptimizationEmitter.__init__.
                             Must include lower_bounds, upper_bounds, and
                             num_initial_samples (required by parent).

    Raises:
        ValueError: If history_cap < 10 (T-11-02 mitigation).
    """

    def __init__(
        self,
        *args: object,
        history_cap: int = 200,
        **kwargs: object,
    ) -> None:
        if history_cap < _HISTORY_CAP_MIN:
            raise ValueError(
                f"history_cap must be >= {_HISTORY_CAP_MIN} to prevent trivial DoS "
                f"(T-11-02); got {history_cap}"
            )
        self._history_cap: int = history_cap
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

        logger.debug(
            "CappedBOPEmitter initialized",
            history_cap=self._history_cap,
            solution_dim=self.solution_dim,
            batch_size=self.batch_size,
        )

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def history_cap(self) -> int:
        """Maximum number of data points retained in GP training set."""
        return self._history_cap

    # ------------------------------------------------------------------
    # History trimming
    # ------------------------------------------------------------------

    def _trim_dataset(self) -> None:
        """Trim _dataset to at most history_cap most recent entries.

        The _dataset dict has keys 'solution', 'objective', 'measures'.
        We keep the LAST history_cap rows (most recent tell() data) and
        drop the oldest entries (FIFO).

        This is the core DoS mitigation for T-11-02: without GPyTorch's
        sparse GP, the sklearn GP inside BayesianOptimizationEmitter scales
        as O(n^3) in the number of training points. Capping at 200 keeps
        training under 0.02s per RESEARCH.md benchmark.
        """
        if not hasattr(self, "_dataset") or self._dataset is None:
            return  # pragma: no cover

        # Cast to typed dict for mypy — parent class stores np.ndarray values
        dataset: dict[str, np.ndarray] = self._dataset  # type: ignore[assignment]

        solution_arr = dataset.get("solution")
        if solution_arr is None or len(solution_arr) <= self._history_cap:
            return  # already within cap — no trimming needed

        n = len(solution_arr)
        for key in ("solution", "objective", "measures"):
            arr = dataset.get(key)
            if arr is not None and len(arr) > self._history_cap:
                dataset[key] = arr[-self._history_cap :]

        logger.debug(
            "CappedBOPEmitter._trim_dataset",
            before=n,
            after=min(n, self._history_cap),
            cap=self._history_cap,
        )

    # ------------------------------------------------------------------
    # Override tell() to trim before GP training
    # ------------------------------------------------------------------

    def tell(  # type: ignore[override]
        self,
        solution: np.ndarray,
        objective: np.ndarray,
        measures: np.ndarray,
        **kwargs: object,
    ) -> None:
        """Tell the emitter about evaluated solutions, then trim GP history.

        Calls the parent tell() first (which appends to _dataset), then
        trims _dataset to at most history_cap entries to keep GP training
        tractable (T-11-02, D-02).

        Args:
            solution:  Array of shape (n, solution_dim) with evaluated solutions.
            objective: Array of shape (n,) with objective values.
            measures:  Array of shape (n, measure_dim) with behavioral measures.
            **kwargs:  Extra keyword arguments forwarded to parent tell().
        """
        super().tell(solution=solution, objective=objective, measures=measures, **kwargs)  # type: ignore[arg-type]
        self._trim_dataset()

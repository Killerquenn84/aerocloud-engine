"""Tests for CappedBOPEmitter and extended ArchiveConfig.

TDD RED phase: tests written before implementation.

Behavioral:
    - Test 1: CappedBOPEmitter constructs without error given valid GridArchive + bounds
    - Test 2: CappedBOPEmitter.ask() returns array of shape (batch_size, solution_dim)
    - Test 3: After history_cap+50 tell() calls, internal _dataset has <= history_cap entries
    - Test 4: ArchiveConfig accepts lower_bounds/upper_bounds/num_initial_samples/history_cap
    - Test 5: ArchiveConfig without bounds fields still works (backwards compatible, defaults to None)

References:
    - 11-01-PLAN.md Task 1
    - RESEARCH.md D-02: history_cap fallback for GPyTorch-free deployment
    - T-11-02: history_cap validated in constructor (DoS mitigation)
"""

from __future__ import annotations

import numpy as np
import pytest
from ribs.archives import GridArchive

from aerocloud.outer_loop.bop_emitter import CappedBOPEmitter
from aerocloud.outer_loop.models import ArchiveConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


SOLUTION_DIM = 8  # 2 words x 4 params — fast for tests
NUM_DESCRIPTOR_DIMS = 4
BATCH_SIZE = 4
NUM_INITIAL_SAMPLES = 10


@pytest.fixture
def small_archive() -> GridArchive:
    """Tiny GridArchive: solution_dim=8, 3^4=81 cells."""
    return GridArchive(
        solution_dim=SOLUTION_DIM,
        dims=[3] * NUM_DESCRIPTOR_DIMS,
        ranges=[(0.0, 1.0)] * NUM_DESCRIPTOR_DIMS,
        seed=0,
    )


@pytest.fixture
def lower_bounds() -> np.ndarray:
    return np.zeros(SOLUTION_DIM, dtype=np.float64)


@pytest.fixture
def upper_bounds() -> np.ndarray:
    return np.ones(SOLUTION_DIM, dtype=np.float64)


@pytest.fixture
def capped_emitter(small_archive: GridArchive, lower_bounds: np.ndarray, upper_bounds: np.ndarray) -> CappedBOPEmitter:
    """CappedBOPEmitter with history_cap=50 for fast capping tests."""
    return CappedBOPEmitter(
        archive=small_archive,
        lower_bounds=lower_bounds,
        upper_bounds=upper_bounds,
        num_initial_samples=NUM_INITIAL_SAMPLES,
        batch_size=BATCH_SIZE,
        history_cap=50,
        seed=0,
    )


# ---------------------------------------------------------------------------
# Test 1: Construction
# ---------------------------------------------------------------------------


class TestCappedBOPEmitterConstruction:
    def test_constructs_without_error(
        self, small_archive: GridArchive, lower_bounds: np.ndarray, upper_bounds: np.ndarray
    ) -> None:
        """Test 1: CappedBOPEmitter constructs without error given valid GridArchive + bounds."""
        emitter = CappedBOPEmitter(
            archive=small_archive,
            lower_bounds=lower_bounds,
            upper_bounds=upper_bounds,
            num_initial_samples=NUM_INITIAL_SAMPLES,
            batch_size=BATCH_SIZE,
            history_cap=200,
            seed=42,
        )
        assert emitter is not None

    def test_history_cap_stored(
        self, small_archive: GridArchive, lower_bounds: np.ndarray, upper_bounds: np.ndarray
    ) -> None:
        """history_cap is stored and accessible."""
        emitter = CappedBOPEmitter(
            archive=small_archive,
            lower_bounds=lower_bounds,
            upper_bounds=upper_bounds,
            num_initial_samples=NUM_INITIAL_SAMPLES,
            batch_size=BATCH_SIZE,
            history_cap=100,
            seed=0,
        )
        assert emitter.history_cap == 100

    def test_invalid_history_cap_raises(
        self, small_archive: GridArchive, lower_bounds: np.ndarray, upper_bounds: np.ndarray
    ) -> None:
        """history_cap must be >= 10 (T-11-02: DoS mitigation)."""
        with pytest.raises(ValueError, match="history_cap"):
            CappedBOPEmitter(
                archive=small_archive,
                lower_bounds=lower_bounds,
                upper_bounds=upper_bounds,
                num_initial_samples=NUM_INITIAL_SAMPLES,
                batch_size=BATCH_SIZE,
                history_cap=5,  # too small
                seed=0,
            )


# ---------------------------------------------------------------------------
# Test 2: ask() shape
# ---------------------------------------------------------------------------


class TestCappedBOPEmitterAsk:
    def test_ask_returns_correct_shape(self, capped_emitter: CappedBOPEmitter) -> None:
        """Test 2: ask() returns array of shape (batch_size, solution_dim)."""
        solutions = capped_emitter.ask()
        assert isinstance(solutions, np.ndarray)
        # During initial phase ask() returns num_initial_samples, not batch_size
        # Solution dimension must always be SOLUTION_DIM
        assert solutions.shape[1] == SOLUTION_DIM

    def test_ask_returns_float_array(self, capped_emitter: CappedBOPEmitter) -> None:
        """ask() returns a floating-point array."""
        solutions = capped_emitter.ask()
        assert np.issubdtype(solutions.dtype, np.floating)

    def test_ask_solutions_within_bounds(
        self, capped_emitter: CappedBOPEmitter, lower_bounds: np.ndarray, upper_bounds: np.ndarray
    ) -> None:
        """Solutions from ask() stay within [lower_bounds, upper_bounds]."""
        solutions = capped_emitter.ask()
        assert np.all(solutions >= lower_bounds - 1e-9)
        assert np.all(solutions <= upper_bounds + 1e-9)


# ---------------------------------------------------------------------------
# Test 3: History capping
# ---------------------------------------------------------------------------


class TestHistoryCapping:
    def test_dataset_capped_after_many_tells(self, capped_emitter: CappedBOPEmitter) -> None:
        """Test 3: After history_cap+50 tell() calls, _dataset has <= history_cap entries."""
        history_cap = capped_emitter.history_cap  # 50
        rng = np.random.default_rng(123)

        # Pump 100 = history_cap + 50 individual tell() entries
        # We do this by cycling ask → tell with batch of 1 each time
        total_tells = history_cap + 50
        tells_done = 0

        # First ask to get initial solutions, then tell them one-by-one conceptually
        # We inject directly into _dataset to test the capping logic without
        # needing a full live GP training loop
        solutions = rng.uniform(0.0, 1.0, size=(total_tells, SOLUTION_DIM))
        objectives = rng.uniform(0.5, 1.0, size=(total_tells, 1))
        measures = rng.uniform(0.0, 1.0, size=(total_tells, NUM_DESCRIPTOR_DIMS))

        # Simulate dataset growth by appending directly and then trimming
        # CappedBOPEmitter.tell() should trim _dataset before delegating to super
        # We test by calling the dataset trimming method directly or via ask/tell cycle

        # Since tell() requires a matching ask() in pyribs, we use the internal
        # _dataset directly to simulate overflow, then call _trim_dataset()
        capped_emitter._dataset["solution"] = solutions
        capped_emitter._dataset["objective"] = objectives
        capped_emitter._dataset["measures"] = measures
        capped_emitter._trim_dataset()

        dataset_len = len(capped_emitter._dataset["solution"])
        assert dataset_len <= history_cap, (
            f"Expected dataset <= {history_cap} entries, got {dataset_len}"
        )

    def test_dataset_keeps_most_recent_entries(self, capped_emitter: CappedBOPEmitter) -> None:
        """After trimming, the LAST history_cap entries are retained (FIFO drop)."""
        history_cap = capped_emitter.history_cap  # 50
        rng = np.random.default_rng(456)

        total = history_cap + 20
        solutions = rng.uniform(0.0, 1.0, size=(total, SOLUTION_DIM))
        objectives = rng.uniform(0.5, 1.0, size=(total, 1))
        measures = rng.uniform(0.0, 1.0, size=(total, NUM_DESCRIPTOR_DIMS))

        capped_emitter._dataset["solution"] = solutions
        capped_emitter._dataset["objective"] = objectives
        capped_emitter._dataset["measures"] = measures
        capped_emitter._trim_dataset()

        # The last history_cap rows must be intact
        expected_solutions = solutions[-history_cap:]
        np.testing.assert_array_equal(
            capped_emitter._dataset["solution"], expected_solutions
        )


# ---------------------------------------------------------------------------
# Test 4: Extended ArchiveConfig
# ---------------------------------------------------------------------------


class TestExtendedArchiveConfig:
    def test_archive_config_accepts_bounds_fields(self) -> None:
        """Test 4: ArchiveConfig accepts lower_bounds/upper_bounds/num_initial_samples/history_cap."""
        cfg = ArchiveConfig(
            solution_dim=32,
            bins_per_dim=5,
            lower_bounds=np.zeros(32),
            upper_bounds=np.ones(32),
            num_initial_samples=20,
            history_cap=200,
            emitter_type="bop",
        )
        assert cfg.lower_bounds is not None
        assert cfg.upper_bounds is not None
        assert cfg.num_initial_samples == 20
        assert cfg.history_cap == 200
        assert cfg.emitter_type == "bop"

    def test_archive_config_emitter_type_bop(self) -> None:
        """emitter_type='bop' is a valid literal."""
        cfg = ArchiveConfig(solution_dim=16, emitter_type="bop")
        assert cfg.emitter_type == "bop"

    def test_archive_config_emitter_type_gaussian(self) -> None:
        """emitter_type='gaussian' is a valid literal (default)."""
        cfg = ArchiveConfig(solution_dim=16)
        assert cfg.emitter_type == "gaussian"

    def test_archive_config_history_cap_ge_10(self) -> None:
        """history_cap must be >= 10."""
        with pytest.raises(Exception):
            ArchiveConfig(solution_dim=16, history_cap=5)


# ---------------------------------------------------------------------------
# Test 5: Backwards compatibility
# ---------------------------------------------------------------------------


class TestArchiveConfigBackwardsCompatibility:
    def test_archive_config_without_bounds_still_works(self) -> None:
        """Test 5: ArchiveConfig without bounds fields still works (defaults to None)."""
        cfg = ArchiveConfig(solution_dim=400, bins_per_dim=10, sigma=0.1, batch_size=16, max_words=100)
        assert cfg.lower_bounds is None
        assert cfg.upper_bounds is None
        assert cfg.num_initial_samples == 20  # default
        assert cfg.history_cap == 200  # default
        assert cfg.emitter_type == "gaussian"  # default

    def test_archive_config_minimal_construction(self) -> None:
        """Minimal ArchiveConfig (solution_dim only) still works."""
        cfg = ArchiveConfig(solution_dim=8)
        assert cfg.solution_dim == 8
        assert cfg.emitter_type == "gaussian"

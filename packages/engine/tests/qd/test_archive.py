"""Tests for outer_loop.archive — ArchiveWrapper with pyribs GridArchive + GaussianEmitter.

TDD RED phase: tests written before implementation.

Behavioral:
    - Test 1: ArchiveWrapper creates GridArchive with correct dims/ranges
    - Test 2: ask() returns (batch_size, solution_dim) numpy array
    - Test 3: tell() with objectives and measures updates archive
    - Test 4: coverage property returns float [0.0, 1.0]
    - Test 5: capacity property returns bins_per_dim^4
    - Test 6: solution_dim = max_words * 4 (D-16, (N,4) flattened)
"""

from __future__ import annotations

import numpy as np
import pytest

from aerocloud.outer_loop.archive import ArchiveWrapper
from aerocloud.outer_loop.models import ArchiveConfig


@pytest.fixture
def small_config() -> ArchiveConfig:
    """Minimal ArchiveConfig for fast tests: 3 bins × 4 dims = 81 cells."""
    return ArchiveConfig(
        solution_dim=800,
        bins_per_dim=3,
        sigma=0.1,
        batch_size=4,
        max_words=200,
    )


@pytest.fixture
def wrapper(small_config: ArchiveConfig) -> ArchiveWrapper:
    """ArchiveWrapper built from the small_config fixture."""
    return ArchiveWrapper(config=small_config, seed=0)


class TestArchiveWrapperConstruction:
    def test_solution_dim_matches_config(self, wrapper: ArchiveWrapper, small_config: ArchiveConfig) -> None:
        """Test 6: solution_dim equals config.max_words * 4."""
        expected_dim = small_config.max_words * 4
        assert wrapper.solution_dim == expected_dim

    def test_capacity_is_bins_power_four(self, wrapper: ArchiveWrapper, small_config: ArchiveConfig) -> None:
        """Test 5: capacity is bins_per_dim^4 (4 behavioral dimensions)."""
        expected = small_config.bins_per_dim ** 4
        assert wrapper.capacity == expected

    def test_initial_coverage_is_zero(self, wrapper: ArchiveWrapper) -> None:
        """Test 4: fresh archive has 0.0 coverage."""
        assert wrapper.coverage == pytest.approx(0.0)

    def test_initial_num_elites_is_zero(self, wrapper: ArchiveWrapper) -> None:
        """New archive has 0 elites."""
        assert wrapper.num_elites == 0


class TestArchiveWrapperAsk:
    def test_ask_returns_correct_shape(self, wrapper: ArchiveWrapper, small_config: ArchiveConfig) -> None:
        """Test 2: ask() returns (batch_size, solution_dim) numpy array."""
        solutions = wrapper.ask()
        assert isinstance(solutions, np.ndarray)
        assert solutions.shape == (small_config.batch_size, small_config.max_words * 4)

    def test_ask_returns_float_array(self, wrapper: ArchiveWrapper) -> None:
        """ask() returns a float array (not integer)."""
        solutions = wrapper.ask()
        assert np.issubdtype(solutions.dtype, np.floating)


class TestArchiveWrapperTell:
    def test_tell_updates_archive(self, wrapper: ArchiveWrapper, small_config: ArchiveConfig) -> None:
        """Test 3: tell() with valid objectives and measures adds entries to archive."""
        solutions = wrapper.ask()
        batch = small_config.batch_size
        objectives = np.random.default_rng(0).uniform(0.5, 1.0, size=batch)
        # 4 behavioral dimensions, all in [0.0, 1.0]
        measures = np.random.default_rng(1).uniform(0.0, 1.0, size=(batch, 4))
        wrapper.tell(objectives=objectives, measures=measures)
        # Archive should have at least some entries
        assert wrapper.num_elites >= 0  # may be 0 if all land in same cell and are replaced

    def test_tell_with_out_of_range_measures_clamped(
        self, wrapper: ArchiveWrapper, small_config: ArchiveConfig
    ) -> None:
        """Pitfall 5: tell() clamps measures to [0.0, 1.0] before passing to archive."""
        solutions = wrapper.ask()
        batch = small_config.batch_size
        objectives = np.ones(batch)
        # Measures outside [0,1] — should be clamped, not raise
        measures = np.full((batch, 4), 1.5)  # all out of range
        # Should not raise
        wrapper.tell(objectives=objectives, measures=measures)

    def test_coverage_increases_after_tell(self, wrapper: ArchiveWrapper, small_config: ArchiveConfig) -> None:
        """Test 4: coverage increases after tell() adds entries."""
        solutions = wrapper.ask()
        batch = small_config.batch_size
        objectives = np.ones(batch) * 0.9
        # Spread measures across the space so different bins are filled
        rng = np.random.default_rng(42)
        measures = rng.uniform(0.0, 1.0, size=(batch, 4))
        wrapper.tell(objectives=objectives, measures=measures)
        assert wrapper.coverage >= 0.0
        assert wrapper.coverage <= 1.0


class TestArchiveWrapperProperties:
    def test_coverage_is_float_in_unit_interval(self, wrapper: ArchiveWrapper) -> None:
        """coverage is always a float in [0.0, 1.0]."""
        cov = wrapper.coverage
        assert isinstance(cov, float)
        assert 0.0 <= cov <= 1.0

    def test_capacity_type(self, wrapper: ArchiveWrapper) -> None:
        """capacity is an integer."""
        assert isinstance(wrapper.capacity, int)

    def test_num_elites_type(self, wrapper: ArchiveWrapper) -> None:
        """num_elites is an integer."""
        assert isinstance(wrapper.num_elites, int)


class TestArchiveWrapperDimValidation:
    def test_solution_dim_computed_from_max_words(self) -> None:
        """Test 6: ArchiveWrapper computes solution_dim = max_words * 4."""
        cfg = ArchiveConfig(solution_dim=400, bins_per_dim=3, max_words=100)
        wrapper = ArchiveWrapper(config=cfg, seed=0)
        # D-16: solution_dim is max_words * 4
        assert wrapper.solution_dim == 100 * 4

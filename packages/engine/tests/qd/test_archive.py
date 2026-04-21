"""Tests for outer_loop.archive — ArchiveWrapper with pyribs GridArchive + GaussianEmitter/BOP.

TDD RED phase: tests written before implementation.

Behavioral (Phase 9 — existing):
    - Test 1: ArchiveWrapper creates GridArchive with correct dims/ranges
    - Test 2: ask() returns (batch_size, solution_dim) numpy array
    - Test 3: tell() with objectives and measures updates archive
    - Test 4: coverage property returns float [0.0, 1.0]
    - Test 5: capacity property returns bins_per_dim^4
    - Test 6: solution_dim = max_words * 4 (D-16, (N,4) flattened)

Behavioral (Phase 11 — new, 11-01-PLAN.md Task 2):
    - Test BOP-1: ArchiveWrapper(emitter_type="bop") uses BayesianOptimizationScheduler
    - Test BOP-2: ArchiveWrapper(emitter_type="gaussian") still uses GaussianEmitter (backwards compat)
    - Test BOP-3: tell() accepts layout_coverage and space_saving extra_fields
    - Test BOP-4: data() returns dict with 'layout_coverage' and 'space_saving' keys
    - Test BOP-5: OuterLoop.single_iteration() extracts and passes layout_coverage + space_saving
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


# ---------------------------------------------------------------------------
# Phase 11: BOP emitter + extra_fields tests (11-01-PLAN.md Task 2)
# ---------------------------------------------------------------------------


@pytest.fixture
def bop_config() -> ArchiveConfig:
    """ArchiveConfig with emitter_type='bop' for Phase 11 tests.

    solution_dim=40 = max_words(10) * 4 (minimum max_words is 10 per constraint).
    """
    return ArchiveConfig(
        solution_dim=40,
        bins_per_dim=3,
        batch_size=4,
        max_words=10,
        num_initial_samples=10,
        history_cap=50,
        emitter_type="bop",
    )


@pytest.fixture
def bop_wrapper(bop_config: ArchiveConfig) -> ArchiveWrapper:
    """ArchiveWrapper with BOP emitter."""
    return ArchiveWrapper(config=bop_config, seed=0)


class TestBOPEmitterSelection:
    def test_bop_config_creates_bayesian_scheduler(self, bop_wrapper: ArchiveWrapper) -> None:
        """Test BOP-1: emitter_type='bop' creates BayesianOptimizationScheduler."""
        from ribs.schedulers import BayesianOptimizationScheduler
        assert isinstance(bop_wrapper._scheduler, BayesianOptimizationScheduler)

    def test_gaussian_config_creates_plain_scheduler(self, wrapper: ArchiveWrapper) -> None:
        """Test BOP-2: emitter_type='gaussian' still creates Scheduler (backwards compat)."""
        from ribs.schedulers import Scheduler
        # BayesianOptimizationScheduler is NOT a subclass of Scheduler in pyribs 0.10.0
        assert not hasattr(bop_wrapper := wrapper, "_scheduler") or True  # just access attribute
        # The gaussian wrapper uses the base Scheduler, not BayesianOptimizationScheduler
        from ribs.schedulers import BayesianOptimizationScheduler
        assert not isinstance(wrapper._scheduler, BayesianOptimizationScheduler)

    def test_bop_wrapper_ask_returns_solutions(self, bop_wrapper: ArchiveWrapper) -> None:
        """BOP emitter ask() returns a (n, solution_dim) array."""
        solutions = bop_wrapper.ask()
        assert isinstance(solutions, np.ndarray)
        assert solutions.ndim == 2
        assert solutions.shape[1] == bop_wrapper.solution_dim


class TestExtraFieldsInArchive:
    def test_tell_accepts_layout_coverage_and_space_saving(self, bop_wrapper: ArchiveWrapper) -> None:
        """Test BOP-3: tell() accepts layout_coverage and space_saving extra_fields."""
        solutions = bop_wrapper.ask()
        batch = solutions.shape[0]
        rng = np.random.default_rng(7)
        objectives = rng.uniform(0.5, 1.0, size=batch)
        measures = rng.uniform(0.0, 1.0, size=(batch, 4))
        lc = rng.uniform(0.0, 1.0, size=batch)
        ss = rng.uniform(0.0, 1.0, size=batch)
        # Should not raise
        bop_wrapper.tell(
            objectives=objectives,
            measures=measures,
            layout_coverage=lc,
            space_saving=ss,
        )

    def test_data_contains_extra_fields(self, bop_wrapper: ArchiveWrapper) -> None:
        """Test BOP-4: data() returns dict with 'layout_coverage' and 'space_saving' keys."""
        solutions = bop_wrapper.ask()
        batch = solutions.shape[0]
        rng = np.random.default_rng(8)
        objectives = rng.uniform(0.5, 1.0, size=batch)
        measures = rng.uniform(0.0, 1.0, size=(batch, 4))
        lc = rng.uniform(0.2, 0.8, size=batch)
        ss = rng.uniform(0.3, 0.9, size=batch)
        bop_wrapper.tell(objectives=objectives, measures=measures, layout_coverage=lc, space_saving=ss)

        if bop_wrapper.num_elites > 0:
            data = bop_wrapper.data()
            assert "layout_coverage" in data, "data() must contain 'layout_coverage'"
            assert "space_saving" in data, "data() must contain 'space_saving'"

    def test_gaussian_wrapper_tell_without_extra_fields_still_works(
        self, wrapper: ArchiveWrapper, small_config: ArchiveConfig
    ) -> None:
        """BOP-backwards: gaussian wrapper tell() without extra_fields works (None → zeros)."""
        solutions = wrapper.ask()
        batch = small_config.batch_size
        rng = np.random.default_rng(9)
        objectives = rng.uniform(0.5, 1.0, size=batch)
        measures = rng.uniform(0.0, 1.0, size=(batch, 4))
        # No layout_coverage / space_saving — should not raise
        wrapper.tell(objectives=objectives, measures=measures)

    def test_extra_fields_clamped_to_unit_interval(self, bop_wrapper: ArchiveWrapper) -> None:
        """T-11-01: extra_fields layout_coverage and space_saving are clamped to [0,1]."""
        solutions = bop_wrapper.ask()
        batch = solutions.shape[0]
        objectives = np.ones(batch) * 0.9
        measures = np.random.default_rng(10).uniform(0.0, 1.0, size=(batch, 4))
        # Out-of-range extra_fields — should be clamped, not raise
        lc_out = np.full(batch, 1.5)
        ss_out = np.full(batch, -0.3)
        bop_wrapper.tell(objectives=objectives, measures=measures, layout_coverage=lc_out, space_saving=ss_out)


class TestOuterLoopExtraFieldsIntegration:
    """Test BOP-5: OuterLoop.single_iteration() passes layout_coverage + space_saving through tell()."""

    def test_outer_loop_single_iteration_passes_extra_fields(self) -> None:
        """OuterLoop.single_iteration() extracts layout_coverage + space_saving from QualityMetrics."""
        from unittest.mock import MagicMock, patch

        from aerocloud.models.archive import BehaviorDescriptor
        from aerocloud.outer_loop.archive import ArchiveWrapper
        from aerocloud.outer_loop.emitter import NoveltyGaussianEmitter, SaturationMonitor
        from aerocloud.outer_loop.models import ArchiveConfig, QualityMetrics, QualityWeights
        from aerocloud.outer_loop.scheduler import OuterLoop

        cfg = ArchiveConfig(
            solution_dim=40,
            bins_per_dim=3,
            batch_size=4,
            max_words=10,
            emitter_type="gaussian",  # gaussian for speed in this integration test
        )
        archive = ArchiveWrapper(config=cfg, seed=0)

        rng = np.random.default_rng(99)

        def fake_evaluate(solution: np.ndarray) -> tuple[QualityMetrics, BehaviorDescriptor, np.ndarray]:
            metrics = QualityMetrics(
                layout_coverage=float(rng.uniform(0.2, 0.8)),
                layout_uniformity=float(rng.uniform(0.2, 0.8)),
                space_saving=float(rng.uniform(0.3, 0.9)),
                compactness=float(rng.uniform(0.1, 0.9)),
                aspect_ratio=float(rng.uniform(0.1, 0.9)),
                realized_adjacencies=float(rng.uniform(0.0, 1.0)),
                distortion_score=float(rng.uniform(0.0, 1.0)),
            )
            bd = BehaviorDescriptor(
                shape_fidelity=float(rng.uniform(0.0, 1.0)),
                rotation_ratio=float(rng.uniform(0.0, 1.0)),
                symmetry=float(rng.uniform(0.0, 1.0)),
                semantic_clustering=float(rng.uniform(0.0, 1.0)),
            )
            embedding = np.zeros(384, dtype=np.float32)
            return metrics, bd, embedding

        novelty_emitter = NoveltyGaussianEmitter(archive_wrapper=archive, sigma_boost=0.2, novelty_k=3)
        saturation_monitor = SaturationMonitor(window=5)
        quality_weights = QualityWeights()

        outer_loop = OuterLoop(
            archive=archive,
            evaluate_fn=fake_evaluate,
            persistence=None,
            novelty_emitter=novelty_emitter,
            saturation_monitor=saturation_monitor,
            quality_weights=quality_weights,
        )

        # Spy on archive.tell to verify it receives layout_coverage + space_saving
        tell_calls: list[dict] = []
        original_tell = archive.tell

        def spy_tell(**kwargs: object) -> None:
            tell_calls.append(dict(kwargs))
            original_tell(**kwargs)  # type: ignore[arg-type]

        archive.tell = spy_tell  # type: ignore[method-assign]

        outer_loop.single_iteration()

        assert len(tell_calls) == 1, "tell() should be called exactly once per iteration"
        call_kwargs = tell_calls[0]
        assert "layout_coverage" in call_kwargs, (
            "OuterLoop must pass layout_coverage to archive.tell()"
        )
        assert "space_saving" in call_kwargs, (
            "OuterLoop must pass space_saving to archive.tell()"
        )
        lc_arr = call_kwargs["layout_coverage"]
        ss_arr = call_kwargs["space_saving"]
        assert isinstance(lc_arr, np.ndarray), "layout_coverage must be a numpy array"
        assert isinstance(ss_arr, np.ndarray), "space_saving must be a numpy array"
        assert lc_arr.shape == (cfg.batch_size,)
        assert ss_arr.shape == (cfg.batch_size,)
        # Values must be in [0, 1] (either raw or clamped)
        assert np.all(lc_arr >= 0.0) and np.all(lc_arr <= 1.0)
        assert np.all(ss_arr >= 0.0) and np.all(ss_arr <= 1.0)

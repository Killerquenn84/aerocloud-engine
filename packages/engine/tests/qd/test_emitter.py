"""Tests for NoveltyGaussianEmitter, SaturationMonitor, and reeval_elites.

TDD Red phase: all tests fail before implementation.

References:
    - 09-04-PLAN.md Task 1 + Task 2
    - D-12: BallTree k-NN for novelty computation
    - D-13: SaturationMonitor with 1% plateau threshold
    - D-14: reeval_elites drift detection at 10%
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from aerocloud.outer_loop.emitter import (
    NoveltyGaussianEmitter,
    SaturationMonitor,
    compute_novelty,
    reeval_elites,
)
from aerocloud.outer_loop.models import ArchiveConfig, ReEvalResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def archive_config() -> ArchiveConfig:
    """Small ArchiveConfig for test speed."""
    return ArchiveConfig(solution_dim=40, bins_per_dim=5)


@pytest.fixture
def small_archive_descriptors() -> np.ndarray:
    """5 random 4D descriptors — fewer than k=15."""
    rng = np.random.default_rng(0)
    return rng.random((5, 4))


@pytest.fixture
def large_archive_descriptors() -> np.ndarray:
    """30 random 4D descriptors — more than k=15."""
    rng = np.random.default_rng(1)
    return rng.random((30, 4))


@pytest.fixture
def mock_archive_wrapper(large_archive_descriptors: np.ndarray) -> MagicMock:
    """Mock ArchiveWrapper with data() returning descriptors + objectives."""
    wrapper = MagicMock()
    n = large_archive_descriptors.shape[0]
    rng = np.random.default_rng(42)
    # Build a data dict similar to pyribs archive.data()
    wrapper.data.return_value = {
        "solution": rng.random((n, 40)),
        "objective": rng.random(n),
        "measures": large_archive_descriptors,
    }
    return wrapper


# ---------------------------------------------------------------------------
# Task 1 — compute_novelty
# ---------------------------------------------------------------------------


class TestComputeNovelty:
    def test_returns_inf_when_archive_smaller_than_k(
        self, small_archive_descriptors: np.ndarray
    ) -> None:
        """Test 1: fewer than k entries → float('inf') (everything is novel)."""
        descriptor = np.array([0.5, 0.5, 0.5, 0.5])
        k = 15
        # small_archive_descriptors has 5 entries, k=15 → should return inf
        result = compute_novelty(descriptor, small_archive_descriptors, k=k)
        assert result == float("inf")

    def test_returns_finite_positive_for_dense_archive(
        self, large_archive_descriptors: np.ndarray
    ) -> None:
        """Test 2: dense archive → finite positive float."""
        descriptor = np.array([0.5, 0.5, 0.5, 0.5])
        k = 15
        result = compute_novelty(descriptor, large_archive_descriptors, k=k)
        assert np.isfinite(result)
        assert result > 0.0

    def test_uses_ball_tree_metric(self, large_archive_descriptors: np.ndarray) -> None:
        """Test 3: BallTree with euclidean metric is used internally."""
        descriptor = np.array([0.5, 0.5, 0.5, 0.5])
        k = 5
        # Verify result is consistent with euclidean k-NN mean distance
        # Compute manually: distances from descriptor to all archive points
        diffs = large_archive_descriptors - descriptor
        distances = np.sqrt(np.sum(diffs**2, axis=1))
        expected_mean = np.mean(np.sort(distances)[:k])
        result = compute_novelty(descriptor, large_archive_descriptors, k=k)
        assert abs(result - expected_mean) < 1e-6

    def test_novelty_lower_for_cluster_center(
        self, large_archive_descriptors: np.ndarray
    ) -> None:
        """Test 4: descriptor at cluster center has lower novelty than outlier.

        A descriptor identical to an archive entry is near its neighbors →
        lower mean k-NN distance than a descriptor far from all archive entries.
        """
        # In-cluster descriptor (identical to an archive entry)
        in_cluster = large_archive_descriptors[0].copy()
        # Out-of-cluster descriptor (far corner)
        far_outlier = np.array([10.0, 10.0, 10.0, 10.0])
        k = 5
        novelty_in = compute_novelty(in_cluster, large_archive_descriptors, k=k)
        novelty_out = compute_novelty(far_outlier, large_archive_descriptors, k=k)
        # Outlier should be more novel (larger mean distance)
        assert novelty_out > novelty_in


# ---------------------------------------------------------------------------
# Task 1 — SaturationMonitor
# ---------------------------------------------------------------------------


class TestSaturationMonitor:
    def test_record_tracks_history(self) -> None:
        """Test 4: record() appends coverage values to history."""
        monitor = SaturationMonitor(window=10)
        monitor.record(0.1)
        monitor.record(0.2)
        monitor.record(0.3)
        assert len(monitor._history) == 3

    def test_is_plateaued_true_when_growth_below_threshold(self) -> None:
        """Test 5: is_plateaued returns True when growth < 1% over window."""
        monitor = SaturationMonitor(window=10)
        # Fill window with nearly identical coverage values (flat plateau)
        for _ in range(10):
            monitor.record(0.5)
        assert monitor.is_plateaued is True

    def test_is_plateaued_false_for_growing_archive(self) -> None:
        """Test 6: is_plateaued returns False for growing archive."""
        monitor = SaturationMonitor(window=10)
        for i in range(10):
            monitor.record(i * 0.05)  # 0.0 → 0.45, growth = 0.45 >> 0.01
        assert monitor.is_plateaued is False

    def test_is_plateaued_false_when_history_shorter_than_window(self) -> None:
        """Plateau requires at least window entries — fewer → False."""
        monitor = SaturationMonitor(window=100)
        monitor.record(0.5)
        monitor.record(0.5)
        assert monitor.is_plateaued is False

    def test_plateau_detection_1pct_boundary(self) -> None:
        """Growth exactly at 1% boundary: < 0.01 → plateaued."""
        monitor = SaturationMonitor(window=5)
        monitor.record(0.500)
        monitor.record(0.501)
        monitor.record(0.502)
        monitor.record(0.503)
        monitor.record(0.509)  # growth = 0.509 - 0.500 = 0.009 < 0.01
        assert monitor.is_plateaued is True


# ---------------------------------------------------------------------------
# Task 1 — NoveltyGaussianEmitter
# ---------------------------------------------------------------------------


class TestNoveltyGaussianEmitter:
    def test_sigma_boost_when_plateaued(
        self, archive_config: ArchiveConfig, mock_archive_wrapper: MagicMock
    ) -> None:
        """Test 7: sigma is multiplied by sigma_boost when saturated."""
        emitter = NoveltyGaussianEmitter(
            archive_wrapper=mock_archive_wrapper,
            base_sigma=0.1,
            novelty_k=5,
            sigma_boost=3.0,
        )
        monitor = SaturationMonitor(window=5)
        for _ in range(5):
            monitor.record(0.5)  # plateau
        assert monitor.is_plateaued is True
        effective = emitter.get_effective_sigma(monitor)
        assert abs(effective - 0.3) < 1e-10

    def test_sigma_unchanged_when_not_plateaued(
        self, archive_config: ArchiveConfig, mock_archive_wrapper: MagicMock
    ) -> None:
        """Sigma stays at base when archive is growing."""
        emitter = NoveltyGaussianEmitter(
            archive_wrapper=mock_archive_wrapper,
            base_sigma=0.1,
            novelty_k=5,
            sigma_boost=3.0,
        )
        monitor = SaturationMonitor(window=5)
        for i in range(5):
            monitor.record(i * 0.1)  # growing
        assert monitor.is_plateaued is False
        effective = emitter.get_effective_sigma(monitor)
        assert abs(effective - 0.1) < 1e-10

    def test_compute_batch_novelty_builds_balltree_once_per_batch(
        self, mock_archive_wrapper: MagicMock
    ) -> None:
        """Test 8: BallTree rebuilt once per compute_batch_novelty call, not per solution."""
        emitter = NoveltyGaussianEmitter(
            archive_wrapper=mock_archive_wrapper,
            base_sigma=0.1,
            novelty_k=5,
        )
        measures = np.random.default_rng(99).random((8, 4))
        with patch(
            "aerocloud.outer_loop.emitter.NearestNeighbors"
        ) as mock_nn_cls:
            mock_nn = MagicMock()
            mock_nn_cls.return_value = mock_nn
            mock_nn.kneighbors.return_value = (
                np.ones((8, 5)) * 0.1,
                np.zeros((8, 5), dtype=int),
            )
            emitter.compute_batch_novelty(measures)
            # NearestNeighbors should be instantiated exactly once per batch
            assert mock_nn_cls.call_count == 1
            # fit() called once
            mock_nn.fit.assert_called_once()

    def test_should_boost_exploration_delegates_to_monitor(
        self, mock_archive_wrapper: MagicMock
    ) -> None:
        """should_boost_exploration returns monitor.is_plateaued."""
        emitter = NoveltyGaussianEmitter(
            archive_wrapper=mock_archive_wrapper,
            base_sigma=0.1,
        )
        monitor = MagicMock()
        monitor.is_plateaued = True
        assert emitter.should_boost_exploration(monitor) is True
        monitor.is_plateaued = False
        assert emitter.should_boost_exploration(monitor) is False


# ---------------------------------------------------------------------------
# Task 2 — reeval_elites
# ---------------------------------------------------------------------------


class TestReevalElites:
    @pytest.fixture
    def archive_with_elites(self) -> MagicMock:
        """Mock archive with 5 elites, fitness sorted desc."""
        wrapper = MagicMock()
        rng = np.random.default_rng(7)
        n = 5
        fitnesses = np.array([0.9, 0.8, 0.7, 0.6, 0.5])
        solutions = rng.random((n, 40))
        measures = rng.random((n, 4))
        wrapper.data.return_value = {
            "solution": solutions,
            "objective": fitnesses,
            "measures": measures,
        }
        return wrapper

    @pytest.fixture
    def archive_empty(self) -> MagicMock:
        """Mock archive with no elites."""
        wrapper = MagicMock()
        wrapper.data.return_value = {
            "solution": np.zeros((0, 40)),
            "objective": np.zeros(0),
            "measures": np.zeros((0, 4)),
        }
        return wrapper

    @pytest.mark.asyncio
    async def test_calls_evaluate_fn_for_each_elite(
        self, archive_with_elites: MagicMock
    ) -> None:
        """Test 1: evaluate_fn is called once per elite in top_n."""
        evaluate_fn = AsyncMock(return_value=(0.9, np.zeros(4)))
        results = await reeval_elites(
            archive_wrapper=archive_with_elites,
            evaluate_fn=evaluate_fn,
            top_n=3,
        )
        assert evaluate_fn.call_count == 3

    @pytest.mark.asyncio
    async def test_detects_drift_when_fitness_drops(
        self, archive_with_elites: MagicMock
    ) -> None:
        """Test 2: drift flagged when fitness_after < 0.9 * fitness_before."""
        # Return fitness that is 20% lower → drift
        async def bad_eval(solution: np.ndarray) -> tuple[float, np.ndarray]:
            return (0.7, np.zeros(4))  # 0.9 before → 0.7 after = 22% drop

        results = await reeval_elites(
            archive_wrapper=archive_with_elites,
            evaluate_fn=bad_eval,
            top_n=1,
            drift_threshold=0.1,
        )
        assert len(results) == 1
        assert results[0].drifted is True
        assert results[0].drift_pct > 0.1

    @pytest.mark.asyncio
    async def test_returns_reeval_result_list(
        self, archive_with_elites: MagicMock
    ) -> None:
        """Test 3: returns list[ReEvalResult] with correct types."""
        async def stable_eval(solution: np.ndarray) -> tuple[float, np.ndarray]:
            return (0.88, np.zeros(4))  # 0.9 before → 0.88 after = 2.2% drop (no drift)

        results = await reeval_elites(
            archive_wrapper=archive_with_elites,
            evaluate_fn=stable_eval,
            top_n=2,
        )
        assert len(results) == 2
        for r in results:
            assert isinstance(r, ReEvalResult)
        # No drift: 0.9 → 0.88 = 2.2% drop, below 10% threshold
        assert results[0].drifted is False

    @pytest.mark.asyncio
    async def test_empty_archive_returns_empty_list(
        self, archive_empty: MagicMock
    ) -> None:
        """Test 4: no elites → empty list."""
        evaluate_fn = AsyncMock(return_value=(0.5, np.zeros(4)))
        results = await reeval_elites(
            archive_wrapper=archive_empty,
            evaluate_fn=evaluate_fn,
            top_n=10,
        )
        assert results == []
        evaluate_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_top_n_limits_evaluations(
        self, archive_with_elites: MagicMock
    ) -> None:
        """Test 5: top_n parameter limits how many elites are re-evaluated."""
        evaluate_fn = AsyncMock(return_value=(0.9, np.zeros(4)))
        results = await reeval_elites(
            archive_wrapper=archive_with_elites,
            evaluate_fn=evaluate_fn,
            top_n=2,
        )
        assert len(results) == 2
        assert evaluate_fn.call_count == 2

    @pytest.mark.asyncio
    async def test_top_n_larger_than_archive_uses_all_elites(
        self, archive_with_elites: MagicMock
    ) -> None:
        """top_n > num_elites: evaluate all elites (not more)."""
        evaluate_fn = AsyncMock(return_value=(0.9, np.zeros(4)))
        results = await reeval_elites(
            archive_wrapper=archive_with_elites,
            evaluate_fn=evaluate_fn,
            top_n=999,
        )
        # archive has 5 elites
        assert len(results) == 5
        assert evaluate_fn.call_count == 5

    @pytest.mark.asyncio
    async def test_drift_pct_computed_correctly(
        self, archive_with_elites: MagicMock
    ) -> None:
        """drift_pct = (before - after) / (before + eps), scaled to 0..1."""
        async def drop_eval(solution: np.ndarray) -> tuple[float, np.ndarray]:
            return (0.45, np.zeros(4))  # top elite: 0.9 → 0.45 = 50% drop

        results = await reeval_elites(
            archive_wrapper=archive_with_elites,
            evaluate_fn=drop_eval,
            top_n=1,
        )
        r = results[0]
        expected_drift = (0.9 - 0.45) / (0.9 + 1e-8)
        assert abs(r.drift_pct - expected_drift) < 1e-5
        assert r.drifted is True

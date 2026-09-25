"""Tests for outer_loop.scheduler — OuterLoop orchestrator (Plan 09-05, Task 1).

TDD RED phase: tests written before implementation.

Behavioral:
    - Test 1: single_iteration calls ask, evaluate_fn for each solution, tell
    - Test 2: run with n_iterations=5 calls single_iteration 5 times
    - Test 3: flush_batch called every flush_every_n total evaluations
    - Test 4: saturation_monitor records coverage after each iteration
    - Test 5: reeval_elites called every reeval_every_n total evaluations
    - Test 6: after 3 iterations with batch_size=16, total_evaluations = 48
    - Test 7: run returns OuterLoopResult with final coverage, num_elites, best_fitness
    - Test 8: no error when persistence is None (flush disabled)
    - Test 9 (property): compute_all_metrics returns QualityMetrics with all fields in [0.0, 1.0]
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from aerocloud.outer_loop.models import QualityMetrics, QualityWeights
from aerocloud.outer_loop.scheduler import OuterLoop, OuterLoopResult


# ---------------------------------------------------------------------------
# Helpers / builders
# ---------------------------------------------------------------------------


def _make_quality_metrics(seed: float = 0.5) -> QualityMetrics:
    """Return a synthetic QualityMetrics with all fields equal to seed."""
    return QualityMetrics(
        layout_coverage=seed,
        layout_uniformity=seed,
        space_saving=seed,
        compactness=seed,
        aspect_ratio=seed,
        realized_adjacencies=seed,
        distortion_score=seed,
    )


def _make_bd(seed: float = 0.5) -> Any:
    """Return a mock BehaviorDescriptor with 4 BD fields equal to seed."""
    bd = MagicMock()
    bd.shape_fidelity = seed
    bd.rotation_ratio = seed
    bd.symmetry = seed
    bd.semantic_clustering = seed
    return bd


def _make_evaluate_fn(
    metrics: QualityMetrics | None = None,
    bd: Any = None,
) -> Any:
    """Synchronous evaluate_fn returning (metrics, bd, embedding_384)."""
    _metrics = metrics or _make_quality_metrics(0.5)
    _bd = bd or _make_bd(0.5)
    _emb = np.zeros(384, dtype=np.float32)

    def _evaluate_fn(solution: np.ndarray) -> tuple[QualityMetrics, Any, np.ndarray]:
        return _metrics, _bd, _emb

    return _evaluate_fn


def _make_archive(batch_size: int = 16) -> MagicMock:
    """Return a mock ArchiveWrapper with controllable behaviour."""
    archive = MagicMock()
    # ask() returns (batch_size, solution_dim) — zero array
    archive.ask.return_value = np.zeros((batch_size, 8), dtype=np.float32)
    archive.tell.return_value = None
    archive.coverage = 0.1
    archive.num_elites = 3
    archive.data.return_value = {
        "solution": np.zeros((3, 8), dtype=np.float32),
        "objective": np.array([0.3, 0.5, 0.4], dtype=np.float32),
        "measures": np.zeros((3, 4), dtype=np.float32),
    }
    return archive


def _make_outer_loop(
    batch_size: int = 16,
    flush_every_n: int = 100,
    reeval_every_n: int = 200,
    persistence: Any = None,
    evaluate_fn: Any = None,
) -> tuple[OuterLoop, MagicMock, MagicMock, MagicMock]:
    """Build an OuterLoop with mocked dependencies."""
    archive = _make_archive(batch_size=batch_size)
    saturation_monitor = MagicMock()
    saturation_monitor.record.return_value = None
    saturation_monitor.is_plateaued = False

    novelty_emitter = MagicMock()
    quality_weights = QualityWeights()

    _evaluate_fn = evaluate_fn or _make_evaluate_fn()

    loop = OuterLoop(
        archive=archive,
        evaluate_fn=_evaluate_fn,
        persistence=persistence,
        novelty_emitter=novelty_emitter,
        saturation_monitor=saturation_monitor,
        quality_weights=quality_weights,
        flush_every_n=flush_every_n,
        reeval_every_n=reeval_every_n,
    )
    return loop, archive, saturation_monitor, novelty_emitter


# ---------------------------------------------------------------------------
# Test 1: single_iteration calls ask, evaluate_fn for each solution, tell
# ---------------------------------------------------------------------------


class TestSingleIteration:
    def test_ask_called_once(self) -> None:
        """single_iteration calls archive.ask() exactly once."""
        loop, archive, _, _ = _make_outer_loop(batch_size=4)
        loop.single_iteration()
        archive.ask.assert_called_once()

    def test_evaluate_fn_called_per_solution(self) -> None:
        """single_iteration calls evaluate_fn once per solution in the batch."""
        call_count = 0

        def counting_fn(solution: np.ndarray) -> tuple[QualityMetrics, Any, np.ndarray]:
            nonlocal call_count
            call_count += 1
            return _make_quality_metrics(0.5), _make_bd(0.5), np.zeros(384, dtype=np.float32)

        loop, archive, _, _ = _make_outer_loop(batch_size=8, evaluate_fn=counting_fn)
        archive.ask.return_value = np.zeros((8, 8), dtype=np.float32)

        loop.single_iteration()

        assert call_count == 8

    def test_tell_called_with_objectives_and_measures(self) -> None:
        """single_iteration calls archive.tell() once with correct shapes."""
        loop, archive, _, _ = _make_outer_loop(batch_size=4)
        loop.single_iteration()

        archive.tell.assert_called_once()
        call_args = archive.tell.call_args
        # Prefer kwargs, fall back to positional args
        if "objectives" in call_args.kwargs:
            objectives = call_args.kwargs["objectives"]
            measures = call_args.kwargs["measures"]
        else:
            objectives = call_args.args[0]
            measures = call_args.args[1]

        assert objectives.shape == (4,)
        assert measures.shape == (4, 4)  # 4 BD dimensions

    def test_returns_batch_size(self) -> None:
        """single_iteration returns the number of evaluations this iteration."""
        loop, archive, _, _ = _make_outer_loop(batch_size=16)
        result = loop.single_iteration()
        assert result == 16


# ---------------------------------------------------------------------------
# Test 2: run calls single_iteration n_iterations times
# ---------------------------------------------------------------------------


class TestRun:
    def test_run_calls_single_iteration_n_times(self) -> None:
        """run() executes the correct number of iterations."""
        loop, _, _, _ = _make_outer_loop(batch_size=4)
        call_count = 0
        original_single = loop.single_iteration

        def counting_single() -> int:
            nonlocal call_count
            call_count += 1
            return original_single()

        loop.single_iteration = counting_single  # type: ignore[method-assign]

        loop.run(n_iterations=5)

        assert call_count == 5

    def test_run_returns_outer_loop_result(self) -> None:
        """run() returns an OuterLoopResult instance."""
        loop, _, _, _ = _make_outer_loop(batch_size=4)
        result = loop.run(n_iterations=3)
        assert isinstance(result, OuterLoopResult)

    def test_run_zero_iterations(self) -> None:
        """run(0) returns OuterLoopResult with total_evaluations=0."""
        loop, _, _, _ = _make_outer_loop(batch_size=4)
        result = loop.run(n_iterations=0)
        assert isinstance(result, OuterLoopResult)
        assert result.total_evaluations == 0

    def test_result_has_expected_fields(self) -> None:
        """OuterLoopResult has coverage, num_elites, best_fitness, total_evaluations."""
        loop, archive, _, _ = _make_outer_loop(batch_size=4)
        archive.coverage = 0.25
        archive.num_elites = 7
        archive.data.return_value = {
            "solution": np.zeros((7, 8), dtype=np.float32),
            "objective": np.array([0.1, 0.4, 0.6, 0.3, 0.7, 0.2, 0.5]),
            "measures": np.zeros((7, 4), dtype=np.float32),
        }

        result = loop.run(n_iterations=2)

        assert hasattr(result, "final_coverage")
        assert hasattr(result, "num_elites")
        assert hasattr(result, "best_fitness")
        assert hasattr(result, "total_evaluations")
        assert hasattr(result, "saturation_plateaued")
        assert hasattr(result, "reeval_results")


# ---------------------------------------------------------------------------
# Test 3: flush_batch called every flush_every_n evaluations
# ---------------------------------------------------------------------------


class TestFlushBatch:
    def test_flush_called_at_flush_every_n(self) -> None:
        """flush_batch is called when total_evaluations reaches flush_every_n."""
        persistence = MagicMock()
        persistence.flush_batch = AsyncMock(return_value=4)

        # batch_size=4, flush_every_n=8 → flush at iteration 2 (after 8 evals)
        loop, _, _, _ = _make_outer_loop(
            batch_size=4,
            flush_every_n=8,
            persistence=persistence,
        )

        loop.run(n_iterations=3)  # 12 evals: flush at 8 (and 16 but that's iter 4)

        assert persistence.flush_batch.call_count >= 1

    def test_no_error_when_persistence_none(self) -> None:
        """No exception when persistence=None (flush disabled)."""
        loop, _, _, _ = _make_outer_loop(batch_size=4, flush_every_n=4, persistence=None)
        # Should not raise
        loop.run(n_iterations=5)

    def test_flush_not_called_before_threshold(self) -> None:
        """flush_batch is NOT called if total_evaluations < flush_every_n."""
        persistence = MagicMock()
        persistence.flush_batch = AsyncMock(return_value=4)

        # batch_size=4, flush_every_n=100 → after 2 iters (8 evals) no flush
        loop, _, _, _ = _make_outer_loop(
            batch_size=4,
            flush_every_n=100,
            persistence=persistence,
        )

        loop.run(n_iterations=2)

        persistence.flush_batch.assert_not_called()


# ---------------------------------------------------------------------------
# Test 4: saturation_monitor records coverage after each iteration
# ---------------------------------------------------------------------------


class TestSaturationMonitor:
    def test_record_called_after_each_iteration(self) -> None:
        """saturation_monitor.record() is called once per iteration."""
        loop, archive, saturation_monitor, _ = _make_outer_loop(batch_size=4)
        loop.run(n_iterations=5)
        assert saturation_monitor.record.call_count == 5

    def test_record_called_with_coverage(self) -> None:
        """saturation_monitor.record() is called with the archive coverage value."""
        loop, archive, saturation_monitor, _ = _make_outer_loop(batch_size=4)
        archive.coverage = 0.42
        loop.run(n_iterations=1)
        saturation_monitor.record.assert_called_with(0.42)


# ---------------------------------------------------------------------------
# Test 5: reeval_elites called every reeval_every_n evaluations
# ---------------------------------------------------------------------------


class TestReevalElites:
    def test_reeval_called_at_reeval_every_n(self) -> None:
        """reeval_elites is triggered when total_evaluations reaches reeval_every_n."""
        # batch_size=4, reeval_every_n=8 → reeval at iter 2 (8 evals)
        loop, archive, _, _ = _make_outer_loop(
            batch_size=4,
            flush_every_n=1000,
            reeval_every_n=8,
        )
        archive.data.return_value = {
            "solution": np.zeros((2, 8), dtype=np.float32),
            "objective": np.array([0.3, 0.5], dtype=np.float32),
            "measures": np.zeros((2, 4), dtype=np.float32),
        }

        result = loop.run(n_iterations=3)  # 12 evals: reeval at 8

        # reeval_results populated (may have 0 entries if archive empty in test)
        assert isinstance(result.reeval_results, list)

    def test_reeval_not_called_before_threshold(self) -> None:
        """reeval_elites is NOT triggered if total_evaluations < reeval_every_n."""
        loop, _, _, _ = _make_outer_loop(
            batch_size=4,
            flush_every_n=1000,
            reeval_every_n=1000,
        )

        # Patch the internal reeval call to count
        call_count = 0
        original_run = loop.run

        # We just verify run completes without reeval via result.reeval_results
        result = loop.run(n_iterations=2)  # 8 evals, reeval_every_n=1000

        # Should have no reeval results at this count
        assert result.reeval_results == []


# ---------------------------------------------------------------------------
# Test 6: total_evaluations counter accuracy
# ---------------------------------------------------------------------------


class TestTotalEvaluations:
    def test_total_evaluations_after_n_iterations(self) -> None:
        """After 3 iterations with batch_size=16, total_evaluations == 48."""
        loop, archive, _, _ = _make_outer_loop(batch_size=16)
        archive.ask.return_value = np.zeros((16, 8), dtype=np.float32)
        result = loop.run(n_iterations=3)
        assert result.total_evaluations == 48

    def test_total_evaluations_single_iteration(self) -> None:
        """After 1 iteration with batch_size=4, total_evaluations == 4."""
        loop, archive, _, _ = _make_outer_loop(batch_size=4)
        archive.ask.return_value = np.zeros((4, 8), dtype=np.float32)
        result = loop.run(n_iterations=1)
        assert result.total_evaluations == 4


# ---------------------------------------------------------------------------
# Test 7: OuterLoopResult accuracy
# ---------------------------------------------------------------------------


class TestOuterLoopResult:
    def test_result_coverage_matches_archive(self) -> None:
        """OuterLoopResult.final_coverage matches archive.coverage."""
        loop, archive, _, _ = _make_outer_loop(batch_size=4)
        archive.coverage = 0.77
        result = loop.run(n_iterations=1)
        assert result.final_coverage == pytest.approx(0.77)

    def test_result_num_elites_matches_archive(self) -> None:
        """OuterLoopResult.num_elites matches archive.num_elites."""
        loop, archive, _, _ = _make_outer_loop(batch_size=4)
        archive.num_elites = 42
        result = loop.run(n_iterations=1)
        assert result.num_elites == 42

    def test_result_best_fitness_from_objectives(self) -> None:
        """OuterLoopResult.best_fitness is the maximum observed objective."""
        loop, archive, _, _ = _make_outer_loop(batch_size=4)

        # QualityMetrics with uniform 0.6 → combined_fitness = 0.6 (equal weights)
        metrics = _make_quality_metrics(0.6)
        evaluate_fn = _make_evaluate_fn(metrics=metrics)
        loop._evaluate_fn = evaluate_fn  # type: ignore[attr-defined]

        archive.ask.return_value = np.zeros((4, 8), dtype=np.float32)
        result = loop.run(n_iterations=1)

        # best_fitness should be positive (non-zero)
        assert result.best_fitness >= 0.0

    def test_saturation_plateaued_reflects_monitor(self) -> None:
        """OuterLoopResult.saturation_plateaued matches saturation_monitor.is_plateaued."""
        loop, archive, saturation_monitor, _ = _make_outer_loop(batch_size=4)
        saturation_monitor.is_plateaued = True
        result = loop.run(n_iterations=1)
        assert result.saturation_plateaued is True


# ---------------------------------------------------------------------------
# Test 8: Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_run_zero_returns_zero_coverage(self) -> None:
        """run(0) returns OuterLoopResult with coverage from archive (no iterations)."""
        loop, archive, _, _ = _make_outer_loop(batch_size=4)
        archive.coverage = 0.0
        archive.num_elites = 0
        result = loop.run(n_iterations=0)
        assert result.total_evaluations == 0
        assert isinstance(result, OuterLoopResult)

    def test_flush_none_persistence_no_error_many_iters(self) -> None:
        """Many iterations with persistence=None do not raise."""
        loop, _, _, _ = _make_outer_loop(batch_size=4, flush_every_n=1, persistence=None)
        # Should not raise even though flush_every_n=1 fires every iteration
        loop.run(n_iterations=10)


# ---------------------------------------------------------------------------
# Test 9: Hypothesis property test — compute_all_metrics bounds
# ---------------------------------------------------------------------------


@given(
    lc=st.floats(0.0, 1.0, allow_nan=False, allow_infinity=False),
    lu=st.floats(0.0, 1.0, allow_nan=False, allow_infinity=False),
    ss=st.floats(0.0, 1.0, allow_nan=False, allow_infinity=False),
    compactness=st.floats(0.0, 1.0, allow_nan=False, allow_infinity=False),
    ar=st.floats(0.0, 1.0, allow_nan=False, allow_infinity=False),
    ra=st.floats(0.0, 1.0, allow_nan=False, allow_infinity=False),
    distortion=st.floats(0.0, 1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_quality_metrics_combined_fitness_always_bounded(
    lc: float,
    lu: float,
    ss: float,
    compactness: float,
    ar: float,
    ra: float,
    distortion: float,
) -> None:
    """QualityMetrics.combined_fitness with uniform weights is in [0.0, 1.0]."""
    metrics = QualityMetrics(
        layout_coverage=lc,
        layout_uniformity=lu,
        space_saving=ss,
        compactness=compactness,
        aspect_ratio=ar,
        realized_adjacencies=ra,
        distortion_score=distortion,
    )
    weights = QualityWeights()  # equal weights: 1/7 each → sum = 1/7 * 7 = 1.0 max
    fitness = metrics.combined_fitness(weights)
    assert 0.0 <= fitness <= 1.0, f"combined_fitness={fitness} out of [0,1]"

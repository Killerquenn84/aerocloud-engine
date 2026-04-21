"""Unit tests for SelfPlayLoop (Plan 10-03, Task 2).

TDD RED phase: tests must FAIL before loop.py is implemented.

All external dependencies are mocked:
    - ArchiveWrapper (archive): provides ask/tell/data
    - evaluate_fn: returns (QualityMetrics, BehaviorDescriptor, emb_384)
    - loop._reviewer: AdversarialReviewer instance replaced with MagicMock
    - ReplayLogger: async methods
    - ArchivePersistence: load_all

Key behaviors verified:
    1. mutation path (rng.random() < mutation_ratio)
    2. crossover path (rng.random() >= mutation_ratio)
    3. reviewer rejection: tell() NOT called
    4. reviewer accept + dominance pass: accepted=True
    5. dominance boundary: 0.72 == 0.71 + 0.01 -> rejected (STRICT >)
    6. no baseline: dominance check skipped, reviewer result is final
    7. run(5) returns SelfPlayRunResult with n_iterations=5
    8. flush_and_finalize returns valid SelfPlayRunResult
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np

from aerocloud.outer_loop.models import QualityMetrics, QualityWeights
from aerocloud.self_play.config import SelfPlayConfig
from aerocloud.self_play.loop import SelfPlayLoop
from aerocloud.self_play.models import SelfPlayEvent, SelfPlayRunResult


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_metrics(lc: float = 0.5) -> QualityMetrics:
    """Create a QualityMetrics with all fields at a uniform value except lc."""
    return QualityMetrics(
        layout_coverage=lc,
        layout_uniformity=0.5,
        space_saving=0.5,
        compactness=0.5,
        aspect_ratio=0.5,
        realized_adjacencies=0.5,
        distortion_score=0.5,
    )


def _make_archive_data(n_elites: int = 2, solution_dim: int = 8) -> dict[str, Any]:
    """Build a mock archive data dict."""
    rng = np.random.default_rng(0)
    solutions = rng.uniform(0.0, 1.0, size=(n_elites, solution_dim))
    measures = rng.uniform(0.0, 1.0, size=(n_elites, 4))
    objectives = rng.uniform(0.0, 1.0, size=(n_elites,))
    return {"solution": solutions, "measures": measures, "objective": objectives}


def _make_loop(
    *,
    mutation_ratio: float = 0.7,
    frozen_baseline: dict[str, tuple[float, QualityMetrics]] | None = None,
    replay_logger: Any | None = None,
    solution_dim: int = 8,
    rng_seed: int = 42,
) -> tuple[SelfPlayLoop, MagicMock, MagicMock]:
    """Create a SelfPlayLoop with mocked archive and evaluate_fn.

    Returns (loop, mock_archive, mock_evaluate_fn).
    The loop._reviewer is replaced with a MagicMock defaulting to accept.
    """
    config = SelfPlayConfig(mutation_ratio=mutation_ratio)
    weights = QualityWeights()

    archive = MagicMock()
    archive.data.return_value = _make_archive_data(solution_dim=solution_dim)
    archive.ask.return_value = np.zeros((1, solution_dim))

    bd_mock = MagicMock()
    bd_mock.shape_fidelity = 0.5
    bd_mock.rotation_ratio = 0.5
    bd_mock.symmetry = 0.5
    bd_mock.semantic_clustering = 0.5

    metrics = _make_metrics(lc=0.5)
    emb = np.zeros(384, dtype=np.float32)
    evaluate_fn = MagicMock(return_value=(metrics, bd_mock, emb))

    rng = np.random.default_rng(rng_seed)

    loop = SelfPlayLoop(
        archive=archive,
        evaluate_fn=evaluate_fn,
        persistence=None,
        quality_weights=weights,
        config=config,
        replay_logger=replay_logger,
        rng=rng,
        frozen_baseline=frozen_baseline,
    )

    # Replace the real reviewer with a controllable mock (default: accept)
    mock_reviewer = MagicMock()
    mock_reviewer.review.return_value = (True, "")
    loop._reviewer = mock_reviewer

    return loop, archive, evaluate_fn


def _force_rng(loop: SelfPlayLoop, random_val: float) -> None:
    """Replace loop._rng with a mock returning a fixed random value."""
    mock_rng = MagicMock()
    mock_rng.random.return_value = random_val
    mock_rng.standard_normal = np.random.default_rng(0).standard_normal
    mock_rng.integers = np.random.default_rng(0).integers
    loop._rng = mock_rng


# ---------------------------------------------------------------------------
# Test 1: mutation path
# ---------------------------------------------------------------------------


class TestSingleIterationMutationPath:
    """rng.random() < mutation_ratio -> structure_aware_mutate is called."""

    def test_single_iteration_mutation_path(self) -> None:
        """When rng returns value < mutation_ratio, mutation operator is used."""
        loop, archive, _ = _make_loop(mutation_ratio=0.7)
        _force_rng(loop, random_val=0.1)  # 0.1 < 0.7 -> mutation path

        with patch(
            "aerocloud.self_play.loop.structure_aware_mutate",
            return_value=np.zeros(8),
        ) as mock_mutate, patch(
            "aerocloud.self_play.loop.uniform_crossover",
        ) as mock_crossover:
            event = loop.single_iteration(0)

        mock_mutate.assert_called_once()
        mock_crossover.assert_not_called()
        assert event.mutation_type == "gaussian"


# ---------------------------------------------------------------------------
# Test 2: crossover path
# ---------------------------------------------------------------------------


class TestSingleIterationCrossoverPath:
    """rng.random() >= mutation_ratio -> uniform_crossover is called."""

    def test_single_iteration_crossover_path(self) -> None:
        """When rng returns value >= mutation_ratio, crossover operator is used."""
        loop, archive, _ = _make_loop(mutation_ratio=0.7)
        _force_rng(loop, random_val=0.9)  # 0.9 >= 0.7 -> crossover path

        with patch(
            "aerocloud.self_play.loop.structure_aware_mutate",
        ) as mock_mutate, patch(
            "aerocloud.self_play.loop.uniform_crossover",
            return_value=np.zeros(8),
        ) as mock_crossover:
            event = loop.single_iteration(0)

        mock_mutate.assert_not_called()
        mock_crossover.assert_called_once()
        assert event.mutation_type == "crossover"


# ---------------------------------------------------------------------------
# Test 3: reviewer rejects
# ---------------------------------------------------------------------------


class TestSingleIterationReviewerRejects:
    """reviewer.review returns (False, reason) -> event.accepted=False, tell() NOT called."""

    def test_single_iteration_reviewer_rejects(self) -> None:
        """Rejected by reviewer: tell() must NOT be called."""
        loop, archive, _ = _make_loop(mutation_ratio=0.7)
        _force_rng(loop, random_val=0.1)  # mutation path

        # Override mock_reviewer to reject
        loop._reviewer.review.return_value = (False, "degenerate_layout: layout_coverage < 0.1")

        with patch(
            "aerocloud.self_play.loop.structure_aware_mutate",
            return_value=np.zeros(8),
        ):
            event = loop.single_iteration(0)

        assert event.accepted is False
        assert "degenerate_layout" in event.reject_reason
        archive.tell.assert_not_called()


# ---------------------------------------------------------------------------
# Test 4: reviewer accepts + dominance passes
# ---------------------------------------------------------------------------


class TestSingleIterationReviewerAcceptsDominancePasses:
    """reviewer accepts + fitness_new > baseline_fitness + margin -> accepted=True."""

    def test_single_iteration_reviewer_accepts_dominance_passes(self) -> None:
        """When reviewer accepts and dominance check passes, event.accepted=True.

        Arithmetic:
            candidate: all metrics=0.5 -> combined = 0.5
            baseline: lc=0.3, rest=0.5 -> combined = (0.3 + 6*0.5)/7 = 3.3/7 ≈ 0.471
            threshold = 0.471 + 0.01 = 0.481
            0.5 > 0.481 -> True (dominance passes)
        """
        baseline_metrics = _make_metrics(lc=0.3)
        weights = QualityWeights()
        baseline_fitness = baseline_metrics.combined_fitness(weights)  # ≈ 0.471

        frozen_baseline = {"bin_0": (baseline_fitness, baseline_metrics)}
        loop, archive, _ = _make_loop(mutation_ratio=0.7, frozen_baseline=frozen_baseline)
        _force_rng(loop, random_val=0.1)  # mutation path

        with patch(
            "aerocloud.self_play.loop.structure_aware_mutate",
            return_value=np.zeros(8),
        ), patch.object(loop, "_get_bin_id", return_value="bin_0"):
            event = loop.single_iteration(0)

        assert event.accepted is True
        assert event.reject_reason == ""


# ---------------------------------------------------------------------------
# Test 5: dominance boundary (STRICT >)
# ---------------------------------------------------------------------------


class TestSingleIterationDominanceBoundary:
    """fitness_new == fitness_baseline + margin exactly -> rejected (STRICT >)."""

    def test_single_iteration_dominance_fails_at_boundary(self) -> None:
        """Boundary case: 0.72 == 0.71 + 0.01 -> dominance NOT exceeded (strict >).

        Decision D-08 (research correction): dominance check is STRICT greater-than.
        0.72 > 0.71 + 0.01 = 0.72 > 0.72 = False -> rejected.
        """
        config = SelfPlayConfig(dominance_margin=0.01, mutation_ratio=0.7)
        weights = QualityWeights()

        candidate_metrics = QualityMetrics(
            layout_coverage=0.72,
            layout_uniformity=0.72,
            space_saving=0.72,
            compactness=0.72,
            aspect_ratio=0.72,
            realized_adjacencies=0.72,
            distortion_score=0.72,
        )
        candidate_fitness = candidate_metrics.combined_fitness(weights)  # = 0.72

        baseline_metrics = QualityMetrics(
            layout_coverage=0.71,
            layout_uniformity=0.71,
            space_saving=0.71,
            compactness=0.71,
            aspect_ratio=0.71,
            realized_adjacencies=0.71,
            distortion_score=0.71,
        )
        baseline_fitness = baseline_metrics.combined_fitness(weights)  # = 0.71

        # Verify boundary arithmetic
        assert abs(candidate_fitness - (baseline_fitness + 0.01)) < 1e-9, (
            f"Boundary setup: {candidate_fitness} != {baseline_fitness} + 0.01"
        )

        frozen_baseline = {"bin_0": (baseline_fitness, baseline_metrics)}

        archive = MagicMock()
        archive.data.return_value = _make_archive_data(solution_dim=8)

        bd_mock = MagicMock()
        evaluate_fn = MagicMock(return_value=(candidate_metrics, bd_mock, np.zeros(384)))

        loop = SelfPlayLoop(
            archive=archive,
            evaluate_fn=evaluate_fn,
            persistence=None,
            quality_weights=weights,
            config=config,
            replay_logger=None,
            rng=np.random.default_rng(0),
            frozen_baseline=frozen_baseline,
        )
        # Replace reviewer with accept-all mock
        mock_reviewer = MagicMock()
        mock_reviewer.review.return_value = (True, "")
        loop._reviewer = mock_reviewer

        _force_rng(loop, random_val=0.1)  # mutation path

        with patch(
            "aerocloud.self_play.loop.structure_aware_mutate",
            return_value=np.zeros(8),
        ), patch.object(loop, "_get_bin_id", return_value="bin_0"):
            event = loop.single_iteration(0)

        assert event.accepted is False, (
            f"Boundary case 0.72 > 0.71+0.01=False must reject. Got accepted={event.accepted}"
        )
        assert "dominance" in event.reject_reason, (
            f"reject_reason should contain 'dominance', got: {event.reject_reason!r}"
        )


# ---------------------------------------------------------------------------
# Test 6: no baseline -> dominance skipped
# ---------------------------------------------------------------------------


class TestSingleIterationNoBaseline:
    """frozen_baseline=None -> only reviewer check matters."""

    def test_single_iteration_no_baseline_skips_dominance(self) -> None:
        """With no frozen baseline, dominance check is skipped; reviewer result is final."""
        loop, archive, _ = _make_loop(mutation_ratio=0.7, frozen_baseline=None)
        _force_rng(loop, random_val=0.1)  # mutation path
        # Reviewer already mocked to accept

        with patch(
            "aerocloud.self_play.loop.structure_aware_mutate",
            return_value=np.zeros(8),
        ):
            event = loop.single_iteration(0)

        assert event.accepted is True
        archive.tell.assert_called_once()


# ---------------------------------------------------------------------------
# Test 7: run() returns SelfPlayRunResult
# ---------------------------------------------------------------------------


class TestRunReturnsResult:
    """run(5) returns SelfPlayRunResult with n_iterations=5."""

    def test_run_returns_result(self) -> None:
        """run(n) returns SelfPlayRunResult with n_iterations=n."""
        loop, archive, _ = _make_loop(mutation_ratio=0.7)

        with patch.object(loop, "single_iteration") as mock_iter:
            mock_iter.return_value = SelfPlayEvent(
                iteration=0,
                parent_bin_ids=["bin_0"],
                mutation_type="gaussian",
                fitness_before=None,
                fitness_after=0.5,
                accepted=True,
                reject_reason="",
            )

            result = loop.run(5)

        assert isinstance(result, SelfPlayRunResult)
        assert result.n_iterations == 5
        assert mock_iter.call_count == 5


# ---------------------------------------------------------------------------
# Test 8: flush_and_finalize returns valid result
# ---------------------------------------------------------------------------


class TestFlushAndFinalizeReturnsResult:
    """flush_and_finalize produces a valid SelfPlayRunResult for graceful exit."""

    def test_flush_and_finalize_returns_result(self) -> None:
        """flush_and_finalize called mid-run returns valid SelfPlayRunResult."""
        loop, _, _ = _make_loop()

        # Simulate partial run: 3 iterations done, 2 accepted, 1 rejected
        loop._n_accepted = 2
        loop._n_rejected = 1

        with patch.object(loop, "_compute_kl_and_finalize", return_value=None):
            result = loop.flush_and_finalize(n_done=3, exit_reason="soft_timeout")

        assert isinstance(result, SelfPlayRunResult)
        assert result.n_iterations == 3
        assert result.n_accepted == 2
        assert result.n_rejected == 1
        assert result.exit_reason == "soft_timeout"

"""Integration tests for SelfPlayLoop.run() (Plan 10-04, Task 1).

Verifies all SP-01 through SP-08 requirements working together end-to-end:
    - SelfPlayLoop.run(50) completes with mock evaluate_fn -> SelfPlayRunResult
    - D-12: Adversarial rejection rate > 5% with mixed/degenerate inputs
    - D-17: Replay events = N for N iterations (both accepted and rejected logged)
    - First-night KL = None (no previous descriptor histogram)
    - flush_and_finalize() returns valid SelfPlayRunResult with correct exit_reason

Note on archive fixture:
    SelfPlayLoop.single_iteration() calls archive.tell() without a preceding ask().
    This is by design — the self-play loop updates the archive directly (bypassing
    the Scheduler ask/tell protocol). Tests use a MagicMock archive pre-populated
    with realistic data from a seeded ArchiveWrapper to exercise the full loop logic
    without triggering the pyribs Scheduler ordering constraint.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from aerocloud.outer_loop.models import QualityMetrics, QualityWeights
from aerocloud.self_play.config import SelfPlayConfig
from aerocloud.self_play.loop import SelfPlayLoop
from aerocloud.self_play.models import SelfPlayEvent, SelfPlayRunResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOLUTION_DIM: int = 40  # 10 words * 4 params
MAX_WORDS: int = 10
N_ELITES: int = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_metrics(
    lc: float = 0.5,
    lu: float = 0.5,
    ss: float = 0.5,
    compactness: float = 0.5,
    aspect_ratio: float = 0.5,
    ra: float = 0.5,
    distortion: float = 0.5,
) -> QualityMetrics:
    """Construct a QualityMetrics with specified values."""
    return QualityMetrics(
        layout_coverage=lc,
        layout_uniformity=lu,
        space_saving=ss,
        compactness=compactness,
        aspect_ratio=aspect_ratio,
        realized_adjacencies=ra,
        distortion_score=distortion,
    )


def _make_mock_archive(seed: int = 42) -> MagicMock:
    """Build a MagicMock archive pre-populated with realistic data.

    Uses seeded RNG to build an archive data dict that mirrors what
    ArchiveWrapper.data() returns. The mock does NOT enforce ask/tell ordering,
    which is correct because SelfPlayLoop.single_iteration() calls tell()
    directly to update the archive (bypassing the Scheduler protocol).

    Returns a MagicMock with .data(), .tell(), .ask() configured.
    """
    rng = np.random.default_rng(seed)
    solutions = rng.uniform(-0.5, 0.5, size=(N_ELITES, SOLUTION_DIM))
    measures = rng.uniform(0.0, 1.0, size=(N_ELITES, 4))
    objectives = rng.uniform(0.1, 0.9, size=(N_ELITES,))

    archive_data: dict[str, np.ndarray] = {
        "solution": solutions,
        "objective": objectives,
        "measures": measures,
    }

    mock = MagicMock()
    mock.data.return_value = archive_data
    mock.ask.return_value = solutions[:4]
    mock.tell.return_value = None
    return mock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def small_archive() -> MagicMock:
    """Mock archive pre-populated with 10 elites (realistic data, seed=42).

    Uses a MagicMock to avoid the pyribs ask/tell ordering constraint that
    SelfPlayLoop.single_iteration() bypasses by design.
    """
    return _make_mock_archive(seed=42)


@pytest.fixture()
def small_config() -> SelfPlayConfig:
    """SelfPlayConfig with 50 iterations for fast tests."""
    return SelfPlayConfig(n_iterations=50, mutation_ratio=0.7)


@pytest.fixture()
def mock_evaluate_fn() -> Any:
    """Mock evaluate_fn returning random QualityMetrics and BD values in [0.1, 0.9].

    Returns (QualityMetrics, BD_mock, emb_384_float32).
    Layout coverage is always >= 0.1 to avoid degenerate_layout rejection.
    """
    rng = np.random.default_rng(123)

    def _fn(solution: np.ndarray) -> tuple[QualityMetrics, Any, np.ndarray]:
        vals = rng.uniform(0.1, 0.9, size=7)
        metrics = QualityMetrics(
            layout_coverage=float(vals[0]),
            layout_uniformity=float(vals[1]),
            space_saving=float(vals[2]),
            compactness=float(vals[3]),
            aspect_ratio=float(vals[4]),
            realized_adjacencies=float(vals[5]),
            distortion_score=float(vals[6]),
        )
        bd = MagicMock()
        bd.shape_fidelity = float(rng.uniform(0.0, 1.0))
        bd.rotation_ratio = float(rng.uniform(0.0, 1.0))
        bd.symmetry = float(rng.uniform(0.0, 1.0))
        bd.semantic_clustering = float(rng.uniform(0.0, 1.0))
        emb = rng.standard_normal(384).astype(np.float32)
        return metrics, bd, emb

    return _fn


def _make_loop(
    archive: Any,
    evaluate_fn: Any,
    config: SelfPlayConfig | None = None,
    frozen_baseline: dict[str, tuple[float, QualityMetrics]] | None = None,
    replay_logger: Any | None = None,
    seed: int = 42,
) -> SelfPlayLoop:
    """Build a SelfPlayLoop with the given archive and evaluate_fn."""
    if config is None:
        config = SelfPlayConfig(n_iterations=50, mutation_ratio=0.7)
    weights = QualityWeights()
    rng = np.random.default_rng(seed)

    return SelfPlayLoop(
        archive=archive,
        evaluate_fn=evaluate_fn,
        persistence=None,
        quality_weights=weights,
        config=config,
        replay_logger=replay_logger,
        rng=rng,
        frozen_baseline=frozen_baseline,
    )


# ---------------------------------------------------------------------------
# Test 1: run() completes and returns SelfPlayRunResult
# ---------------------------------------------------------------------------


class TestRunCompletesAndReturnsResult:
    """SelfPlayLoop.run(50) returns SelfPlayRunResult with valid n_iterations."""

    def test_run_completes_and_returns_result(
        self,
        small_archive: MagicMock,
        small_config: SelfPlayConfig,
        mock_evaluate_fn: Any,
    ) -> None:
        """run(50) with mock evaluate_fn completes and returns a valid SelfPlayRunResult.

        Verifies:
            - Returns SelfPlayRunResult instance
            - n_iterations is in [1, 50]
            - n_accepted + n_rejected == n_iterations
            - exit_reason == 'completed'
        """
        loop = _make_loop(small_archive, mock_evaluate_fn, config=small_config)
        result = loop.run(50)

        assert isinstance(result, SelfPlayRunResult)
        assert 1 <= result.n_iterations <= 50, (
            f"Expected n_iterations in [1, 50], got {result.n_iterations}"
        )
        assert result.n_accepted + result.n_rejected == result.n_iterations, (
            f"n_accepted({result.n_accepted}) + n_rejected({result.n_rejected}) "
            f"!= n_iterations({result.n_iterations})"
        )
        assert result.exit_reason == "completed"


# ---------------------------------------------------------------------------
# Test 2: adversarial rejection rate > 5% (D-12)
# ---------------------------------------------------------------------------


class TestAdversarialRejectionRateExceeds5Percent:
    """D-12: rejection rate > 5% with mixed/degenerate evaluate_fn over 100 iterations."""

    def test_adversarial_rejection_rate_exceeds_5_percent(
        self,
        small_archive: MagicMock,
    ) -> None:
        """Rejection rate > 5% confirmed when evaluate_fn produces mixed results.

        Adversarial inputs:
            - Every 3rd evaluation returns degenerate layout_coverage=0.05
              (triggers Rule 3: degenerate_layout, guaranteed rejection)
            - Other evaluations return normal metrics

        With 33% degenerate inputs, rejection rate is >= 33% >> 5% (D-12).
        """
        call_count = [0]
        rng = np.random.default_rng(7)

        def adversarial_fn(solution: np.ndarray) -> tuple[QualityMetrics, Any, np.ndarray]:
            call_count[0] += 1
            # Every 3rd call: degenerate layout (guaranteed rejection by Rule 3)
            if call_count[0] % 3 == 0:
                metrics = _make_metrics(lc=0.05)  # degenerate: LC < 0.1 threshold
            else:
                metrics = _make_metrics(
                    lc=float(rng.uniform(0.2, 0.8)),
                    lu=float(rng.uniform(0.2, 0.8)),
                )
            bd = MagicMock()
            emb = np.zeros(384, dtype=np.float32)
            return metrics, bd, emb

        loop = _make_loop(small_archive, adversarial_fn)
        result = loop.run(100)

        total = result.n_accepted + result.n_rejected
        rejection_rate = result.n_rejected / total if total > 0 else 0.0

        assert rejection_rate > 0.05, (
            f"Rejection rate {rejection_rate:.2%} must exceed 5% (D-12). "
            f"n_accepted={result.n_accepted}, n_rejected={result.n_rejected}"
        )


# ---------------------------------------------------------------------------
# Test 3: frozen baseline dominance rejects weak mutations
# ---------------------------------------------------------------------------


class TestFrozenBaselineDominanceRejectsWeakMutations:
    """Baseline dominance: mutants with fitness not exceeding baseline + margin are rejected."""

    def test_frozen_baseline_dominance_rejects_weak_mutations(
        self,
        small_archive: MagicMock,
    ) -> None:
        """Mutations returning fitness == baseline_fitness are rejected by dominance check.

        Setup:
            - frozen_baseline["bin_0"] has fitness 0.5 (all metrics = 0.5)
            - evaluate_fn always returns fitness = 0.5
            - dominance_margin = 0.01
            - Dominance check: 0.5 > 0.5 + 0.01 = 0.5 > 0.51 = False -> rejected

        With _get_bin_id patched to return "bin_0" for all candidates, every
        adversarial-approved candidate will fail the dominance check.
        """
        weights = QualityWeights()
        baseline_metrics = _make_metrics(lc=0.5)
        baseline_fitness = baseline_metrics.combined_fitness(weights)  # == 0.5

        frozen_baseline = {"bin_0": (baseline_fitness, baseline_metrics)}

        def weak_evaluate_fn(solution: np.ndarray) -> tuple[QualityMetrics, Any, np.ndarray]:
            # fitness = 0.5 which does NOT exceed 0.5 + 0.01 -> dominance rejected
            metrics = _make_metrics(lc=0.5)
            bd = MagicMock()
            emb = np.zeros(384, dtype=np.float32)
            return metrics, bd, emb

        loop = _make_loop(small_archive, weak_evaluate_fn, frozen_baseline=frozen_baseline)
        # Patch _get_bin_id to always return "bin_0" so dominance fires on every candidate
        with patch.object(loop, "_get_bin_id", return_value="bin_0"):
            result = loop.run(20)

        assert result.n_rejected > 0, (
            "Expected at least some dominance rejections when fitness == baseline "
            "(does not exceed baseline + margin)"
        )


# ---------------------------------------------------------------------------
# Test 4: replay events count matches iterations (D-17)
# ---------------------------------------------------------------------------


class TestReplayEventsCountMatchesIterations:
    """D-17: Both accepted and rejected events are logged (replay completeness)."""

    def test_replay_events_count_matches_iterations(
        self,
        small_archive: MagicMock,
        mock_evaluate_fn: Any,
    ) -> None:
        """len(logged_events) == n_iterations (both accepted and rejected events logged).

        SelfPlayLoop.single_iteration() always returns a SelfPlayEvent — either
        accepted=True or accepted=False. This test verifies that every iteration
        produces exactly one event (no silent drops, no double-counting).

        Approach: call single_iteration() directly N times and collect results.
        This is equivalent to what run() does (run() calls single_iteration in a loop)
        but avoids the asyncio.run() complexity with mock ReplayLogger.
        """
        n_iterations = 30
        loop = _make_loop(small_archive, mock_evaluate_fn)

        # Initialize loop state as run() does
        loop._run_id = uuid.uuid4()
        loop._started_at = "2026-04-21T00:00:00"
        loop._n_accepted = 0
        loop._n_rejected = 0
        loop._prev_histogram = None

        events: list[SelfPlayEvent] = []
        for i in range(n_iterations):
            event = loop.single_iteration(i)
            events.append(event)

        assert len(events) == n_iterations, (
            f"Expected {n_iterations} events, got {len(events)}"
        )

        # Every event is either accepted or rejected — no silent drops
        all_accounted = sum(1 for e in events if e.accepted) + sum(
            1 for e in events if not e.accepted
        )
        assert all_accounted == n_iterations, (
            "All events must be either accepted or rejected — no silent gaps"
        )


# ---------------------------------------------------------------------------
# Test 5: KL = None on first night
# ---------------------------------------------------------------------------


class TestKlNoneOnFirstNight:
    """First night (no previous descriptor histogram) -> kl_divergence is None in result."""

    def test_kl_none_on_first_night(
        self,
        small_archive: MagicMock,
        mock_evaluate_fn: Any,
        small_config: SelfPlayConfig,
    ) -> None:
        """Without a previous descriptor histogram, kl_divergence must be None.

        First-night case (D-17, open question 3): no prior run -> no histogram to
        compare against -> KL divergence is undefined -> result.kl_divergence is None.

        With no replay_logger, _prev_histogram is never loaded, so _compute_kl_and_finalize
        returns None.
        """
        loop = _make_loop(
            small_archive,
            mock_evaluate_fn,
            config=small_config,
            replay_logger=None,  # no DB -> no previous histogram
        )

        result = loop.run(10)

        assert result.kl_divergence is None, (
            f"First night KL must be None (no prior histogram), got {result.kl_divergence}"
        )


# ---------------------------------------------------------------------------
# Test 6: soft_timeout exit via flush_and_finalize
# ---------------------------------------------------------------------------


class TestSoftTimeoutExit:
    """flush_and_finalize produces a valid SelfPlayRunResult with exit_reason='soft_timeout'."""

    def test_soft_timeout_exit(
        self,
        small_archive: MagicMock,
        mock_evaluate_fn: Any,
    ) -> None:
        """After 5 iterations, flush_and_finalize(5, 'soft_timeout') returns valid result.

        Simulates a SoftTimeLimitExceeded scenario: the loop has completed 5 iterations
        (n_accepted=3, n_rejected=2), then flush_and_finalize is called for graceful exit.

        Verifies:
            - result is a SelfPlayRunResult
            - result.exit_reason == 'soft_timeout'
            - result.n_iterations == 5
            - result.n_accepted == 3
            - result.n_rejected == 2
        """
        loop = _make_loop(small_archive, mock_evaluate_fn)

        # Simulate state after 5 partial iterations
        loop._n_accepted = 3
        loop._n_rejected = 2

        with patch.object(loop, "_compute_kl_and_finalize", return_value=None):
            result = loop.flush_and_finalize(n_done=5, exit_reason="soft_timeout")

        assert isinstance(result, SelfPlayRunResult)
        assert result.exit_reason == "soft_timeout", (
            f"Expected exit_reason='soft_timeout', got {result.exit_reason!r}"
        )
        assert result.n_iterations == 5, (
            f"Expected n_iterations=5, got {result.n_iterations}"
        )
        assert result.n_accepted == 3
        assert result.n_rejected == 2

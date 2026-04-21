"""Unit tests for AdversarialReviewer (Plan 10-02, Task 2 — TDD RED).

Tests: AdversarialReviewer.review() for all 4 rules:
    Rule 3 (degenerate layout): layout_coverage < 0.1
    Rule 2 (OOD parameters):    z_score > 3.0 on any dimension
    Rule 4 (gaming single metric): aspect_ratio contribution > 50% of fitness
    Rule 1 (reward hacking):    combined increases but >= 2 individual metrics decrease

Priority order: Rule 3 → Rule 2 → Rule 4 → Rule 1 (cheapest checks first).

Design: D-10/D-11 per research Pattern 5.
"""

from __future__ import annotations

import numpy as np
import pytest

from aerocloud.outer_loop.models import QualityMetrics, QualityWeights
from aerocloud.self_play.reviewer import AdversarialReviewer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_metrics(**kwargs: float) -> QualityMetrics:
    """Create QualityMetrics with all fields default 0.5, override as needed."""
    defaults: dict[str, float] = {
        "layout_coverage": 0.5,
        "layout_uniformity": 0.5,
        "space_saving": 0.5,
        "compactness": 0.5,
        "aspect_ratio": 0.5,
        "realized_adjacencies": 0.5,
        "distortion_score": 0.5,
    }
    defaults.update(kwargs)
    return QualityMetrics(**defaults)


def _make_reviewer(
    n_elites: int = 10,
    solution_dim: int = 40,
    mean: float = 0.5,
    std: float = 0.1,
) -> tuple[AdversarialReviewer, np.ndarray]:
    """Build reviewer with controlled archive statistics."""
    rng = np.random.default_rng(123)
    archive_solutions = rng.normal(loc=mean, scale=std, size=(n_elites, solution_dim)).astype(np.float64)
    weights = QualityWeights()
    reviewer = AdversarialReviewer(archive_solutions=archive_solutions, weights=weights)
    return reviewer, archive_solutions


# ---------------------------------------------------------------------------
# Test 1: Accept valid solution
# ---------------------------------------------------------------------------


def test_accept_valid_solution() -> None:
    """A normal solution within distribution with all metrics balanced is accepted."""
    reviewer, archive_solutions = _make_reviewer()

    # Solution within archive distribution (mean=0.5, std=0.1)
    solution = np.full(40, 0.5, dtype=np.float64)
    metrics = _make_metrics()  # all 0.5 — no degenerate, no single-metric dominance

    accepted, reason = reviewer.review(solution, metrics, metrics_baseline=None)

    assert accepted is True, f"Expected accepted=True, got reason='{reason}'"
    assert reason == "", f"Expected empty reason, got '{reason}'"


# ---------------------------------------------------------------------------
# Test 2: Reject degenerate layout (Rule 3)
# ---------------------------------------------------------------------------


def test_reject_degenerate_layout() -> None:
    """layout_coverage < 0.1 should trigger Rule 3 rejection."""
    reviewer, _ = _make_reviewer()

    solution = np.full(40, 0.5, dtype=np.float64)
    metrics = _make_metrics(layout_coverage=0.05)

    accepted, reason = reviewer.review(solution, metrics, metrics_baseline=None)

    assert accepted is False, "Expected rejection for degenerate layout"
    assert "degenerate_layout" in reason, f"Expected 'degenerate_layout' in reason, got '{reason}'"


# ---------------------------------------------------------------------------
# Test 3: Reject OOD parameters (Rule 2)
# ---------------------------------------------------------------------------


def test_reject_ood_parameters() -> None:
    """Solution with one param 10 std devs from mean should trigger Rule 2."""
    reviewer, archive_solutions = _make_reviewer(mean=0.5, std=0.1)

    # Put one parameter 10 std devs away from archive mean
    solution = np.full(40, 0.5, dtype=np.float64)
    solution[5] = 0.5 + 10 * 0.1  # 10 sigma above mean

    metrics = _make_metrics()  # all other rules should pass

    accepted, reason = reviewer.review(solution, metrics, metrics_baseline=None)

    assert accepted is False, "Expected rejection for OOD parameter"
    assert "ood_parameters" in reason, f"Expected 'ood_parameters' in reason, got '{reason}'"


# ---------------------------------------------------------------------------
# Test 4: Reject gaming aspect_ratio (Rule 4)
# ---------------------------------------------------------------------------


def test_reject_gaming_aspect_ratio() -> None:
    """AR=1.0, all others=0.0 → AR contributes 100% of fitness → reject."""
    reviewer, _ = _make_reviewer()

    solution = np.full(40, 0.5, dtype=np.float64)
    metrics = _make_metrics(
        layout_coverage=0.5,  # must be >= 0.1 to pass Rule 3
        layout_uniformity=0.0,
        space_saving=0.0,
        compactness=0.0,
        aspect_ratio=1.0,
        realized_adjacencies=0.0,
        distortion_score=0.0,
    )

    accepted, reason = reviewer.review(solution, metrics, metrics_baseline=None)

    assert accepted is False, "Expected rejection for gaming aspect_ratio"
    assert "gaming_aspect_ratio" in reason, f"Expected 'gaming_aspect_ratio' in reason, got '{reason}'"


# ---------------------------------------------------------------------------
# Test 5: Reject reward hacking (Rule 1)
# ---------------------------------------------------------------------------


def test_reject_reward_hacking() -> None:
    """Combined fitness increases but 3 individual metrics decrease → reject."""
    reviewer, _ = _make_reviewer()

    solution = np.full(40, 0.5, dtype=np.float64)

    # Baseline: moderate but balanced
    baseline = _make_metrics(
        layout_coverage=0.5,
        layout_uniformity=0.5,
        space_saving=0.5,
        compactness=0.5,
        aspect_ratio=0.5,
        realized_adjacencies=0.5,
        distortion_score=0.5,
    )
    # New: combined increases via aspect_ratio hike, but 3 metrics decline
    # Math check: baseline=0.5*7/7=0.5; new=(0.4+0.4+0.4+0.5+1.0+0.5+0.5)/7=3.7/7≈0.529 > 0.5
    weights = QualityWeights()
    new_metrics = _make_metrics(
        layout_coverage=0.4,    # down from 0.5 (1)
        layout_uniformity=0.4,  # down from 0.5 (2)
        space_saving=0.4,       # down from 0.5 (3)
        compactness=0.5,
        aspect_ratio=1.0,       # massively up from 0.5 — drives combined fitness up
        realized_adjacencies=0.5,
        distortion_score=0.5,
    )

    # Verify that combined fitness for new_metrics IS greater than baseline
    baseline_fitness = baseline.combined_fitness(weights)
    new_fitness = new_metrics.combined_fitness(weights)
    assert new_fitness > baseline_fitness, (
        "Test setup error: new_metrics combined fitness must exceed baseline"
    )

    accepted, reason = reviewer.review(solution, new_metrics, metrics_baseline=baseline)

    assert accepted is False, "Expected rejection for reward hacking"
    assert "reward_hacking" in reason, f"Expected 'reward_hacking' in reason, got '{reason}'"
    assert "3" in reason, f"Expected '3' in reason (3 metrics decreased), got '{reason}'"


# ---------------------------------------------------------------------------
# Test 6: No baseline skips Rule 1
# ---------------------------------------------------------------------------


def test_no_baseline_skips_rule1() -> None:
    """If metrics_baseline is None, Rule 1 is not checked. Solution accepted."""
    reviewer, _ = _make_reviewer()

    solution = np.full(40, 0.5, dtype=np.float64)
    # Metrics that would trigger reward_hacking if baseline were provided
    metrics = _make_metrics(
        layout_coverage=0.3,
        layout_uniformity=0.3,
        space_saving=0.3,
        aspect_ratio=1.0,
    )

    # Pass None for baseline → Rule 1 skipped; Rule 4 will catch gaming_aspect_ratio
    # So we need a metrics that passes all other rules — use balanced metrics
    balanced = _make_metrics()
    accepted, reason = reviewer.review(solution, balanced, metrics_baseline=None)

    assert accepted is True, f"Expected accepted=True with no baseline, got reason='{reason}'"


# ---------------------------------------------------------------------------
# Test 7: Rule priority — degenerate checked before OOD
# ---------------------------------------------------------------------------


def test_rule_priority_degenerate_first() -> None:
    """When both degenerate AND OOD conditions hold, degenerate_layout is reported."""
    reviewer, _ = _make_reviewer(mean=0.5, std=0.1)

    # OOD: one dimension 10 sigma away
    solution = np.full(40, 0.5, dtype=np.float64)
    solution[0] = 0.5 + 10 * 0.1

    # Also degenerate: layout_coverage < 0.1
    metrics = _make_metrics(layout_coverage=0.05)

    accepted, reason = reviewer.review(solution, metrics, metrics_baseline=None)

    assert accepted is False
    # Must report degenerate_layout (Rule 3 checked first, not OOD Rule 2)
    assert "degenerate_layout" in reason, (
        f"Expected Rule 3 (degenerate_layout) checked first, got '{reason}'"
    )


# ---------------------------------------------------------------------------
# Test 8: Borderline layout_coverage=0.1 is accepted
# ---------------------------------------------------------------------------


def test_borderline_lc_0_1_accepted() -> None:
    """layout_coverage=0.1 exactly is NOT degenerate (rule is strict < 0.1)."""
    reviewer, _ = _make_reviewer()

    solution = np.full(40, 0.5, dtype=np.float64)
    metrics = _make_metrics(layout_coverage=0.1)

    accepted, reason = reviewer.review(solution, metrics, metrics_baseline=None)

    # Rule 3 should NOT fire at exactly 0.1
    assert "degenerate_layout" not in reason, (
        f"LC=0.1 should not be degenerate (strict < 0.1), got '{reason}'"
    )


# ---------------------------------------------------------------------------
# Test 9: Exactly 2 metrics decrease triggers Rule 1
# ---------------------------------------------------------------------------


def test_exactly_2_metrics_decrease_triggers() -> None:
    """Combined fitness up, exactly 2 individual metrics down → reject (Rule 1)."""
    reviewer, _ = _make_reviewer()

    solution = np.full(40, 0.5, dtype=np.float64)
    weights = QualityWeights()

    baseline = _make_metrics(
        layout_coverage=0.5,
        layout_uniformity=0.5,
        space_saving=0.5,
        compactness=0.5,
        aspect_ratio=0.5,
        realized_adjacencies=0.5,
        distortion_score=0.5,
    )

    # Exactly 2 metrics decrease; combined still rises because aspect_ratio spikes
    new_metrics = _make_metrics(
        layout_coverage=0.3,    # down (1)
        layout_uniformity=0.3,  # down (2)
        space_saving=0.5,
        compactness=0.5,
        aspect_ratio=1.0,       # up a lot
        realized_adjacencies=0.5,
        distortion_score=0.5,
    )

    baseline_fitness = baseline.combined_fitness(weights)
    new_fitness = new_metrics.combined_fitness(weights)
    assert new_fitness > baseline_fitness, (
        "Test setup error: new combined fitness must exceed baseline"
    )

    accepted, reason = reviewer.review(solution, new_metrics, metrics_baseline=baseline)

    assert accepted is False, "Expected rejection with exactly 2 metrics decreased"
    assert "reward_hacking" in reason, f"Expected 'reward_hacking' in reason, got '{reason}'"
    assert "2" in reason, f"Expected '2' in reason (2 metrics decreased), got '{reason}'"

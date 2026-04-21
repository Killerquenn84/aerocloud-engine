"""Determinism tests for CQD + BOP-Elites pipeline (Phase 11, OUTER2-05).

Plan: 11-04-PLAN.md Task 2
TDD RED phase: Tests verify bit-exact reproducibility with fixed seed=42.

BDD Scenarios (Given/When/Then):

DT1 — Two BOP runs with same seed produce identical CQD scores:
    Given two ArchiveWrapper instances (gaussian emitter, seed=42) with same evaluate_fn
    When 20 iterations are run on each
    Then CQD scores are bit-exact equal

DT2 — Two runs with same seed produce identical archive objective arrays:
    Given two ArchiveWrapper instances (gaussian emitter, seed=42) with same evaluate_fn
    When 20 iterations are run on each
    Then archive.data()['objective'] arrays are bit-exact equal (np.array_equal)

DT3 — Two compute_cqd() calls on same data produce identical theta_curve:
    Given the same objectives + measures arrays
    When compute_cqd() is called twice with seed=42
    Then theta_curve lists are bit-exact equal

DT4 — Two extract_pareto_front() calls on same data produce identical indices:
    Given the same objectives + measures + extra_fields arrays
    When extract_pareto_front() is called twice
    Then front.indices are identical (same non-dominated set)

Notes:
    - Uses gaussian emitter (not BOP) to avoid 7-8s/iteration GP overhead.
    - 20 iterations is sufficient to populate the archive for determinism verification.
    - Fixed seed=42 throughout: ArchiveWrapper(seed=42), rng seed=42, compute_cqd seed=42.
    - Bit-exact comparison: np.array_equal() for arrays, == for floats.
"""

from __future__ import annotations

import numpy as np
import pytest

from aerocloud.models.archive import BehaviorDescriptor
from aerocloud.outer_loop.archive import ArchiveWrapper
from aerocloud.outer_loop.cqd import compute_cqd, compute_cqd_from_archive
from aerocloud.outer_loop.models import (
    ArchiveConfig,
    QualityMetrics,
    QualityWeights,
)
from aerocloud.outer_loop.pareto import extract_pareto_front


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_WORDS = 10
_SOLUTION_DIM = _MAX_WORDS * 4  # 40
_BINS = 5
_N_ITERATIONS = 20


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config() -> ArchiveConfig:
    """Minimal gaussian ArchiveConfig for fast determinism tests."""
    return ArchiveConfig(
        solution_dim=_SOLUTION_DIM,
        bins_per_dim=_BINS,
        batch_size=4,
        max_words=_MAX_WORDS,
        emitter_type="gaussian",
        sigma=0.3,
    )


def _make_evaluate_fn(seed: int):
    """Return a deterministic evaluate_fn: same solution + same call order → same result.

    The fn ignores the actual solution values and uses only the RNG state,
    which is seeded identically for each run. This guarantees bit-exact
    identical outputs for the same sequence of calls.
    """
    rng = np.random.default_rng(seed)

    def _evaluate_fn(
        solution: np.ndarray,
    ) -> tuple[QualityMetrics, BehaviorDescriptor, np.ndarray]:
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
        bd_vals = rng.uniform(0.0, 1.0, size=4)
        bd = BehaviorDescriptor(
            shape_fidelity=float(bd_vals[0]),
            rotation_ratio=float(bd_vals[1]),
            symmetry=float(bd_vals[2]),
            semantic_clustering=float(bd_vals[3]),
        )
        return metrics, bd, np.zeros(384)

    return _evaluate_fn


def _run_archive(evaluate_fn, n_iterations: int, seed: int = 42) -> ArchiveWrapper:
    """Build and populate an ArchiveWrapper with n_iterations of evaluations."""
    config = _make_config()
    archive = ArchiveWrapper(config=config, seed=seed)
    weights = QualityWeights()

    for _ in range(n_iterations):
        solutions = archive.ask()
        objectives_list: list[float] = []
        measures_list: list[list[float]] = []
        lc_list: list[float] = []
        ss_list: list[float] = []
        for sol in solutions:
            metrics, bd, _ = evaluate_fn(sol)
            objectives_list.append(float(metrics.combined_fitness(weights)))
            measures_list.append([
                bd.shape_fidelity,
                bd.rotation_ratio,
                bd.symmetry,
                bd.semantic_clustering,
            ])
            lc_list.append(float(metrics.layout_coverage))
            ss_list.append(float(metrics.space_saving))
        archive.tell(
            objectives=np.array(objectives_list),
            measures=np.array(measures_list),
            layout_coverage=np.array(lc_list),
            space_saving=np.array(ss_list),
        )

    return archive


# ---------------------------------------------------------------------------
# DT1: Two identical runs → identical CQD scores
# ---------------------------------------------------------------------------


class TestCQDDeterminism:
    """DT1: Two runs with seed=42 produce bit-exact identical CQD scores."""

    def test_cqd_scores_identical_across_two_runs(self) -> None:
        """DT1: CQD score is bit-exact equal for two identical seeded runs."""
        # Run 1
        archive1 = _run_archive(_make_evaluate_fn(seed=42), _N_ITERATIONS, seed=42)
        result1 = compute_cqd_from_archive(archive1, n_samples=1000, seed=42)

        # Run 2 (identical seed and evaluate_fn sequence)
        archive2 = _run_archive(_make_evaluate_fn(seed=42), _N_ITERATIONS, seed=42)
        result2 = compute_cqd_from_archive(archive2, n_samples=1000, seed=42)

        assert result1.cqd == result2.cqd, (
            f"CQD scores not bit-exact equal: {result1.cqd} != {result2.cqd}"
        )


# ---------------------------------------------------------------------------
# DT2: Two identical runs → identical archive objective arrays
# ---------------------------------------------------------------------------


class TestArchiveDeterminism:
    """DT2: Two runs with seed=42 produce bit-exact identical archive data."""

    def test_archive_objectives_identical_across_two_runs(self) -> None:
        """DT2: archive.data()['objective'] arrays are bit-exact equal for two seeded runs."""
        archive1 = _run_archive(_make_evaluate_fn(seed=42), _N_ITERATIONS, seed=42)
        archive2 = _run_archive(_make_evaluate_fn(seed=42), _N_ITERATIONS, seed=42)

        obj1 = np.asarray(archive1.data()["objective"], dtype=np.float64)
        obj2 = np.asarray(archive2.data()["objective"], dtype=np.float64)

        assert obj1.shape == obj2.shape, (
            f"Archive objective arrays have different shapes: {obj1.shape} vs {obj2.shape}"
        )
        assert np.array_equal(obj1, obj2), (
            f"Archive objective arrays are not bit-exact equal:\n"
            f"  max diff = {np.max(np.abs(obj1 - obj2)):.2e}"
        )


# ---------------------------------------------------------------------------
# DT3: compute_cqd() on same data → identical theta_curve
# ---------------------------------------------------------------------------


class TestCQDComputeDeterminism:
    """DT3: Two compute_cqd() calls on same arrays → bit-exact identical theta_curve."""

    def test_theta_curve_identical_for_same_inputs(self) -> None:
        """DT3: compute_cqd() with seed=42 produces bit-exact theta_curve on repeated calls."""
        # Build fixed numpy arrays (not from archive — pure array determinism)
        rng = np.random.default_rng(42)
        n_elites = 30
        objectives = rng.uniform(0.1, 0.9, size=n_elites)
        measures = rng.uniform(0.0, 1.0, size=(n_elites, 4))

        result1 = compute_cqd(objectives, measures, n_samples=500, seed=42)
        result2 = compute_cqd(objectives, measures, n_samples=500, seed=42)

        assert result1.theta_curve == result2.theta_curve, (
            "theta_curve not bit-exact equal across two compute_cqd() calls "
            f"with same inputs and seed=42"
        )

    def test_cqd_scalar_identical_for_same_inputs(self) -> None:
        """DT3b: compute_cqd().cqd scalar is bit-exact equal on repeated calls."""
        rng = np.random.default_rng(99)
        n_elites = 20
        objectives = rng.uniform(0.1, 0.9, size=n_elites)
        measures = rng.uniform(0.0, 1.0, size=(n_elites, 4))

        result1 = compute_cqd(objectives, measures, n_samples=500, seed=42)
        result2 = compute_cqd(objectives, measures, n_samples=500, seed=42)

        assert result1.cqd == result2.cqd, (
            f"CQD scalar not bit-exact equal: {result1.cqd} != {result2.cqd}"
        )


# ---------------------------------------------------------------------------
# DT4: Two extract_pareto_front() calls on same data → identical indices
# ---------------------------------------------------------------------------


class TestParetoDeterminism:
    """DT4: Two extract_pareto_front() calls on same data → identical Pareto indices."""

    def test_pareto_indices_identical_for_same_inputs(self) -> None:
        """DT4: extract_pareto_front() is deterministic: same data → same indices."""
        rng = np.random.default_rng(42)
        n_elites = 25
        objectives = rng.uniform(0.1, 0.9, size=n_elites)
        measures = rng.uniform(0.0, 1.0, size=(n_elites, 4))
        layout_coverage = rng.uniform(0.0, 1.0, size=n_elites)
        space_saving = rng.uniform(0.0, 1.0, size=n_elites)

        front1 = extract_pareto_front(objectives, measures, layout_coverage, space_saving)
        front2 = extract_pareto_front(objectives, measures, layout_coverage, space_saving)

        assert sorted(front1.indices) == sorted(front2.indices), (
            f"Pareto indices not identical across two calls:\n"
            f"  call 1: {sorted(front1.indices)}\n"
            f"  call 2: {sorted(front2.indices)}"
        )

    def test_pareto_objectives_identical_for_same_inputs(self) -> None:
        """DT4b: extract_pareto_front() design_fidelity and packing_density are identical."""
        rng = np.random.default_rng(77)
        n_elites = 20
        objectives = rng.uniform(0.1, 0.9, size=n_elites)
        measures = rng.uniform(0.0, 1.0, size=(n_elites, 4))
        layout_coverage = rng.uniform(0.0, 1.0, size=n_elites)
        space_saving = rng.uniform(0.0, 1.0, size=n_elites)

        front1 = extract_pareto_front(objectives, measures, layout_coverage, space_saving)
        front2 = extract_pareto_front(objectives, measures, layout_coverage, space_saving)

        assert front1.design_fidelity == front2.design_fidelity, (
            "design_fidelity lists not identical"
        )
        assert front1.packing_density == front2.packing_density, (
            "packing_density lists not identical"
        )

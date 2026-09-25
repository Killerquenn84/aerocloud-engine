"""Integration tests for the full Phase 11 BOP-Elites + CQD + Pareto pipeline.

Plan: 11-04-PLAN.md Task 1
TDD RED phase: Tests written before implementation.

Performance note:
    BayesianOptimizationEmitter with sklearn GP takes ~7-8s per iteration
    (GP matrix inversion O(n^3) in solution_dim). Populating 50 iterations
    would take ~400s, making tests unusable. Solution: use GaussianEmitter
    for archive population (fast), and test BOP wiring separately with only
    the initial Sobol batch (5 samples, takes ~0.6s). All pipeline assertions
    (CQD, Pareto, Slider, HV) remain valid regardless of emitter type — they
    operate only on archive.data().

BDD Scenarios (Given/When/Then):

SC1 — Archive fills after 50 iterations:
    Given an ArchiveWrapper (gaussian emitter) with bins_per_dim=5, batch_size=4
    When 50 single_iteration() calls are made with a random evaluate_fn
    Then archive.num_elites > 0 AND archive.coverage > 0.0

SC2 — CQD from archive after 50 iterations:
    Given the archive populated via SC1
    When compute_cqd_from_archive() is called
    Then result.cqd > 0.0 AND len(result.theta_curve) == 51

SC3 — Pareto front from archive after 50 iterations:
    Given the archive populated via SC1
    When extract_pareto_front_from_archive() is called
    Then len(front.indices) >= 1

SC4 — Pareto-Slider at 5 positions (OUTER2-08 / D-14):
    Given the Pareto front from SC3
    When pareto_slider() is called at positions [0.0, 0.25, 0.5, 0.75, 1.0]
    Then each call returns a dict with 'solution', 'objective', 'measures' keys

SC5 — CQD_HV monotonically non-decreasing:
    Given two sequential groups of 10 iterations (first low, then high objectives)
    When HV is measured after each group
    Then HV_after >= HV_before

SC6 — compute_cqd_hv returns float >= 0:
    Given the archive populated via SC1
    When compute_cqd_hv() is called on archive.data()
    Then result >= 0.0

SC7 — OuterLoop wiring test with BOP ArchiveWrapper:
    Given an OuterLoop constructed with BOP ArchiveWrapper
    When single_iteration() is called once (Sobol initial batch)
    Then no exception is raised AND total_evaluations > 0
"""

from __future__ import annotations

import numpy as np
import pytest

from aerocloud.models.archive import BehaviorDescriptor
from aerocloud.outer_loop.archive import ArchiveWrapper
from aerocloud.outer_loop.cqd import compute_cqd_from_archive
from unittest.mock import MagicMock

from aerocloud.outer_loop.emitter import SaturationMonitor
from aerocloud.outer_loop.models import (
    ArchiveConfig,
    QualityMetrics,
    QualityWeights,
)
from aerocloud.outer_loop.pareto import (
    compute_cqd_hv,
    extract_pareto_front_from_archive,
    pareto_slider,
)
from aerocloud.outer_loop.scheduler import OuterLoop


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Gaussian emitter config: fast, no GP overhead. max_words=10 satisfies ge=10.
_MAX_WORDS = 10
_SOLUTION_DIM = _MAX_WORDS * 4  # 40
_BINS = 5

# BOP config: solution_dim=40, initial Sobol batch only (5 samples, ~0.6s)
_BOP_NUM_INITIAL = 5
_BOP_HISTORY_CAP = 50


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def gaussian_config() -> ArchiveConfig:
    """Fast ArchiveConfig using GaussianEmitter (no GP overhead)."""
    return ArchiveConfig(
        solution_dim=_SOLUTION_DIM,
        bins_per_dim=_BINS,
        batch_size=4,
        max_words=_MAX_WORDS,
        emitter_type="gaussian",
        sigma=0.3,
    )


@pytest.fixture
def bop_config() -> ArchiveConfig:
    """BOP ArchiveConfig for wiring test (SC7 only — single Sobol batch)."""
    return ArchiveConfig(
        solution_dim=_SOLUTION_DIM,
        bins_per_dim=_BINS,
        batch_size=1,  # BayesianOptimizationEmitter requires batch_size=1
        max_words=_MAX_WORDS,
        emitter_type="bop",
        lower_bounds=np.zeros(_SOLUTION_DIM),
        upper_bounds=np.ones(_SOLUTION_DIM),
        num_initial_samples=_BOP_NUM_INITIAL,
        history_cap=_BOP_HISTORY_CAP,
    )


@pytest.fixture
def rng_evaluate_fn():
    """Mock evaluate_fn returning random QualityMetrics + BehaviorDescriptor (seed=42)."""
    rng = np.random.default_rng(42)

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


def _run_archive_iterations(
    archive: ArchiveWrapper,
    evaluate_fn,
    n_iterations: int,
) -> None:
    """Helper: run n_iterations of ask/evaluate/tell on an ArchiveWrapper."""
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


@pytest.fixture
def populated_archive(
    gaussian_config: ArchiveConfig, rng_evaluate_fn
) -> ArchiveWrapper:
    """ArchiveWrapper populated with 50 iterations of random evaluations (gaussian emitter)."""
    archive = ArchiveWrapper(config=gaussian_config, seed=42)
    _run_archive_iterations(archive, rng_evaluate_fn, n_iterations=50)
    return archive


# ---------------------------------------------------------------------------
# SC1: Archive fills after 50 iterations
# ---------------------------------------------------------------------------


class TestArchiveFills:
    """SC1: archive.num_elites > 0 and coverage > 0.0 after 50 iterations."""

    def test_archive_has_elites_after_50_iterations(
        self, populated_archive: ArchiveWrapper
    ) -> None:
        """SC1a: archive.num_elites > 0 after 50 iterations."""
        assert populated_archive.num_elites > 0, (
            f"Expected >0 elites, got {populated_archive.num_elites}"
        )

    def test_archive_coverage_nonzero_after_50_iterations(
        self, populated_archive: ArchiveWrapper
    ) -> None:
        """SC1b: archive.coverage > 0.0 after 50 iterations."""
        assert populated_archive.coverage > 0.0, (
            f"Expected >0 coverage, got {populated_archive.coverage}"
        )


# ---------------------------------------------------------------------------
# SC2: CQD from archive after 50 iterations
# ---------------------------------------------------------------------------


class TestCQDFromArchive:
    """SC2: CQD > 0.0 and theta_curve has 51 elements."""

    def test_cqd_positive(self, populated_archive: ArchiveWrapper) -> None:
        """SC2a: CQDResult.cqd > 0.0 after 50 iterations."""
        result = compute_cqd_from_archive(populated_archive, n_samples=1000, seed=42)
        assert result.cqd > 0.0, f"Expected cqd > 0.0, got {result.cqd}"

    def test_cqd_theta_curve_length(self, populated_archive: ArchiveWrapper) -> None:
        """SC2b: len(theta_curve) == 51."""
        result = compute_cqd_from_archive(populated_archive, n_samples=1000, seed=42)
        assert len(result.theta_curve) == 51


# ---------------------------------------------------------------------------
# SC3: Pareto front from archive after 50 iterations
# ---------------------------------------------------------------------------


class TestParetoFrontFromArchive:
    """SC3: extract_pareto_front_from_archive returns >= 1 non-dominated point."""

    def test_pareto_front_has_elites(self, populated_archive: ArchiveWrapper) -> None:
        """SC3: len(front.indices) >= 1 after 50 iterations."""
        front = extract_pareto_front_from_archive(populated_archive)
        assert len(front.indices) >= 1, (
            f"Expected >=1 Pareto points, got {len(front.indices)}"
        )


# ---------------------------------------------------------------------------
# SC4: Pareto-Slider at 5 positions (OUTER2-08 / D-14)
# ---------------------------------------------------------------------------


class TestParetoSlider:
    """SC4: pareto_slider at 5 positions each returns valid dict."""

    @pytest.mark.parametrize("position", [0.0, 0.25, 0.5, 0.75, 1.0])
    def test_slider_returns_valid_dict(
        self, populated_archive: ArchiveWrapper, position: float
    ) -> None:
        """SC4: pareto_slider at each position returns dict with required keys."""
        front = extract_pareto_front_from_archive(populated_archive)
        data = populated_archive.data()
        result = pareto_slider(front, position, data)
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert "solution" in result, f"Missing 'solution' at position={position}"
        assert "objective" in result, f"Missing 'objective' at position={position}"
        assert "measures" in result, f"Missing 'measures' at position={position}"


# ---------------------------------------------------------------------------
# SC5: HV monotonically non-decreasing
# ---------------------------------------------------------------------------


class TestHypervolumeMono:
    """SC5: HV after adding better elites >= HV before."""

    def test_hv_nondecreasing(self, gaussian_config: ArchiveConfig) -> None:
        """SC5: HV is monotonically non-decreasing when better elites are added.

        Strategy:
            - First 10 iterations: low objectives [0.1, 0.3] via rng_low
            - Next 10 iterations: high objectives [0.7, 0.9] via rng_high
            - MAP-Elites replaces elites only when objective improves
            - HV_after >= HV_before (SC5 contract)
        """
        archive = ArchiveWrapper(config=gaussian_config, seed=42)
        weights = QualityWeights()
        rng_low = np.random.default_rng(100)
        rng_high = np.random.default_rng(200)

        def low_fn(solution: np.ndarray) -> tuple[QualityMetrics, BehaviorDescriptor, np.ndarray]:
            vals = rng_low.uniform(0.1, 0.3, size=7)
            metrics = QualityMetrics(
                layout_coverage=float(vals[0]),
                layout_uniformity=float(vals[1]),
                space_saving=float(vals[2]),
                compactness=float(vals[3]),
                aspect_ratio=float(vals[4]),
                realized_adjacencies=float(vals[5]),
                distortion_score=float(vals[6]),
            )
            bd_vals = rng_low.uniform(0.0, 1.0, size=4)
            bd = BehaviorDescriptor(
                shape_fidelity=float(bd_vals[0]),
                rotation_ratio=float(bd_vals[1]),
                symmetry=float(bd_vals[2]),
                semantic_clustering=float(bd_vals[3]),
            )
            return metrics, bd, np.zeros(384)

        def high_fn(solution: np.ndarray) -> tuple[QualityMetrics, BehaviorDescriptor, np.ndarray]:
            vals = rng_high.uniform(0.7, 0.9, size=7)
            metrics = QualityMetrics(
                layout_coverage=float(vals[0]),
                layout_uniformity=float(vals[1]),
                space_saving=float(vals[2]),
                compactness=float(vals[3]),
                aspect_ratio=float(vals[4]),
                realized_adjacencies=float(vals[5]),
                distortion_score=float(vals[6]),
            )
            bd_vals = rng_high.uniform(0.0, 1.0, size=4)
            bd = BehaviorDescriptor(
                shape_fidelity=float(bd_vals[0]),
                rotation_ratio=float(bd_vals[1]),
                symmetry=float(bd_vals[2]),
                semantic_clustering=float(bd_vals[3]),
            )
            return metrics, bd, np.zeros(384)

        # First 10 iterations: low objectives
        _run_archive_iterations(archive, low_fn, n_iterations=10)
        data_before = archive.data()
        obj_b = np.asarray(data_before["objective"], dtype=np.float64)
        meas_b = np.asarray(data_before["measures"], dtype=np.float64)
        lc_b = np.asarray(data_before["layout_coverage"], dtype=np.float64)
        ss_b = np.asarray(data_before["space_saving"], dtype=np.float64)
        hv_before = compute_cqd_hv(
            obj_b, meas_b, lc_b, ss_b, gaussian_config.bins_per_dim
        )

        # Next 10 iterations: high objectives (replaces low elites)
        _run_archive_iterations(archive, high_fn, n_iterations=10)
        data_after = archive.data()
        obj_a = np.asarray(data_after["objective"], dtype=np.float64)
        meas_a = np.asarray(data_after["measures"], dtype=np.float64)
        lc_a = np.asarray(data_after["layout_coverage"], dtype=np.float64)
        ss_a = np.asarray(data_after["space_saving"], dtype=np.float64)
        hv_after = compute_cqd_hv(
            obj_a, meas_a, lc_a, ss_a, gaussian_config.bins_per_dim
        )

        assert hv_after >= hv_before, (
            f"HV not monotonically non-decreasing: "
            f"before={hv_before:.4f}, after={hv_after:.4f}"
        )


# ---------------------------------------------------------------------------
# SC6: compute_cqd_hv returns float >= 0
# ---------------------------------------------------------------------------


class TestCQDHVFromArchive:
    """SC6: compute_cqd_hv returns float >= 0.0."""

    def test_cqd_hv_nonnegative(self, populated_archive: ArchiveWrapper) -> None:
        """SC6: compute_cqd_hv on archive data returns a float >= 0.0."""
        data = populated_archive.data()
        objectives = np.asarray(data["objective"], dtype=np.float64)
        measures = np.asarray(data["measures"], dtype=np.float64)
        layout_coverage = np.asarray(data["layout_coverage"], dtype=np.float64)
        space_saving = np.asarray(data["space_saving"], dtype=np.float64)

        hv = compute_cqd_hv(
            objectives, measures, layout_coverage, space_saving, bins_per_dim=_BINS
        )
        assert isinstance(hv, float)
        assert hv >= 0.0


# ---------------------------------------------------------------------------
# SC7: OuterLoop wiring test with BOP ArchiveWrapper
# ---------------------------------------------------------------------------


class TestOuterLoopBOPWiring:
    """SC7: OuterLoop with BOP ArchiveWrapper runs single_iteration() without error.

    Uses only the initial Sobol batch (5 samples, ~0.6s) to avoid GP overhead.
    """

    def test_single_iteration_with_bop_archive(
        self, bop_config: ArchiveConfig, rng_evaluate_fn
    ) -> None:
        """SC7: OuterLoop.single_iteration() with BOP archive completes without error."""
        archive = ArchiveWrapper(config=bop_config, seed=42)
        weights = QualityWeights()
        novelty_emitter = MagicMock()
        saturation_monitor = SaturationMonitor(window=5)

        outer_loop = OuterLoop(
            archive=archive,
            evaluate_fn=rng_evaluate_fn,
            persistence=None,
            novelty_emitter=novelty_emitter,
            saturation_monitor=saturation_monitor,
            quality_weights=weights,
        )

        batch_size = outer_loop.single_iteration()
        assert batch_size >= 1, f"Expected batch_size >= 1, got {batch_size}"
        assert outer_loop._total_evaluations > 0

    def test_bop_archive_fills_after_sobol_init(
        self, bop_config: ArchiveConfig
    ) -> None:
        """SC7b: BOP archive has elites after initial Sobol batch."""
        archive = ArchiveWrapper(config=bop_config, seed=42)
        weights = QualityWeights()
        rng = np.random.default_rng(42)

        # Run only the initial Sobol batch (first ask gives num_initial_samples solutions)
        solutions = archive.ask()
        n = len(solutions)
        objectives_list = []
        measures_list = []
        lc_list = []
        ss_list = []
        for sol in solutions:
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
            objectives_list.append(float(metrics.combined_fitness(weights)))
            measures_list.append([float(v) for v in bd_vals])
            lc_list.append(float(metrics.layout_coverage))
            ss_list.append(float(metrics.space_saving))
        archive.tell(
            objectives=np.array(objectives_list),
            measures=np.array(measures_list),
            layout_coverage=np.array(lc_list),
            space_saving=np.array(ss_list),
        )

        assert archive.num_elites > 0, (
            f"Expected BOP archive to have elites after Sobol batch, got 0"
        )
        assert archive.coverage > 0.0

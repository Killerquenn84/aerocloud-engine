"""Tests for quality metrics — 5 geometric + 2 semantic + aggregator.

TDD Red → Green for Task 1 (geometric) and Task 2 (semantic + aggregator).

References:
    - D-05: LC, LU, SS, Compactness, Aspect Ratio formulas
    - D-06: Realized Adjacencies, Distortion formulas
    - .planning/phases/09-outer-loop-v1/09-02-PLAN.md
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from aerocloud.outer_loop.metrics import (
    compute_all_metrics,
    compute_aspect_ratio,
    compute_compactness,
    compute_distortion,
    compute_lc,
    compute_lu,
    compute_realized_adjacencies,
    compute_ss,
)
from aerocloud.outer_loop.models import QualityMetrics, QualityWeights

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ones_mask(h: int = 8, w: int = 8) -> np.ndarray:
    """All-True binary mask."""
    return np.ones((h, w), dtype=bool)


def _zeros_mask(h: int = 8, w: int = 8) -> np.ndarray:
    """All-False binary mask."""
    return np.zeros((h, w), dtype=bool)


# ---------------------------------------------------------------------------
# Task 1: Geometric quality metrics — RED
# ---------------------------------------------------------------------------


class TestComputeLC:
    """layout_coverage = ink pixels inside silhouette / silhouette area."""

    def test_full_coverage_returns_one(self) -> None:
        """Test 1: All silhouette pixels have ink → LC = 1.0."""
        density = np.ones((8, 8), dtype=float)
        mask = _ones_mask()
        result = compute_lc(density, mask)
        assert math.isclose(result, 1.0, rel_tol=1e-6)

    def test_empty_layout_returns_zero(self) -> None:
        """Test 2: No ink anywhere → LC = 0.0."""
        density = np.zeros((8, 8), dtype=float)
        mask = _ones_mask()
        result = compute_lc(density, mask)
        assert math.isclose(result, 0.0, abs_tol=1e-9)

    def test_partial_coverage(self) -> None:
        """Half of silhouette pixels have ink → LC ≈ 0.5."""
        density = np.zeros((8, 8), dtype=float)
        density[:4, :] = 1.0  # top half has ink
        mask = _ones_mask()
        result = compute_lc(density, mask)
        assert math.isclose(result, 0.5, rel_tol=1e-6)

    def test_empty_mask_returns_zero(self) -> None:
        """Edge case: empty silhouette mask → 0.0 (no silhouette area)."""
        density = np.ones((8, 8), dtype=float)
        mask = _zeros_mask()
        result = compute_lc(density, mask)
        assert math.isclose(result, 0.0, abs_tol=1e-9)

    def test_nan_input_returns_zero(self) -> None:
        """Threat T-09-04: NaN in density → returns 0.0."""
        density = np.full((8, 8), float("nan"))
        mask = _ones_mask()
        result = compute_lc(density, mask)
        assert result == 0.0

    def test_result_in_range(self) -> None:
        """Test 10 partial: LC always in [0.0, 1.0]."""
        rng = np.random.default_rng(42)
        density = rng.uniform(0, 1, (16, 16))
        mask = rng.random((16, 16)) > 0.5
        result = compute_lc(density, mask)
        assert 0.0 <= result <= 1.0


class TestComputeLU:
    """layout_uniformity = 1 - std(local_densities) / range(local_densities)."""

    def test_uniform_density_returns_one(self) -> None:
        """Test 3: Uniform density grid → LU close to 1.0."""
        density = np.full((16, 16), 0.5, dtype=float)
        mask = _ones_mask(16, 16)
        result = compute_lu(density, mask, k=4)
        assert result >= 0.9

    def test_single_corner_density_low(self) -> None:
        """Test 4: Single-corner density → LU < uniform case.

        With k=4 and a 16x16 grid, corner density concentrates all ink in one
        quadrant. The resulting LU should be lower than the all-uniform case.
        The formula: LU = 1 - std(cells) / (max - min + eps).
        When only 1 of 16 cells has high density (0.25 mean, rest 0.0):
        std ≈ 0.06, span = 0.25, LU ≈ 0.76 — less than uniform (1.0).
        For a very extreme case (all ink in a single cell), LU drops further.
        """
        density = np.zeros((16, 16), dtype=float)
        density[:4, :4] = 1.0  # full top-left quadrant saturated, rest empty
        mask = _ones_mask(16, 16)
        uniform_density = np.full((16, 16), 0.5)
        lu_corner = compute_lu(density, mask, k=4)
        lu_uniform = compute_lu(uniform_density, mask, k=4)
        # Corner case must have lower uniformity than uniform
        assert lu_corner < lu_uniform

    def test_result_in_range(self) -> None:
        """Test 10 partial: LU always in [0.0, 1.0]."""
        rng = np.random.default_rng(7)
        density = rng.uniform(0, 1, (16, 16))
        mask = rng.random((16, 16)) > 0.3
        result = compute_lu(density, mask)
        assert 0.0 <= result <= 1.0

    def test_nan_input_returns_zero(self) -> None:
        """Threat T-09-04: NaN in density → 0.0."""
        density = np.full((8, 8), float("nan"))
        mask = _ones_mask()
        result = compute_lu(density, mask)
        assert result == 0.0


class TestComputeSS:
    """space_saving = 1 - whitespace_inside / silhouette_area."""

    def test_no_whitespace_returns_one(self) -> None:
        """Test 5: All silhouette pixels have ink → SS = 1.0."""
        density = np.ones((8, 8), dtype=float)
        mask = _ones_mask()
        result = compute_ss(density, mask)
        assert math.isclose(result, 1.0, rel_tol=1e-6)

    def test_all_whitespace_returns_zero(self) -> None:
        """All silhouette pixels are empty → SS = 0.0."""
        density = np.zeros((8, 8), dtype=float)
        mask = _ones_mask()
        result = compute_ss(density, mask)
        assert math.isclose(result, 0.0, abs_tol=1e-9)

    def test_half_whitespace(self) -> None:
        """Half of silhouette has whitespace → SS = 0.5."""
        density = np.zeros((8, 8), dtype=float)
        density[:4, :] = 1.0
        mask = _ones_mask()
        result = compute_ss(density, mask)
        assert math.isclose(result, 0.5, rel_tol=1e-6)

    def test_result_in_range(self) -> None:
        """Test 10 partial: SS always in [0.0, 1.0]."""
        rng = np.random.default_rng(99)
        density = rng.uniform(0, 1, (16, 16))
        mask = rng.random((16, 16)) > 0.4
        result = compute_ss(density, mask)
        assert 0.0 <= result <= 1.0

    def test_nan_input_returns_zero(self) -> None:
        """Threat T-09-04: NaN density → 0.0."""
        density = np.full((8, 8), float("nan"))
        mask = _ones_mask()
        result = compute_ss(density, mask)
        assert result == 0.0

    def test_ss_distinct_from_lc(self) -> None:
        """LC and SS must be distinguishable: LC = ink coverage, SS = 1 - whitespace."""
        # Layout where 50% have ink (LC=0.5) but no silhouette area → SS=1.0 if no whitespace
        # Use density > 0 threshold at 0.1
        density = np.zeros((8, 8), dtype=float)
        density[:4, :] = 0.5  # low ink, but still > 0, so not whitespace
        mask = _ones_mask()
        lc = compute_lc(density, mask)
        ss = compute_ss(density, mask)
        # LC = ratio of pixels where density > 0 = 0.5
        # SS = 1 - (whitespace/total) = 1 - (32/64) = 0.5 (bottom half is zero, i.e., whitespace)
        assert math.isclose(lc, 0.5, rel_tol=1e-5)
        assert math.isclose(ss, 0.5, rel_tol=1e-5)
        # Now make a case where they differ
        density2 = np.zeros((8, 8), dtype=float)
        density2[0, 0] = 1.0  # single pixel has ink, rest is whitespace
        lc2 = compute_lc(density2, mask)
        ss2 = compute_ss(density2, mask)
        assert lc2 < 0.02  # only 1/64 pixels have ink
        assert ss2 < 0.02  # almost all is whitespace


class TestComputeCompactness:
    """Compactness = 4*pi * area / perimeter^2."""

    def test_circle_hull_returns_near_one(self) -> None:
        """Test 6: Circle-like arrangement → compactness close to 1.0."""
        # 32 points arranged in a circle
        theta = np.linspace(0, 2 * math.pi, 32, endpoint=False)
        radius = 10.0
        positions = np.column_stack([radius * np.sin(theta), radius * np.cos(theta)])
        sizes = np.ones((32, 2), dtype=float)  # tiny sizes
        result = compute_compactness(positions, sizes)
        # A perfect circle convex hull is close to 1.0 (isoperimetric quotient)
        assert result > 0.7

    def test_elongated_hull_below_half(self) -> None:
        """Test 7: Elongated arrangement → compactness < 0.5."""
        # Very elongated: points along a line
        positions = np.column_stack([np.linspace(0, 100, 20), np.zeros(20)])
        sizes = np.ones((20, 2), dtype=float)
        result = compute_compactness(positions, sizes)
        assert result < 0.5

    def test_degenerate_zero_size_two_points_returns_zero(self) -> None:
        """Threat T-09-03: 2 zero-size words → < 3 unique corners → 0.0."""
        positions = np.array([[0.0, 0.0], [1.0, 1.0]])
        sizes = np.zeros((2, 2), dtype=float)  # zero sizes → corners collapse to position
        result = compute_compactness(positions, sizes)
        assert math.isclose(result, 0.0, abs_tol=1e-9)

    def test_degenerate_one_point_returns_zero(self) -> None:
        """Threat T-09-03: single word with zero size → 0.0."""
        positions = np.array([[5.0, 5.0]])
        sizes = np.zeros((1, 2), dtype=float)
        result = compute_compactness(positions, sizes)
        assert math.isclose(result, 0.0, abs_tol=1e-9)

    def test_result_in_range(self) -> None:
        """Test 10 partial: compactness always in [0.0, 1.0]."""
        rng = np.random.default_rng(11)
        positions = rng.uniform(0, 100, (20, 2))
        sizes = rng.uniform(5, 15, (20, 2))
        result = compute_compactness(positions, sizes)
        assert 0.0 <= result <= 1.0


class TestComputeAspectRatio:
    """aspect_ratio = 1 - |actual_ratio - phi| / phi, phi = 1.618."""

    def test_golden_ratio_returns_one(self) -> None:
        """Test 8: golden ratio layout → AR = 1.0."""
        phi = 1.618
        result = compute_aspect_ratio(phi, 1.0)
        assert math.isclose(result, 1.0, rel_tol=1e-6)

    def test_square_returns_below_one(self) -> None:
        """Test 9: square → AR < 1.0 (ratio = 1.0, phi = 1.618)."""
        result = compute_aspect_ratio(1.0, 1.0)  # actual ratio = 1.0
        assert result < 1.0

    def test_result_in_range(self) -> None:
        """Test 10 partial: AR always in [0.0, 1.0]."""
        result = compute_aspect_ratio(5.0, 1.0)  # very elongated
        assert 0.0 <= result <= 1.0

    def test_exact_formula(self) -> None:
        """Verify formula: AR = clamp(1 - |actual - phi| / phi, 0, 1)."""
        phi = 1.618
        # actual ratio = 2.0 (landscape): score = 1 - |2.0 - 1.618| / 1.618
        expected = max(0.0, min(1.0, 1 - abs(2.0 - phi) / phi))
        result = compute_aspect_ratio(2.0, 1.0)
        assert math.isclose(result, expected, rel_tol=1e-5)


# ---------------------------------------------------------------------------
# Task 2: Semantic metrics — RED
# ---------------------------------------------------------------------------


class TestComputeRealizedAdjacencies:
    """realized_adjacencies = fraction of similar pairs that are adjacent."""

    def _make_positions(self, n: int) -> np.ndarray:
        """n words placed in a column, each 10px wide x 10px tall."""
        # positions (y, x) in (N, 2) shape
        return np.array([[i * 10.0, 0.0] for i in range(n)])

    def _make_sizes(self, n: int) -> np.ndarray:
        """All words 10x10."""
        return np.full((n, 2), 10.0)

    def test_all_similar_pairs_adjacent_returns_one(self) -> None:
        """Test 1: All similar pairs adjacent → RA = 1.0.

        Use 2 words touching each other. With positions (0,0) and (10,0),
        sizes 10x10: gap_y = 10 - (5+5) = 0, gap_x = 0 - (5+5) = -10 <= 0.
        Both dimensions satisfy gap <= 0 → adjacent.
        """
        positions = np.array([[0.0, 0.0], [10.0, 0.0]])  # 2 words, vertically touching
        sizes = np.full((2, 2), 10.0)
        sim = np.array([[1.0, 0.9], [0.9, 1.0]])  # both similar
        result = compute_realized_adjacencies(sim, positions, sizes, sim_threshold=0.7)
        assert math.isclose(result, 1.0, rel_tol=1e-6)

    def test_no_similar_pairs_adjacent_returns_zero(self) -> None:
        """Test 2: No similar pairs adjacent → RA = 0.0."""
        # Words far apart, all similar
        positions = np.array([[0.0, 0.0], [1000.0, 1000.0], [2000.0, 2000.0]])
        sizes = self._make_sizes(3)
        sim = np.full((3, 3), 0.9)
        np.fill_diagonal(sim, 1.0)
        result = compute_realized_adjacencies(sim, positions, sizes, sim_threshold=0.7)
        assert math.isclose(result, 0.0, abs_tol=1e-9)

    def test_no_semantically_similar_pairs_returns_zero(self) -> None:
        """Test 3: No similar pairs at all → 0.0 (edge case: no similar pairs exist)."""
        positions = self._make_positions(3)
        sizes = self._make_sizes(3)
        sim = np.eye(3)  # only self-similarity above threshold
        result = compute_realized_adjacencies(sim, positions, sizes, sim_threshold=0.7)
        assert math.isclose(result, 0.0, abs_tol=1e-9)

    def test_result_in_range(self) -> None:
        """RA always in [0.0, 1.0]."""
        rng = np.random.default_rng(5)
        n = 10
        positions = rng.uniform(0, 100, (n, 2))
        sizes = np.full((n, 2), 15.0)
        sim = rng.uniform(0, 1, (n, n))
        sim = (sim + sim.T) / 2
        np.fill_diagonal(sim, 1.0)
        result = compute_realized_adjacencies(sim, positions, sizes)
        assert 0.0 <= result <= 1.0


class TestComputeDistortion:
    """distortion_score measures spatial/embedding distance ratio (inverted)."""

    def test_proportional_positions_high_score(self) -> None:
        """Test 4: Positions proportional to embeddings → high distortion_score."""
        # embeddings in 2D for simplicity: A=(1,0), B=(0,1), C=(-1,0)
        embeddings = np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]])
        # positions proportional to embeddings scaled by 100
        positions_yx = embeddings[:, ::-1] * 100.0
        result = compute_distortion(positions_yx, embeddings)
        assert result > 0.5  # should be reasonably high

    def test_scrambled_positions_low_score(self) -> None:
        """Test 5: Scrambled positions → lower distortion_score than proportional.

        Perfect proportionality: spatial dist = constant * embedding dist for all pairs.
        Scrambling breaks this uniformity → higher CV → lower score.
        """
        embeddings = np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0], [0.0, -1.0]])
        # Perfect proportionality: position = scale * embedding (all ratios equal)
        proportional_pos = embeddings * 100.0
        # Scrambled: positions reordered (breaks the proportionality structure)
        scrambled_pos = proportional_pos[[2, 0, 3, 1]]
        score_prop = compute_distortion(proportional_pos, embeddings)
        score_scram = compute_distortion(scrambled_pos, embeddings)
        # Proportional positions should have higher (or equal) score than scrambled
        assert score_prop >= score_scram

    def test_single_word_returns_one(self) -> None:
        """< 2 words → 1.0 (no pairs to compute)."""
        positions = np.array([[0.0, 0.0]])
        embeddings = np.array([[1.0, 0.0, 0.0, 0.0]])
        result = compute_distortion(positions, embeddings)
        assert math.isclose(result, 1.0, rel_tol=1e-6)

    def test_result_in_range(self) -> None:
        """distortion_score always in [0.0, 1.0]."""
        rng = np.random.default_rng(77)
        positions = rng.uniform(0, 200, (15, 2))
        embeddings = rng.standard_normal((15, 8))
        result = compute_distortion(positions, embeddings)
        assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# Task 2: compute_all_metrics aggregator — RED
# ---------------------------------------------------------------------------


class TestComputeAllMetrics:
    """compute_all_metrics returns a fully populated QualityMetrics instance."""

    @pytest.fixture
    def sample_inputs(self) -> dict:
        """Small synthetic inputs for aggregator tests."""
        rng = np.random.default_rng(123)
        h, w = 16, 16
        density = rng.uniform(0, 1, (h, w))
        sdf_mask = np.ones((h, w), dtype=bool)
        n = 5
        positions_yx = rng.uniform(0, 100, (n, 2))
        sizes = np.full((n, 2), 12.0)
        embeddings = rng.standard_normal((n, 4))
        sim = rng.uniform(0, 1, (n, n))
        sim = (sim + sim.T) / 2
        np.fill_diagonal(sim, 1.0)
        return {
            "density": density,
            "sdf_mask": sdf_mask,
            "positions_yx": positions_yx,
            "sizes": sizes,
            "embeddings": embeddings,
            "cosine_sim_matrix": sim,
            "bbox_width": 100.0,
            "bbox_height": 62.0,
        }

    def test_returns_quality_metrics(self, sample_inputs: dict) -> None:
        """Test 6: compute_all_metrics returns QualityMetrics instance."""
        result = compute_all_metrics(**sample_inputs)
        assert isinstance(result, QualityMetrics)

    def test_all_7_fields_present(self, sample_inputs: dict) -> None:
        """All 7 fields are populated and in [0.0, 1.0]."""
        result = compute_all_metrics(**sample_inputs)
        assert 0.0 <= result.layout_coverage <= 1.0
        assert 0.0 <= result.layout_uniformity <= 1.0
        assert 0.0 <= result.space_saving <= 1.0
        assert 0.0 <= result.compactness <= 1.0
        assert 0.0 <= result.aspect_ratio <= 1.0
        assert 0.0 <= result.realized_adjacencies <= 1.0
        assert 0.0 <= result.distortion_score <= 1.0

    def test_combined_fitness_matches_manual(self, sample_inputs: dict) -> None:
        """Test 7: combined_fitness equals manual weighted sum."""
        result = compute_all_metrics(**sample_inputs)
        weights = QualityWeights()
        expected = (
            weights.w_lc * result.layout_coverage
            + weights.w_lu * result.layout_uniformity
            + weights.w_ss * result.space_saving
            + weights.w_compactness * result.compactness
            + weights.w_ar * result.aspect_ratio
            + weights.w_ra * result.realized_adjacencies
            + weights.w_distortion * result.distortion_score
        )
        actual = result.combined_fitness(weights)
        assert math.isclose(actual, expected, rel_tol=1e-9)

    def test_custom_weights(self, sample_inputs: dict) -> None:
        """Verify custom weights change the fitness value."""
        result = compute_all_metrics(**sample_inputs)
        default_fitness = result.combined_fitness(QualityWeights())
        custom_weights = QualityWeights(
            w_lc=10.0, w_lu=0.0, w_ss=0.0, w_compactness=0.0,
            w_ar=0.0, w_ra=0.0, w_distortion=0.0,
        )
        custom_fitness = result.combined_fitness(custom_weights)
        # custom_fitness = 10 * lc, default ≈ sum(1/7 * each)
        assert not math.isclose(default_fitness, custom_fitness, rel_tol=1e-6)

"""Tests for outer_loop.models — QualityWeights, QualityMetrics, ArchiveConfig, ReEvalResult.

TDD RED phase: all tests must fail before implementation exists.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aerocloud.outer_loop.models import (
    ArchiveConfig,
    QualityMetrics,
    QualityWeights,
    ReEvalResult,
)


# ---------------------------------------------------------------------------
# Test 1: QualityWeights — 7 float fields, all >= 0
# ---------------------------------------------------------------------------


class TestQualityWeights:
    def test_default_weights_have_seven_fields(self) -> None:
        """QualityWeights has exactly 7 weight fields, all float >= 0."""
        w = QualityWeights()
        fields = [
            w.w_lc,
            w.w_lu,
            w.w_ss,
            w.w_compactness,
            w.w_ar,
            w.w_ra,
            w.w_distortion,
        ]
        assert len(fields) == 7
        for val in fields:
            assert isinstance(val, float)
            assert val >= 0.0

    def test_custom_weights_accepted(self) -> None:
        """Non-default positive weights are accepted."""
        w = QualityWeights(
            w_lc=2.0, w_lu=1.5, w_ss=0.5,
            w_compactness=1.0, w_ar=1.0, w_ra=0.8, w_distortion=0.3,
        )
        assert w.w_lc == 2.0
        assert w.w_distortion == 0.3

    def test_negative_weight_rejected(self) -> None:
        """Negative weights must raise ValidationError."""
        with pytest.raises(ValidationError):
            QualityWeights(w_lc=-1.0)

    def test_frozen_immutable(self) -> None:
        """QualityWeights is frozen (immutable)."""
        w = QualityWeights()
        with pytest.raises(Exception):
            w.w_lc = 999.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Test 2: QualityMetrics — 7 metrics bounded [0.0, 1.0]
# ---------------------------------------------------------------------------


class TestQualityMetrics:
    def test_all_seven_metrics_bounded(self, sample_quality_metrics: QualityMetrics) -> None:
        """All 7 metric fields are in [0.0, 1.0]."""
        for field_name in [
            "layout_coverage", "layout_uniformity", "space_saving",
            "compactness", "aspect_ratio", "realized_adjacencies", "distortion_score",
        ]:
            val = getattr(sample_quality_metrics, field_name)
            assert 0.0 <= val <= 1.0, f"{field_name}={val} out of bounds"

    def test_out_of_range_rejected(self) -> None:
        """Values > 1.0 or < 0.0 must raise ValidationError."""
        with pytest.raises(ValidationError):
            QualityMetrics(
                layout_coverage=1.5,  # out of range
                layout_uniformity=0.5,
                space_saving=0.5,
                compactness=0.5,
                aspect_ratio=0.5,
                realized_adjacencies=0.5,
                distortion_score=0.5,
            )

    def test_combined_fitness_returns_float(
        self, sample_quality_metrics: QualityMetrics, quality_weights: QualityWeights
    ) -> None:
        """combined_fitness() returns a float."""
        fitness = sample_quality_metrics.combined_fitness(quality_weights)
        assert isinstance(fitness, float)

    def test_combined_fitness_weighted_sum(self) -> None:
        """combined_fitness() is the correct weighted sum."""
        metrics = QualityMetrics(
            layout_coverage=1.0,
            layout_uniformity=0.0,
            space_saving=0.0,
            compactness=0.0,
            aspect_ratio=0.0,
            realized_adjacencies=0.0,
            distortion_score=0.0,
        )
        weights = QualityWeights(
            w_lc=1.0, w_lu=0.0, w_ss=0.0,
            w_compactness=0.0, w_ar=0.0, w_ra=0.0, w_distortion=0.0,
        )
        # Only w_lc * layout_coverage = 1.0 * 1.0 = 1.0
        assert metrics.combined_fitness(weights) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Test 3: ArchiveConfig — bins_per_dim default=10, solution_dim required
# ---------------------------------------------------------------------------


class TestArchiveConfig:
    def test_default_bins_per_dim(self) -> None:
        """bins_per_dim defaults to 10."""
        cfg = ArchiveConfig(solution_dim=800)
        assert cfg.bins_per_dim == 10

    def test_solution_dim_required(self) -> None:
        """solution_dim is required — omitting it must raise ValidationError."""
        with pytest.raises(ValidationError):
            ArchiveConfig()  # type: ignore[call-arg]

    def test_custom_config(self) -> None:
        """Custom values are accepted."""
        cfg = ArchiveConfig(solution_dim=400, bins_per_dim=5, sigma=0.05, batch_size=8)
        assert cfg.solution_dim == 400
        assert cfg.bins_per_dim == 5
        assert cfg.sigma == 0.05
        assert cfg.batch_size == 8

    def test_archive_config_fixture(self, archive_config: ArchiveConfig) -> None:
        """The conftest fixture returns a valid ArchiveConfig."""
        assert archive_config.solution_dim == 800
        assert archive_config.bins_per_dim == 5


# ---------------------------------------------------------------------------
# Test 4: ReEvalResult — fitness_before, fitness_after, drifted bool
# ---------------------------------------------------------------------------


class TestReEvalResult:
    def test_fields_exist(self) -> None:
        """ReEvalResult has bin_id, fitness_before, fitness_after, drifted, drift_pct."""
        result = ReEvalResult(
            bin_id="abc123",
            fitness_before=0.7,
            fitness_after=0.5,
            drifted=True,
            drift_pct=28.57,
        )
        assert result.bin_id == "abc123"
        assert result.fitness_before == 0.7
        assert result.fitness_after == 0.5
        assert result.drifted is True
        assert result.drift_pct == pytest.approx(28.57)

    def test_frozen(self) -> None:
        """ReEvalResult is frozen."""
        result = ReEvalResult(
            bin_id="x", fitness_before=0.5, fitness_after=0.4, drifted=True, drift_pct=20.0
        )
        with pytest.raises(Exception):
            result.drifted = False  # type: ignore[misc]

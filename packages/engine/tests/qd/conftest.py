"""Shared fixtures for Quality-Diversity (outer loop) tests."""

from __future__ import annotations

import pytest

from aerocloud.outer_loop.models import ArchiveConfig, QualityMetrics, QualityWeights


@pytest.fixture
def archive_config() -> ArchiveConfig:
    """Fast ArchiveConfig for tests — small bins to keep archive tiny."""
    return ArchiveConfig(solution_dim=800, bins_per_dim=5)


@pytest.fixture
def quality_weights() -> QualityWeights:
    """Default QualityWeights instance."""
    return QualityWeights()


@pytest.fixture
def sample_quality_metrics() -> QualityMetrics:
    """Plausible quality metrics fixture."""
    return QualityMetrics(
        layout_coverage=0.72,
        layout_uniformity=0.68,
        space_saving=0.55,
        compactness=0.61,
        aspect_ratio=0.80,
        realized_adjacencies=0.45,
        distortion_score=0.30,
    )

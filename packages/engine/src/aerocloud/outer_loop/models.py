"""Pydantic models for the Outer Loop (MAP-Elites) subsystem.

Models follow the AeroCloudBase pattern: frozen, strict, extra="forbid".

References:
    - .planning/phases/09-outer-loop-v1/09-01-PLAN.md (Task 1)
    - .planning/phases/09-outer-loop-v1/09-03-PLAN.md (Task 2 — ArchiveFlushEntry)
    - .planning/phases/11-outer-loop-v2/11-01-PLAN.md (Task 1 — BOP fields)
    - D-07: Combined fitness = weighted sum (unnormalized, like LossWeights)
    - D-08: ArchiveFlushEntry carries BD scalars + params_blob + quality_metrics
    - OUTER-01, OUTER-02, OUTER-05, OUTER2-01, OUTER2-02
"""

from __future__ import annotations

from typing import Any, Literal

import numpy as np
from pydantic import ConfigDict, Field

from aerocloud.models.archive import BehaviorDescriptor
from aerocloud.models.base import AeroCloudBase

# ---------------------------------------------------------------------------
# Quality weights
# ---------------------------------------------------------------------------

_DEFAULT_WEIGHT = 1.0 / 7.0  # ~0.142857


class QualityWeights(AeroCloudBase):
    """Weighting coefficients for the 7-metric composite quality score.

    Weights are unnormalized floats >= 0, following the same pattern as
    LossWeights in the inner-loop models (D-07 decision).

    Fields map to the 7 QualityMetrics:
        w_lc         → layout_coverage
        w_lu         → layout_uniformity
        w_ss         → space_saving
        w_compactness → compactness
        w_ar         → aspect_ratio
        w_ra         → realized_adjacencies
        w_distortion → distortion_score
    """

    w_lc: float = Field(
        default=_DEFAULT_WEIGHT,
        ge=0.0,
        description="Weight for Layout Coverage (LC) metric",
    )
    w_lu: float = Field(
        default=_DEFAULT_WEIGHT,
        ge=0.0,
        description="Weight for Layout Uniformity (LU) metric",
    )
    w_ss: float = Field(
        default=_DEFAULT_WEIGHT,
        ge=0.0,
        description="Weight for Space Saving (SS) metric",
    )
    w_compactness: float = Field(
        default=_DEFAULT_WEIGHT,
        ge=0.0,
        description="Weight for Compactness metric",
    )
    w_ar: float = Field(
        default=_DEFAULT_WEIGHT,
        ge=0.0,
        description="Weight for Aspect Ratio (AR) metric",
    )
    w_ra: float = Field(
        default=_DEFAULT_WEIGHT,
        ge=0.0,
        description="Weight for Realized Adjacencies (RA) metric",
    )
    w_distortion: float = Field(
        default=_DEFAULT_WEIGHT,
        ge=0.0,
        description="Weight for Distortion score metric",
    )


# ---------------------------------------------------------------------------
# Quality metrics
# ---------------------------------------------------------------------------


class QualityMetrics(AeroCloudBase):
    """Seven quality metrics for a word cloud layout, all bounded [0.0, 1.0].

    - layout_coverage (LC): ratio of ink pixels inside silhouette to total
      silhouette area.
    - layout_uniformity (LU): 1 - normalized std dev of local density.
    - space_saving (SS): 1 - (whitespace inside silhouette / silhouette area).
    - compactness: 4*pi * area / perimeter^2 (isoperimetric quotient).
    - aspect_ratio: 1 - |actual_ratio - φ| / φ where φ = 1.618.
    - realized_adjacencies (RA): fraction of semantically-similar word pairs
      that are spatially adjacent.
    - distortion_score: inverted spatial/embedding distance ratio.
    """

    layout_coverage: float = Field(..., ge=0.0, le=1.0)
    layout_uniformity: float = Field(..., ge=0.0, le=1.0)
    space_saving: float = Field(..., ge=0.0, le=1.0)
    compactness: float = Field(..., ge=0.0, le=1.0)
    aspect_ratio: float = Field(..., ge=0.0, le=1.0)
    realized_adjacencies: float = Field(..., ge=0.0, le=1.0)
    distortion_score: float = Field(..., ge=0.0, le=1.0)

    def combined_fitness(self, weights: QualityWeights) -> float:
        """Compute the weighted sum of all 7 quality metrics.

        Args:
            weights: QualityWeights instance with per-metric coefficients.

        Returns:
            Weighted sum as a float (not normalized — may exceed 1.0 if
            weights are unnormalized).
        """
        return (
            weights.w_lc * self.layout_coverage
            + weights.w_lu * self.layout_uniformity
            + weights.w_ss * self.space_saving
            + weights.w_compactness * self.compactness
            + weights.w_ar * self.aspect_ratio
            + weights.w_ra * self.realized_adjacencies
            + weights.w_distortion * self.distortion_score
        )


# ---------------------------------------------------------------------------
# Archive configuration
# ---------------------------------------------------------------------------


class ArchiveConfig(AeroCloudBase):
    """Configuration for the MAP-Elites GridArchive + emitter.

    solution_dim is required because it depends on the word count at runtime.
    All other fields have sensible defaults.

    Phase 11 additions (11-01-PLAN.md, OUTER2-01, OUTER2-02):
        - lower_bounds / upper_bounds: required by BayesianOptimizationEmitter.
          Defaults to None (backwards compat) — ArchiveWrapper auto-fills with
          zeros/ones when emitter_type="bop".
        - num_initial_samples: Sobol random samples before GP takes over.
        - history_cap: Maximum GP training set size (T-11-02 DoS mitigation).
          Must be >= 10.
        - emitter_type: "gaussian" keeps Phase 9 behaviour; "bop" uses
          CappedBOPEmitter + BayesianOptimizationScheduler.
    """

    solution_dim: int = Field(
        ...,
        ge=4,
        description="Flattened parameter dimension: max_words * 4 (y, x, scale, rotation)",
    )
    bins_per_dim: int = Field(
        default=10,
        ge=2,
        le=100,
        description="Number of bins per behavioral dimension (default: 10 → 10^4 = 10,000 cells)",
    )
    sigma: float = Field(
        default=0.1,
        gt=0.0,
        description="GaussianEmitter perturbation standard deviation",
    )
    batch_size: int = Field(
        default=16,
        ge=1,
        description="Number of solutions per ask() call",
    )
    max_words: int = Field(
        default=200,
        ge=10,
        description="Maximum word count for fixed solution_dim allocation",
    )
    # --- Phase 11 BOP-Elites fields ---
    lower_bounds: np.ndarray | None = Field(
        default=None,
        description=(
            "Lower bounds for BayesianOptimizationEmitter solution space. "
            "None → ArchiveWrapper auto-fills np.zeros(solution_dim). "
            "Required when emitter_type='bop'."
        ),
    )
    upper_bounds: np.ndarray | None = Field(
        default=None,
        description=(
            "Upper bounds for BayesianOptimizationEmitter solution space. "
            "None → ArchiveWrapper auto-fills np.ones(solution_dim). "
            "Required when emitter_type='bop'."
        ),
    )
    num_initial_samples: int = Field(
        default=20,
        ge=1,
        description=(
            "Number of Sobol random samples before GP-driven acquisition starts "
            "(passed to BayesianOptimizationEmitter.num_initial_samples)."
        ),
    )
    history_cap: int = Field(
        default=200,
        ge=10,
        description=(
            "Maximum number of data points kept in the GP training set "
            "(T-11-02 DoS mitigation). ge=10 prevents trivial cap values."
        ),
    )
    emitter_type: Literal["gaussian", "bop"] = Field(
        default="gaussian",
        description=(
            "'gaussian' → GaussianEmitter + Scheduler (Phase 9 behaviour, backwards compat). "
            "'bop' → CappedBOPEmitter + BayesianOptimizationScheduler (Phase 11 BOP-Elites)."
        ),
    )

    model_config = ConfigDict(
        frozen=True,
        strict=False,
        extra="forbid",
        arbitrary_types_allowed=True,
    )


# ---------------------------------------------------------------------------
# Re-evaluation result
# ---------------------------------------------------------------------------


class ReEvalResult(AeroCloudBase):
    """Result of re-evaluating an existing elite from the archive (D-14).

    Captures before/after fitness comparison and drift detection.
    """

    bin_id: str = Field(..., description="Archive bin identifier for the re-evaluated elite")
    fitness_before: float = Field(..., description="Fitness value recorded at time of archiving")
    fitness_after: float = Field(..., description="Fitness value from re-evaluation run")
    drifted: bool = Field(
        ...,
        description="True if fitness dropped by more than the drift threshold (default 10%)",
    )
    drift_pct: float = Field(
        ...,
        description="Percentage change in fitness: 100 * (before - after) / before",
    )


# ---------------------------------------------------------------------------
# Archive flush entry (Plan 09-03, Task 2 — D-08, D-10)
# ---------------------------------------------------------------------------


class ArchiveFlushEntry(AeroCloudBase):
    """One archive entry to flush to PostgreSQL via archive_v1 upsert.

    Carries everything needed for the ON CONFLICT upsert (D-10):
        - bin_id: conflict key (UNIQUE NOT NULL)
        - descriptor_vec: 384-dim BERT embedding as float32 ndarray
        - fitness: scalar quality score (higher is better)
        - metadata: arbitrary JSON-serializable dict
        - behavior_descriptor: 4 BD scalars (stored in dedicated columns for D-09)
        - params_bytes: safetensors-serialized (N, 4) params tensor (NOT pickle)
        - quality_metrics_json: serialized QualityMetrics dict for audit trail

    Security (T-09-05): All fields are passed as parameterized SQL arguments.
    No string interpolation of user-derived data is performed in persistence.py.

    Security (T-09-06): params_bytes must be produced by params_to_bytes()
    (safetensors format). pickle is forbidden per CLAUDE.md constraint.
    """

    bin_id: str = Field(..., description="Unique archive bin identifier")
    descriptor_vec: Any = Field(
        ...,
        description="384-dim float32 numpy array — layout BERT embedding for pgvector column",
    )
    fitness: float = Field(..., description="Combined quality score (higher is better)")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary JSON-serializable metadata dict",
    )
    behavior_descriptor: BehaviorDescriptor = Field(
        ...,
        description="4D behavioral descriptor (stored in dedicated REAL columns for D-09)",
    )
    params_bytes: bytes = Field(
        ...,
        description="safetensors-serialized (N, 4) params tensor — NOT pickle",
    )
    quality_metrics_json: dict[str, Any] = Field(
        default_factory=dict,
        description="Serialized QualityMetrics dict for audit trail (JSONB column)",
    )

    model_config = ConfigDict(
        frozen=True,
        strict=False,
        extra="forbid",
        arbitrary_types_allowed=True,
    )

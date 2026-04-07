"""MAP-Elites archive models — Phase 9 Outer Loop types."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from aerocloud.models.base import AeroCloudBase


class BehaviorDescriptor(AeroCloudBase):
    """Behavioral descriptor vector for a layout (used as the MAP-Elites grid key).

    Dimensions are the behavioral axes from Blueprint Teil VIII:
    shape fidelity, rotation, symmetry, semantics.
    """

    shape_fidelity: float = Field(..., ge=0.0, le=1.0)
    rotation_ratio: float = Field(..., ge=0.0, le=1.0, description="Fraction of 90-rotated words")
    symmetry: float = Field(..., ge=0.0, le=1.0)
    semantic_clustering: float = Field(..., ge=0.0, le=1.0)


class MapElitesEntry(AeroCloudBase):
    """A single archive entry — one elite solution for a behavioral cell."""

    bin_id: str = Field(..., description="Hash of the descriptor bucket")
    descriptor: BehaviorDescriptor
    fitness: float = Field(..., description="Quality score (higher is better)")
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

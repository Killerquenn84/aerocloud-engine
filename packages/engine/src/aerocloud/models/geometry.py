"""Pydantic contracts at the geometry package boundary.

Rules:
- (y, x) ordering only (D-14, D-16).
- ``AABB`` uses ``y_min, x_min, y_max, x_max`` (NOT left/top/right/bottom).
- numpy arrays carried via ``arbitrary_types_allowed=True``.
- half-open intervals: ``[y_min, y_max) x [x_min, x_max)``.

References:
    - D-14: (y, x) canonical internally (ADR-0005)
    - D-16: AABB field names enforce numpy-native ordering
    - D-32: GlyphBBox carries pixel-scanned AABB + advance width + pixel_buffer
    - D-43: PlacementResult + DropReason enum for structured fail-fast contract
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

import numpy as np
from pydantic import ConfigDict, Field, field_validator, model_validator

from aerocloud.models.base import AeroCloudBase


class AABB(AeroCloudBase):
    """Axis-aligned bounding box in numpy-native (y, x) ordering, half-open.

    Fields are ordered (y_min, x_min, y_max, x_max) to match numpy row-major
    convention (D-14). NOT Pillow's (left, top, right, bottom). The half-open
    convention [y_min, y_max) x [x_min, x_max) means adjacent boxes do NOT
    overlap (D-35 AABB collision semantics).

    Raises:
        ValidationError: if y_min >= y_max, x_min >= x_max, or any extra field
            is passed (extra=forbid from AeroCloudBase).
    """

    y_min: int = Field(ge=0)
    x_min: int = Field(ge=0)
    y_max: int = Field(ge=0)
    x_max: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_half_open(self) -> AABB:
        if self.y_min >= self.y_max:
            raise ValueError(
                f"y_min ({self.y_min}) must be strictly less than y_max ({self.y_max})"
            )
        if self.x_min >= self.x_max:
            raise ValueError(
                f"x_min ({self.x_min}) must be strictly less than x_max ({self.x_max})"
            )
        return self


class GlyphBBox(AeroCloudBase):
    """Pixel-scanned AABB of a rasterized glyph (D-32).

    Carries:
    - ``bbox``: tight pixel-scanned AABB in (y, x) ordering (may be None for
      whitespace glyphs with no ink pixels).
    - ``advance_width``: glyph advance width in pixels (for downstream layout).
    - ``pixel_buffer``: L-mode (H, W) uint8 numpy array of the raw raster.
    - Identity: ``font_family``, ``size_pt``, ``codepoint``.

    ``pixel_buffer`` is allowed to be a numpy ndarray via
    ``arbitrary_types_allowed=True`` (Pydantic v2 ConfigDict override to add
    this while preserving the frozen/strict/extra=forbid from AeroCloudBase).
    """

    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    bbox: AABB | None
    advance_width: int = Field(ge=0)
    pixel_buffer: np.ndarray
    font_family: str = Field(min_length=1)
    size_pt: int = Field(gt=0, le=256)
    codepoint: int = Field(ge=0, le=0x10FFFF)

    @field_validator("pixel_buffer", mode="before")
    @classmethod
    def _check_buffer(cls, v: Any) -> np.ndarray:
        if not isinstance(v, np.ndarray):
            raise TypeError(
                f"pixel_buffer must be np.ndarray, got {type(v).__name__}"
            )
        if v.dtype != np.uint8:
            raise TypeError(
                f"pixel_buffer must be dtype=uint8, got {v.dtype}"
            )
        if v.ndim != 2:
            raise TypeError(
                f"pixel_buffer must be 2-D (H, W), got ndim={v.ndim}"
            )
        return v


class MaskInput(AeroCloudBase):
    """PNG bytes input at the geometry package boundary.

    Minimum length of 8 bytes enforces that at least the PNG signature header
    is present.
    """

    raw_png_bytes: bytes = Field(min_length=8)


class GlyphRasterRequest(AeroCloudBase):
    """Request to rasterize a single Unicode codepoint.

    Drives ``glyph.rasterize_glyph`` — all fields are validated before any
    font I/O occurs so callers get a clear error for bad inputs.
    """

    font_family: str = Field(min_length=1)
    codepoint: int = Field(ge=0, le=0x10FFFF)
    size_pt: int = Field(gt=0, le=256)


# ---------------------------------------------------------------------------
# Spiral placement models (D-43, Wave 3)
# ---------------------------------------------------------------------------


class DropReason(StrEnum):
    """Machine-readable reason why a word could not be placed (D-43).

    Used in ``DroppedWord.reason``. Phase 5 Inner Loop must consume these
    as structured values — never parse log messages.

    Values:
        NO_FEASIBLE_ANCHOR: All pixels in the feasibility field are <= 0;
            the word physically cannot fit anywhere in the remaining free
            space (word may be too large, or mask too full).
        ITERATION_BUDGET_EXCEEDED: The spiral search exhausted all seeds
            (max_seeds_per_word * max_iterations_per_seed) without finding
            a collision-free placement.
        TOO_LARGE_FOR_MASK: The word's AABB dimensions exceed the mask
            dimensions entirely — rejected before any search attempt.
        WALL_CLOCK_EXCEEDED: The per-word wall-clock budget (1.0 s) was
            exhausted before a placement was found.
    """

    NO_FEASIBLE_ANCHOR = "no_feasible_anchor"
    ITERATION_BUDGET_EXCEEDED = "iteration_budget_exceeded"
    TOO_LARGE_FOR_MASK = "too_large_for_mask"
    WALL_CLOCK_EXCEEDED = "wall_clock_exceeded"


class PlacedWord(AeroCloudBase):
    """A word that was successfully placed in the silhouette (D-43).

    ``y`` and ``x`` are the center pixel coordinates (row, column) in the
    (y, x) canonical system (D-14). ``bbox`` carries the full half-open AABB.
    """

    word: str
    y: int = Field(ge=0, description="Center row (y-axis) in (y, x) ordering")
    x: int = Field(ge=0, description="Center column (x-axis)")
    bbox: AABB
    size_pt: int = Field(gt=0, description="Font point size used for placement")


class DroppedWord(AeroCloudBase):
    """A word that could not be placed, with a machine-readable reason (D-43).

    ``details`` carries optional human-readable context (e.g. which budget
    was hit). It is NEVER required by Phase 5 — only ``reason`` is.
    """

    word: str
    reason: DropReason
    details: str | None = None


class PlacementStats(AeroCloudBase):
    """Aggregate statistics for a single ``place_words`` call (D-43).

    Used for budget tuning and observability. ``wall_clock_ms`` is the
    total elapsed time including feasibility-field computation for all words.
    """

    total_words: int = Field(ge=0)
    placed: int = Field(ge=0)
    dropped: int = Field(ge=0)
    total_iterations: int = Field(ge=0)
    wall_clock_ms: float = Field(ge=0.0)


class PlacementResult(AeroCloudBase):
    """Structured result of a full spiral placement pass (D-43).

    Phase 5 must consume ``placements`` + ``dropped_words`` as structured
    values. ``PlacementFailedError`` is raised ONLY for contract violations;
    ordinary unplaceable words appear in ``dropped_words``.
    """

    placements: list[PlacedWord]
    dropped_words: list[DroppedWord]
    stats: PlacementStats


class PlacementRequest(AeroCloudBase):
    """Input contract for ``place_words`` (D-43).

    ``words`` is a list of ``(text, aabb_h, aabb_w)`` tuples — glyph sizing
    (rasterization) happens upstream; this module only handles placement.
    ``seed`` drives ``set_seed`` for full determinism (D-45).
    """

    raw_png_bytes: bytes = Field(min_length=8)
    words: list[tuple[str, int, int]]  # (text, aabb_h, aabb_w)
    seed: int = 0

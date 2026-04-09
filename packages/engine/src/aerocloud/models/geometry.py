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
"""

from __future__ import annotations

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

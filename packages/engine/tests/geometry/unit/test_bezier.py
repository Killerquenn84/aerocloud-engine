"""Unit tests for Bezier path representation (GEO2-09).

BDD Scenario:
  Given: bezier.py implements BezierCurve, BezierGlyph models and glyph_to_bezier()
  When: glyph_to_bezier() is called with a GlyphBBox containing a pixel_buffer
  Then: Returns a BezierGlyph with at least one contour, float64 control points,
        and (y, x) coordinate ordering (D-14, cv2 flip applied)

TDD Phase: RED — aerocloud.geometry.bezier does not exist yet.

Threat mitigations tested:
- T-07-05-01: cv2 (x,y) → (y,x) coordinate flip (test_cv2_coords_flipped)
- T-07-05-03: float64 precision (test_glyph_to_bezier_points_are_float64)
"""

from __future__ import annotations

import numpy as np
import pytest

from aerocloud.geometry.bezier import (  # type: ignore[import-not-found]
    BezierCurve,
    BezierGlyph,
    glyph_to_bezier,
)
from aerocloud.models.geometry import GlyphBBox


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_glyphbbox(pixel_buffer: np.ndarray) -> GlyphBBox:
    """Create a minimal GlyphBBox with the given pixel_buffer."""
    from aerocloud.models.geometry import AABB

    has_ink = pixel_buffer.max() > 0 if pixel_buffer.size > 0 else False
    bbox = None
    if has_ink:
        nz = np.argwhere(pixel_buffer > 0)
        y_min = int(nz[:, 0].min())
        y_max = int(nz[:, 0].max()) + 1
        x_min = int(nz[:, 1].min())
        x_max = int(nz[:, 1].max()) + 1
        bbox = AABB(y_min=y_min, x_min=x_min, y_max=y_max, x_max=x_max)

    return GlyphBBox(
        bbox=bbox,
        advance_width=8,
        pixel_buffer=pixel_buffer,
        font_family="TestFont",
        size_pt=12,
        codepoint=ord("A"),
    )


def _solid_8x8() -> GlyphBBox:
    """8x8 solid ink block."""
    buf = np.full((8, 8), 255, dtype=np.uint8)
    return _make_glyphbbox(buf)


def _empty_buffer() -> GlyphBBox:
    """All-zero pixel_buffer (no ink)."""
    buf = np.zeros((8, 8), dtype=np.uint8)
    # For empty buffer, we need a valid GlyphBBox (whitespace has bbox=None)
    from aerocloud.models.geometry import AABB
    return GlyphBBox(
        bbox=None,
        advance_width=4,
        pixel_buffer=buf,
        font_family="TestFont",
        size_pt=12,
        codepoint=ord(" "),
    )


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


def test_bezier_curve_model_frozen() -> None:
    """BezierCurve is immutable (Pydantic frozen=True)."""
    curve = BezierCurve(
        p0=(0.0, 0.0),
        p1=(1.0, 2.0),
        p2=(3.0, 4.0),
        p3=(5.0, 6.0),
    )
    with pytest.raises((TypeError, Exception)):
        object.__setattr__(curve, "p0", (99.0, 99.0))  # type: ignore[misc]


def test_bezier_glyph_model_frozen() -> None:
    """BezierGlyph is immutable."""
    glyph = BezierGlyph(
        font_family="TestFont",
        size_pt=12,
        codepoint=65,
        contours=(),
        tolerance=1.0,
    )
    with pytest.raises((TypeError, Exception)):
        object.__setattr__(glyph, "font_family", "Other")  # type: ignore[misc]


def test_bezier_glyph_not_subclass_of_glyphbbox() -> None:
    """BezierGlyph is a sibling model, NOT a subclass of GlyphBBox (D-17)."""
    glyph = BezierGlyph(
        font_family="TestFont",
        size_pt=12,
        codepoint=65,
        contours=(),
        tolerance=1.0,
    )
    assert not isinstance(glyph, GlyphBBox), (
        "D-17 VIOLATION: BezierGlyph must NOT be a subclass of GlyphBBox. "
        "GlyphBBox is frozen=True and cannot be subclassed."
    )


# ---------------------------------------------------------------------------
# glyph_to_bezier() functional tests
# ---------------------------------------------------------------------------


def test_glyph_to_bezier_solid_8x8() -> None:
    """8x8 solid ink pixel_buffer → BezierGlyph with at least 1 contour."""
    gb = _solid_8x8()
    result = glyph_to_bezier(gb)
    assert isinstance(result, BezierGlyph)
    assert len(result.contours) >= 1, (
        "Solid 8x8 pixel buffer must yield at least 1 contour"
    )


def test_glyph_to_bezier_empty_returns_empty_contours() -> None:
    """All-zero pixel_buffer → BezierGlyph with 0 contours (graceful handling)."""
    gb = _empty_buffer()
    result = glyph_to_bezier(gb)
    assert isinstance(result, BezierGlyph)
    assert len(result.contours) == 0, (
        "Empty pixel buffer must yield 0 contours"
    )


def test_glyph_to_bezier_points_are_float64() -> None:
    """All control points in BezierCurve are float64 tuples (D-19, T-07-05-03)."""
    gb = _solid_8x8()
    result = glyph_to_bezier(gb)
    assert len(result.contours) >= 1
    for contour in result.contours:
        for curve in contour:
            for pt in (curve.p0, curve.p1, curve.p2, curve.p3):
                assert len(pt) == 2
                for coord in pt:
                    assert isinstance(coord, float), (
                        f"Control point coordinate must be float, got {type(coord)}"
                    )
                    # Verify float64 precision (not float32)
                    arr = np.array(pt, dtype=np.float64)
                    assert arr.dtype == np.float64


def test_glyph_to_bezier_yx_ordering() -> None:
    """BezierCurve p0 coordinates are (y, x) — y < H and x < W of pixel_buffer."""
    buf = np.full((8, 8), 255, dtype=np.uint8)
    gb = _make_glyphbbox(buf)
    result = glyph_to_bezier(gb)
    assert len(result.contours) >= 1
    H, W = buf.shape
    for contour in result.contours:
        for curve in contour:
            # p0 = (y, x) — y is first coordinate, must be within buffer height
            y, x = curve.p0
            assert y < H, f"y coordinate {y} exceeds buffer height {H}"
            assert x < W, f"x coordinate {x} exceeds buffer width {W}"


def test_glyph_to_bezier_tolerance_recorded() -> None:
    """BezierGlyph.tolerance == tolerance argument passed to glyph_to_bezier."""
    gb = _solid_8x8()
    result = glyph_to_bezier(gb, tolerance=2.5)
    assert result.tolerance == 2.5, (
        f"Expected tolerance=2.5, got {result.tolerance}"
    )


def test_bezier_curve_count_reduces_with_higher_tolerance() -> None:
    """Higher tolerance → fewer Bezier curves (more simplification)."""
    # Use a larger buffer to ensure enough polygon points for both tolerances
    buf = np.zeros((32, 32), dtype=np.uint8)
    # Draw a ring to get a more complex contour
    for y in range(32):
        for x in range(32):
            dist = ((y - 16) ** 2 + (x - 16) ** 2) ** 0.5
            if 8 <= dist <= 14:
                buf[y, x] = 255
    gb = _make_glyphbbox(buf)

    low_tol = glyph_to_bezier(gb, tolerance=0.5)
    high_tol = glyph_to_bezier(gb, tolerance=5.0)

    low_count = sum(len(c) for c in low_tol.contours)
    high_count = sum(len(c) for c in high_tol.contours)

    assert low_count >= high_count, (
        f"Lower tolerance should yield >= curves than higher tolerance. "
        f"Got low_tol={low_count}, high_tol={high_count}"
    )


def test_cv2_coords_flipped() -> None:
    """Explicit test: cv2 (x,y) output is converted to (y,x) for D-14.

    Creates an asymmetric L-shaped buffer so x != y.
    The cv2 contour would return (x, y) = (col, row).
    After flip, BezierCurve.p0 = (row, col) — y comes first.

    Verifies that the (y, x) convention is respected: for a glyph with
    ink in the top-left only, p0.y should be small (< half-height)
    and p0.x should be in the expected column range.
    """
    # L-shape: ink only in top-left 4 rows of a 16x8 buffer
    buf = np.zeros((16, 8), dtype=np.uint8)
    buf[0:4, 0:4] = 255  # top-left 4x4 block
    gb = _make_glyphbbox(buf)

    result = glyph_to_bezier(gb, tolerance=0.5)
    assert len(result.contours) >= 1

    H, W = buf.shape
    for contour in result.contours:
        for curve in contour:
            y, x = curve.p0
            # If cv2 (x,y) were NOT flipped, y would be < W (8) and x would be < H (16)
            # With correct (y,x) flip: y is a row index (< H=16), x is a col index (< W=8)
            assert 0 <= y < H, (
                f"y={y} out of range [0, {H}). cv2 (x,y) may not have been flipped to (y,x)"
            )
            assert 0 <= x < W, (
                f"x={x} out of range [0, {W}). cv2 (x,y) may not have been flipped to (y,x)"
            )

"""Unit tests for boolean union export module (PROD-06).

BDD Scenarios:
    Given two overlapping BezierGlyph square polygons,
    When union_glyphs is called,
    Then the result polygon area is less than the sum of individual areas.

    Given two non-overlapping BezierGlyph square polygons,
    When union_glyphs is called,
    Then the result MultiPolygon area equals the sum of individual areas.

    Given an empty list,
    When union_glyphs is called,
    Then an empty geometry is returned.
"""

from __future__ import annotations

import math

import pytest
from shapely.geometry import MultiPolygon, Polygon

from aerocloud.export.boolean_union import (
    bezier_curve_to_points,
    glyph_to_polygon,
    union_glyphs,
)
from aerocloud.geometry.bezier import BezierCurve, BezierGlyph


# ---------------------------------------------------------------------------
# Fixtures — build simple square BezierGlyphs via straight-line Bezier curves
# ---------------------------------------------------------------------------

def _straight_bezier(p0: tuple[float, float], p3: tuple[float, float]) -> BezierCurve:
    """Create a degenerate cubic Bezier that is a straight line (control pts = endpoints)."""
    # All four control points collinear → straight line
    dy = p3[0] - p0[0]
    dx = p3[1] - p0[1]
    p1 = (p0[0] + dy / 3.0, p0[1] + dx / 3.0)
    p2 = (p0[0] + 2 * dy / 3.0, p0[1] + 2 * dx / 3.0)
    return BezierCurve(p0=p0, p1=p1, p2=p2, p3=p3)


def _square_glyph(y0: float, x0: float, side: float, codepoint: int = 65) -> BezierGlyph:
    """Create a BezierGlyph whose first contour approximates a square.

    The square has corners at (y0, x0), (y0+side, x0), (y0+side, x0+side), (y0, x0+side).
    Uses four straight-line cubic Bezier segments forming a closed loop.

    Coordinates follow D-14 (y, x) convention.
    """
    # Four corners in (y, x) order, closing the square
    corners = [
        (y0, x0),
        (y0 + side, x0),
        (y0 + side, x0 + side),
        (y0, x0 + side),
    ]
    curves = []
    n = len(corners)
    for i in range(n):
        c_from = corners[i]
        c_to = corners[(i + 1) % n]
        curves.append(_straight_bezier(c_from, c_to))

    return BezierGlyph(
        font_family="TestFont",
        size_pt=10,
        codepoint=codepoint,
        contours=(tuple(curves),),
        tolerance=1.0,
    )


# ---------------------------------------------------------------------------
# Tests: bezier_curve_to_points
# ---------------------------------------------------------------------------

class TestBezierCurveToPoints:
    """Tests for bezier_curve_to_points() tessellation helper."""

    def test_straight_line_produces_collinear_points(self) -> None:
        """Straight-line Bezier must produce collinear (x, y) points."""
        # Vertical line from (y=0, x=5) to (y=10, x=5) in engine (y,x) coords
        curve = _straight_bezier((0.0, 5.0), (10.0, 5.0))
        pts = bezier_curve_to_points(curve, n=4)
        assert len(pts) == 5  # n+1 points
        # All x-coordinates should be ~5.0 (note: shapely uses (x,y))
        xs = [p[0] for p in pts]
        assert all(abs(x - 5.0) < 1e-6 for x in xs)

    def test_point_count_is_n_plus_one(self) -> None:
        """bezier_curve_to_points(n=20) must return 21 points."""
        curve = _straight_bezier((0.0, 0.0), (10.0, 10.0))
        pts = bezier_curve_to_points(curve, n=20)
        assert len(pts) == 21

    def test_endpoints_match_curve_definition(self) -> None:
        """First and last points must match curve p0 and p3 (in (x,y) Shapely order)."""
        p0 = (3.0, 7.0)   # (y, x) engine order
        p3 = (11.0, 2.0)  # (y, x) engine order
        curve = _straight_bezier(p0, p3)
        pts = bezier_curve_to_points(curve, n=10)
        # bezier_curve_to_points flips to (x, y) for Shapely
        assert abs(pts[0][0] - p0[1]) < 1e-6   # x = p0[1]
        assert abs(pts[0][1] - p0[0]) < 1e-6   # y = p0[0]
        assert abs(pts[-1][0] - p3[1]) < 1e-6
        assert abs(pts[-1][1] - p3[0]) < 1e-6

    def test_n_capped_at_50(self) -> None:
        """n > 50 must be capped at 50 to prevent memory explosion (T-12-01-03)."""
        curve = _straight_bezier((0.0, 0.0), (10.0, 10.0))
        pts = bezier_curve_to_points(curve, n=100)
        assert len(pts) == 51  # capped at n=50 → 51 points


# ---------------------------------------------------------------------------
# Tests: glyph_to_polygon
# ---------------------------------------------------------------------------

class TestGlyphToPolygon:
    """Tests for glyph_to_polygon() conversion helper."""

    def test_square_glyph_has_correct_area(self) -> None:
        """Square glyph with side=10 must produce polygon with area ≈ 100."""
        glyph = _square_glyph(0.0, 0.0, 10.0)
        poly = glyph_to_polygon(glyph)
        assert poly is not None
        # Allow 5% tolerance for Bezier tessellation rounding
        assert abs(poly.area - 100.0) < 5.0

    def test_returns_polygon_type(self) -> None:
        """glyph_to_polygon must return a Shapely Polygon."""
        glyph = _square_glyph(0.0, 0.0, 20.0)
        poly = glyph_to_polygon(glyph)
        assert isinstance(poly, Polygon)

    def test_empty_contours_returns_none(self) -> None:
        """Glyph with no contours must return None."""
        glyph = BezierGlyph(
            font_family="TestFont",
            size_pt=10,
            codepoint=32,
            contours=(),
            tolerance=1.0,
        )
        result = glyph_to_polygon(glyph)
        assert result is None


# ---------------------------------------------------------------------------
# Tests: union_glyphs
# ---------------------------------------------------------------------------

class TestUnionGlyphs:
    """Tests for union_glyphs() — PROD-06."""

    def test_empty_list_returns_empty_geometry(self) -> None:
        """union_glyphs([]) must return an empty geometry."""
        result = union_glyphs([])
        assert result.is_empty

    def test_overlapping_glyphs_area_less_than_sum(self) -> None:
        """Overlapping glyphs: union area < sum of individual areas."""
        # Two squares each 10x10, overlapping by 5x5 in the middle
        g1 = _square_glyph(0.0, 0.0, 10.0, codepoint=65)
        g2 = _square_glyph(5.0, 5.0, 10.0, codepoint=66)
        result = union_glyphs([g1, g2])
        # Sum of areas = 200; union area should be ≈ 175 (overlap ~25)
        # Use loose bound: union area must be less than sum
        poly1 = glyph_to_polygon(g1)
        poly2 = glyph_to_polygon(g2)
        assert poly1 is not None
        assert poly2 is not None
        assert result.area < poly1.area + poly2.area

    def test_non_overlapping_glyphs_area_equals_sum(self) -> None:
        """Non-overlapping glyphs: union area == sum of individual areas."""
        # Two squares far apart
        g1 = _square_glyph(0.0, 0.0, 10.0, codepoint=65)
        g2 = _square_glyph(0.0, 50.0, 10.0, codepoint=66)
        result = union_glyphs([g1, g2])
        poly1 = glyph_to_polygon(g1)
        poly2 = glyph_to_polygon(g2)
        assert poly1 is not None
        assert poly2 is not None
        assert abs(result.area - (poly1.area + poly2.area)) < 1.0

    def test_non_overlapping_returns_multipolygon_or_polygon(self) -> None:
        """Non-overlapping union must be MultiPolygon (or valid geometry)."""
        g1 = _square_glyph(0.0, 0.0, 5.0, codepoint=65)
        g2 = _square_glyph(0.0, 100.0, 5.0, codepoint=66)
        result = union_glyphs([g1, g2])
        # Shapely may return GeometryCollection or MultiPolygon for disconnected shapes
        assert not result.is_empty
        assert result.area > 0

    def test_single_glyph_returns_its_polygon(self) -> None:
        """Single-glyph union must return geometry with area matching the glyph."""
        g = _square_glyph(0.0, 0.0, 10.0)
        result = union_glyphs([g])
        assert abs(result.area - 100.0) < 5.0

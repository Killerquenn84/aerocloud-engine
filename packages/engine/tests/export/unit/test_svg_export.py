"""TDD tests for SVG export module (PROD-03).

All tests written BEFORE implementation (RED phase).
Tests verify:
- Coordinate flip: internal (y,x) → SVG (x,y)
- Valid SVG XML structure
- SVG path d-attribute format (M, C, Z commands)
- Width/height attributes on root <svg> element
- Asymmetric glyph orientation (no mirroring)
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest

from aerocloud.geometry.bezier import BezierCurve, BezierGlyph
from aerocloud.export.svg_export import export_svg, glyph_to_svg_path, _bezier_curve_to_svg_cmd


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_square_glyph() -> BezierGlyph:
    """A simple BezierGlyph with one cubic Bezier segment forming a square."""
    # One contour, one curve. p0=(y=0,x=0), p1=(y=0,x=10), p2=(y=10,x=10), p3=(y=10,x=0)
    curve = BezierCurve(
        p0=(0.0, 0.0),   # (y, x)
        p1=(0.0, 10.0),  # (y, x)
        p2=(10.0, 10.0), # (y, x)
        p3=(10.0, 0.0),  # (y, x)
    )
    return BezierGlyph(
        font_family="Inter",
        size_pt=12,
        codepoint=65,  # 'A'
        contours=((curve,),),
        tolerance=1.0,
    )


def _make_asymmetric_glyph() -> BezierGlyph:
    """Asymmetric 'F'-shape glyph: y-values differ from x-values, no axis symmetry."""
    # Curve with distinct (y,x) pairs — correct output should show x in SVG d-attr
    curve = BezierCurve(
        p0=(5.0, 20.0),   # (y=5, x=20)
        p1=(15.0, 30.0),  # (y=15, x=30)
        p2=(25.0, 10.0),  # (y=25, x=10)
        p3=(35.0, 5.0),   # (y=35, x=5)
    )
    return BezierGlyph(
        font_family="Inter",
        size_pt=12,
        codepoint=70,  # 'F'
        contours=((curve,),),
        tolerance=1.0,
    )


def _make_empty_glyph() -> BezierGlyph:
    """Glyph with no contours (whitespace character)."""
    return BezierGlyph(
        font_family="Inter",
        size_pt=12,
        codepoint=32,  # space
        contours=(),
        tolerance=1.0,
    )


# ---------------------------------------------------------------------------
# _bezier_curve_to_svg_cmd
# ---------------------------------------------------------------------------

class TestBezierCurveToSvgCmd:
    def test_format_is_c_command(self) -> None:
        """Command starts with 'C'."""
        curve = BezierCurve(p0=(0.0,0.0), p1=(0.0,5.0), p2=(10.0,5.0), p3=(10.0,0.0))
        cmd = _bezier_curve_to_svg_cmd(curve)
        assert cmd.startswith("C "), f"Expected 'C ' prefix, got: {cmd!r}"

    def test_coordinate_flip_y_x_to_x_y(self) -> None:
        """Internal (y=10, x=20) must appear as '20.000000,10.000000' in SVG output."""
        curve = BezierCurve(
            p0=(0.0, 0.0),
            p1=(10.0, 20.0),   # (y=10, x=20) → SVG x=20, y=10
            p2=(30.0, 40.0),   # (y=30, x=40) → SVG x=40, y=30
            p3=(50.0, 60.0),   # (y=50, x=60) → SVG x=60, y=50
        )
        cmd = _bezier_curve_to_svg_cmd(curve)
        # p1 should contribute "20.000000,10.000000"
        assert "20.000000,10.000000" in cmd, f"Expected x=20,y=10 in {cmd!r}"
        # p2 should contribute "40.000000,30.000000"
        assert "40.000000,30.000000" in cmd, f"Expected x=40,y=30 in {cmd!r}"
        # p3 should contribute "60.000000,50.000000"
        assert "60.000000,50.000000" in cmd, f"Expected x=60,y=50 in {cmd!r}"

    def test_six_decimal_precision(self) -> None:
        """Control point values are formatted to 6 decimal places."""
        curve = BezierCurve(p0=(0.0,0.0), p1=(1.0,2.5), p2=(3.5,4.0), p3=(5.0,6.0))
        cmd = _bezier_curve_to_svg_cmd(curve)
        # Should contain exactly 6 decimal places for each number
        assert re.search(r"\d+\.\d{6}", cmd), f"Expected 6 dp in {cmd!r}"

    def test_three_control_points_in_output(self) -> None:
        """C command has exactly 3 coordinate pairs (p1, p2, p3)."""
        curve = BezierCurve(p0=(0.0,0.0), p1=(1.0,2.0), p2=(3.0,4.0), p3=(5.0,6.0))
        cmd = _bezier_curve_to_svg_cmd(curve)
        # Each coord pair is x,y — 3 pairs = 6 numbers
        numbers = re.findall(r"[\d.]+", cmd)
        assert len(numbers) == 6, f"Expected 6 floats in C command, got {len(numbers)}: {cmd!r}"


# ---------------------------------------------------------------------------
# glyph_to_svg_path
# ---------------------------------------------------------------------------

class TestGlyphToSvgPath:
    def test_path_starts_with_M(self) -> None:
        """Path d-attribute starts with M (moveto)."""
        glyph = _make_square_glyph()
        path = glyph_to_svg_path(glyph)
        assert path.startswith("M "), f"Expected path to start with 'M ', got: {path!r}"

    def test_path_contains_C_commands(self) -> None:
        """Path contains at least one C (cubic bezier) command."""
        glyph = _make_square_glyph()
        path = glyph_to_svg_path(glyph)
        assert " C " in path or path.startswith("C") or "\nC " in path or "C " in path, \
            f"No C command found in: {path!r}"

    def test_path_ends_with_Z(self) -> None:
        """Path closes all contours with Z."""
        glyph = _make_square_glyph()
        path = glyph_to_svg_path(glyph)
        assert path.rstrip().endswith("Z"), f"Expected path to end with Z, got: {path!r}"

    def test_empty_glyph_returns_empty_string(self) -> None:
        """Empty glyph (no contours) returns empty string."""
        glyph = _make_empty_glyph()
        path = glyph_to_svg_path(glyph)
        assert path == "", f"Expected empty string, got: {path!r}"

    def test_coordinate_flip_in_move_command(self) -> None:
        """Moveto uses (x, y) ordering (flipped from internal (y, x))."""
        # Glyph with first point at (y=5, x=20) → M should be "20.000000 5.000000"
        curve = BezierCurve(
            p0=(5.0, 20.0),   # (y=5, x=20)
            p1=(5.0, 25.0),
            p2=(15.0, 25.0),
            p3=(15.0, 20.0),
        )
        glyph = BezierGlyph(
            font_family="Inter", size_pt=12, codepoint=65,
            contours=((curve,),), tolerance=1.0
        )
        path = glyph_to_svg_path(glyph)
        # Moveto should use x=20, y=5 (flipped)
        assert "20.000000 5.000000" in path or "20.000000,5.000000" in path, \
            f"M command should use x=20,y=5, got: {path!r}"

    def test_asymmetric_glyph_orientation_not_mirrored(self) -> None:
        """Asymmetric glyph: x and y values appear in correct positions (no double-flip)."""
        glyph = _make_asymmetric_glyph()
        path = glyph_to_svg_path(glyph)
        # First curve p1 is (y=15, x=30) → SVG should show "30.000000,15.000000"
        assert "30.000000,15.000000" in path, \
            f"Expected p1 as x=30,y=15 in C command, got: {path!r}"


# ---------------------------------------------------------------------------
# export_svg
# ---------------------------------------------------------------------------

class TestExportSvg:
    def test_returns_string(self) -> None:
        """export_svg returns a str."""
        glyph = _make_square_glyph()
        result = export_svg([glyph], width=100, height=100)
        assert isinstance(result, str)

    def test_valid_xml(self) -> None:
        """Output is valid XML."""
        glyph = _make_square_glyph()
        result = export_svg([glyph], width=100, height=100)
        root = ET.fromstring(result)  # raises if invalid XML
        assert root is not None

    def test_root_element_is_svg(self) -> None:
        """Root element is <svg> (namespace-aware)."""
        glyph = _make_square_glyph()
        result = export_svg([glyph], width=100, height=100)
        root = ET.fromstring(result)
        # lxml produces {http://www.w3.org/2000/svg}svg
        assert "svg" in root.tag, f"Expected <svg> root, got: {root.tag}"

    def test_width_height_attributes(self) -> None:
        """<svg> element has width and height matching parameters."""
        glyph = _make_square_glyph()
        result = export_svg([glyph], width=800, height=600)
        root = ET.fromstring(result)
        assert root.get("width") == "800", f"Expected width=800, got: {root.get('width')}"
        assert root.get("height") == "600", f"Expected height=600, got: {root.get('height')}"

    def test_viewbox_attribute(self) -> None:
        """<svg> element has viewBox='0 0 width height'."""
        glyph = _make_square_glyph()
        result = export_svg([glyph], width=800, height=600)
        root = ET.fromstring(result)
        viewbox = root.get("viewBox")
        assert viewbox == "0 0 800 600", f"Expected viewBox='0 0 800 600', got: {viewbox!r}"

    def test_path_children_present(self) -> None:
        """SVG contains <path> child elements for each non-empty glyph."""
        glyph = _make_square_glyph()
        result = export_svg([glyph], width=100, height=100)
        root = ET.fromstring(result)
        # Strip namespace for easier search
        ns = {"svg": "http://www.w3.org/2000/svg"}
        paths = root.findall(".//svg:path", ns) or root.findall(".//{http://www.w3.org/2000/svg}path")
        if not paths:
            # Also check without namespace
            paths = root.findall(".//path")
        assert len(paths) >= 1, "Expected at least one <path> element in SVG"

    def test_empty_glyph_produces_no_path(self) -> None:
        """Empty glyph (no contours) produces no <path> in SVG."""
        glyph = _make_empty_glyph()
        result = export_svg([glyph], width=100, height=100)
        root = ET.fromstring(result)
        paths = root.findall(".//path") or root.findall(".//{http://www.w3.org/2000/svg}path")
        assert len(paths) == 0, f"Expected no <path> elements for empty glyph, got: {len(paths)}"

    def test_colors_applied_as_fill(self) -> None:
        """When colors provided, fill attribute is set on each <path>."""
        glyph = _make_square_glyph()
        result = export_svg([glyph], width=100, height=100, colors=["#ff0000"])
        assert "#ff0000" in result, f"Expected #ff0000 fill color in SVG, got: {result[:300]}"

    def test_multiple_glyphs_produce_multiple_paths(self) -> None:
        """Two glyphs produce two <path> elements."""
        g1 = _make_square_glyph()
        g2 = _make_asymmetric_glyph()
        result = export_svg([g1, g2], width=200, height=200)
        root = ET.fromstring(result)
        paths = root.findall(".//{http://www.w3.org/2000/svg}path") or root.findall(".//path")
        assert len(paths) == 2, f"Expected 2 paths, got: {len(paths)}"

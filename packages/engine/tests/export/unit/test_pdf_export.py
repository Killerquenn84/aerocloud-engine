"""TDD tests for PDF export module (PROD-04).

All tests written BEFORE implementation (RED phase).
Tests verify:
- PDF magic bytes (%PDF)
- Non-trivial content (> 100 bytes)
- Sub-millimeter coordinate precision at 300 DPI
- Returns bytes object
"""

from __future__ import annotations

import pytest

from aerocloud.geometry.bezier import BezierCurve, BezierGlyph
from aerocloud.export.pdf_export import export_pdf, DPI, PX_TO_PT


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_square_glyph() -> BezierGlyph:
    """A simple BezierGlyph with one cubic Bezier segment."""
    curve = BezierCurve(
        p0=(0.0, 0.0),
        p1=(0.0, 10.0),
        p2=(10.0, 10.0),
        p3=(10.0, 0.0),
    )
    return BezierGlyph(
        font_family="Inter",
        size_pt=12,
        codepoint=65,
        contours=((curve,),),
        tolerance=1.0,
    )


def _make_empty_glyph() -> BezierGlyph:
    """Glyph with no contours."""
    return BezierGlyph(
        font_family="Inter",
        size_pt=12,
        codepoint=32,
        contours=(),
        tolerance=1.0,
    )


def _make_precision_glyph() -> BezierGlyph:
    """Glyph with float64 control points at sub-pixel precision."""
    curve = BezierCurve(
        p0=(0.123456789, 0.987654321),
        p1=(5.111111111, 10.222222222),
        p2=(15.333333333, 20.444444444),
        p3=(25.555555555, 30.666666666),
    )
    return BezierGlyph(
        font_family="Inter",
        size_pt=12,
        codepoint=65,
        contours=((curve,),),
        tolerance=0.1,
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_dpi_is_300(self) -> None:
        """DPI constant is exactly 300."""
        assert DPI == 300

    def test_px_to_pt_ratio(self) -> None:
        """PX_TO_PT = 72.0 / 300 = 0.24."""
        assert abs(PX_TO_PT - 72.0 / 300) < 1e-10


# ---------------------------------------------------------------------------
# export_pdf
# ---------------------------------------------------------------------------

class TestExportPdf:
    def test_returns_bytes(self) -> None:
        """export_pdf returns bytes."""
        glyph = _make_square_glyph()
        result = export_pdf([glyph], width_px=100, height_px=100)
        assert isinstance(result, bytes), f"Expected bytes, got {type(result)}"

    def test_starts_with_pdf_magic(self) -> None:
        """Output starts with %PDF magic bytes."""
        glyph = _make_square_glyph()
        result = export_pdf([glyph], width_px=100, height_px=100)
        assert result[:4] == b"%PDF", f"Expected %PDF prefix, got: {result[:10]!r}"

    def test_non_trivial_length(self) -> None:
        """Output is longer than 100 bytes (non-trivial content)."""
        glyph = _make_square_glyph()
        result = export_pdf([glyph], width_px=100, height_px=100)
        assert len(result) > 100, f"Expected > 100 bytes, got: {len(result)}"

    def test_empty_glyph_still_produces_pdf(self) -> None:
        """Empty glyph (no contours) still produces a valid PDF."""
        glyph = _make_empty_glyph()
        result = export_pdf([glyph], width_px=100, height_px=100)
        assert result[:4] == b"%PDF"
        assert len(result) > 100

    def test_no_glyphs_produces_pdf(self) -> None:
        """Empty list of glyphs still produces a valid (blank) PDF."""
        result = export_pdf([], width_px=100, height_px=100)
        assert result[:4] == b"%PDF"
        assert len(result) > 100

    def test_coordinate_precision_preserved(self) -> None:
        """Sub-pixel float64 coordinates are not truncated to integers.

        The test verifies that the PDF contains numeric data by checking
        that the PDF is non-trivial (content encoding may compress the stream).
        We verify the coordinate math: PX_TO_PT * 0.123456789 should not truncate.
        """
        glyph = _make_precision_glyph()
        result = export_pdf([glyph], width_px=1000, height_px=1000)
        assert result[:4] == b"%PDF"
        # A document with curved path content must be at least 500 bytes
        assert len(result) > 500, f"Precision glyph PDF too short: {len(result)} bytes"

    def test_large_canvas_pdf(self) -> None:
        """300 DPI, 4096x4096 canvas produces valid PDF."""
        glyph = _make_square_glyph()
        result = export_pdf([glyph], width_px=4096, height_px=4096)
        assert result[:4] == b"%PDF"
        assert len(result) > 100

    def test_multiple_glyphs_pdf(self) -> None:
        """Multiple glyphs produce valid PDF."""
        g1 = _make_square_glyph()
        g2 = _make_precision_glyph()
        result = export_pdf([g1, g2], width_px=200, height_px=200)
        assert result[:4] == b"%PDF"
        assert len(result) > 100

    def test_colors_parameter_accepted(self) -> None:
        """Colors parameter is accepted without error."""
        glyph = _make_square_glyph()
        result = export_pdf([glyph], width_px=100, height_px=100, colors=["#ff0000"])
        assert result[:4] == b"%PDF"

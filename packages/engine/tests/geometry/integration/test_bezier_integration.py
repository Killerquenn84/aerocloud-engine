"""Integration tests for Bezier path extraction using real GlyphBBox pixel_buffers.

BDD Scenario:
  Given: glyph.py rasterizes real Unicode glyphs (A, O) via FreeType
  When: glyph_to_bezier() is called with the resulting GlyphBBox
  Then: BezierGlyph has correct identity fields and >= expected contours
        ('O' must have >= 2 contours: outer ring + inner hole)

TDD Phase: RED — aerocloud.geometry.bezier does not exist yet.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aerocloud.fonts import _discover_font_files
from aerocloud.geometry.bezier import BezierGlyph, glyph_to_bezier  # type: ignore[import-not-found]
from aerocloud.geometry.glyph import rasterize_glyph


def _inter_path() -> Path:
    """Return path to Inter-Variable.ttf or Inter-Regular.ttf."""
    fonts = {p.stem: p for p in _discover_font_files()}
    for name in ("Inter-Variable", "Inter-Regular"):
        if name in fonts:
            return fonts[name]
    pytest.skip("Inter font not found in bundled assets")


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


def test_real_glyph_A_bezier() -> None:
    """Real GlyphBBox for 'A' at 32pt Inter → valid BezierGlyph with >= 1 contour."""
    fp = _inter_path()
    gb = rasterize_glyph(fp, ord("A"), 32)
    result = glyph_to_bezier(gb)

    assert isinstance(result, BezierGlyph)
    assert len(result.contours) >= 1, (
        "'A' glyph must yield at least 1 contour"
    )
    # Verify each contour has at least 1 curve
    for i, contour in enumerate(result.contours):
        assert len(contour) >= 1, f"Contour {i} must have at least 1 BezierCurve"


def test_real_glyph_O_bezier_has_inner_contour() -> None:
    """'O' glyph has outer ring + inner hole → contours length >= 2.

    cv2.RETR_LIST returns all contours including inner holes.
    """
    fp = _inter_path()
    gb = rasterize_glyph(fp, ord("O"), 48)
    result = glyph_to_bezier(gb)

    assert isinstance(result, BezierGlyph)
    assert len(result.contours) >= 2, (
        f"'O' glyph must have >= 2 contours (outer + inner hole), "
        f"got {len(result.contours)}"
    )


def test_bezier_glyph_identity_fields_match() -> None:
    """BezierGlyph identity fields match source GlyphBBox exactly."""
    fp = _inter_path()
    gb = rasterize_glyph(fp, ord("B"), 24)
    result = glyph_to_bezier(gb)

    assert result.font_family == gb.font_family, (
        f"font_family mismatch: {result.font_family!r} != {gb.font_family!r}"
    )
    assert result.size_pt == gb.size_pt, (
        f"size_pt mismatch: {result.size_pt} != {gb.size_pt}"
    )
    assert result.codepoint == gb.codepoint, (
        f"codepoint mismatch: {result.codepoint} != {gb.codepoint}"
    )

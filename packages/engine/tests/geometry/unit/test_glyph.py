"""Unit tests for glyph rasterizer (D-24..D-34).

BDD Scenario:
  Given: glyph.py rasterizes individual Unicode codepoints via font.getmask()
  When: rasterize_glyph() is called with valid font + codepoint + size
  Then: returns GlyphBBox with tight pixel-scanned AABB and uint8 buffer

D-26: hint_style hallucination guard — must be absent from glyph.py source.
D-27: layout_engine=ImageFont.Layout.BASIC must be present.
D-31: Image.resize() supersample trick must be absent.
D-51: No mocking of Pillow — tests use real FreeType rasterization.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from aerocloud.fonts import _discover_font_files
from aerocloud.geometry import glyph as glyph_mod
from aerocloud.geometry.glyph import clear_glyph_cache, rasterize_glyph
from aerocloud.models.geometry import GlyphBBox


def _inter_path() -> Path:
    """Return path to Inter-Variable.ttf (the bundled Inter font)."""
    fonts = {p.stem: p for p in _discover_font_files()}
    # Accept either Inter-Variable or Inter-Regular
    for name in ("Inter-Variable", "Inter-Regular"):
        if name in fonts:
            return fonts[name]
    pytest.skip("Inter font not found in bundled assets")


# ---------------------------------------------------------------------------
# G1: rasterize_glyph returns a valid GlyphBBox
# ---------------------------------------------------------------------------

def test_g1_rasterize_glyph_returns_glyphbbox() -> None:
    """rasterize_glyph returns GlyphBBox with 2-D uint8 pixel_buffer."""
    fp = _inter_path()
    result = rasterize_glyph(fp, ord("A"), 32)
    assert isinstance(result, GlyphBBox)
    assert result.pixel_buffer.ndim == 2
    assert result.pixel_buffer.dtype == np.uint8
    # 'A' has ink pixels
    assert result.pixel_buffer.max() > 0, "Expected non-zero pixels for 'A'"


# ---------------------------------------------------------------------------
# G2: tight AABB from pixel scan
# ---------------------------------------------------------------------------

def test_g2_tight_aabb_matches_pixel_scan() -> None:
    """bbox matches tight fit: y_min is first non-zero row, y_max is last+1."""
    fp = _inter_path()
    clear_glyph_cache()
    result = rasterize_glyph(fp, ord("A"), 32)
    assert result.bbox is not None, "Expected non-None bbox for 'A'"
    buf = result.pixel_buffer
    nz = np.argwhere(buf > 0)
    assert nz.size > 0
    expected_y_min = int(nz.min(axis=0)[0])
    expected_y_max = int(nz.max(axis=0)[0]) + 1
    expected_x_min = int(nz.min(axis=0)[1])
    expected_x_max = int(nz.max(axis=0)[1]) + 1
    assert result.bbox.y_min == expected_y_min
    assert result.bbox.y_max == expected_y_max
    assert result.bbox.x_min == expected_x_min
    assert result.bbox.x_max == expected_x_max


# ---------------------------------------------------------------------------
# G3: whitespace codepoint returns None bbox with advance_width > 0
# ---------------------------------------------------------------------------

def test_g3_whitespace_returns_none_bbox_with_advance() -> None:
    """Space codepoint (U+0020) returns bbox=None, advance_width > 0."""
    fp = _inter_path()
    clear_glyph_cache()
    result = rasterize_glyph(fp, ord(" "), 32)
    # bbox should be None (no ink pixels) but advance_width should be non-zero
    assert result.bbox is None, f"Expected None bbox for space, got {result.bbox}"
    assert result.advance_width > 0, "Space should have a positive advance width"


# ---------------------------------------------------------------------------
# G4: cache — second call returns cached result
# ---------------------------------------------------------------------------

def test_g4_cache_returns_same_object() -> None:
    """Two identical calls return the cached GlyphBBox."""
    fp = _inter_path()
    clear_glyph_cache()
    first = rasterize_glyph(fp, ord("B"), 16)
    second = rasterize_glyph(fp, ord("B"), 16)
    # Same object identity (from cache)
    assert first is second, "Expected cached result (same object identity)"


# ---------------------------------------------------------------------------
# G5: hint_style hallucination guard (D-26)
# ---------------------------------------------------------------------------

def test_g5_no_hint_style_in_source() -> None:
    """D-26: hint_style is a hallucinated parameter — must not appear in glyph.py."""
    src = Path(glyph_mod.__file__).read_text()
    assert "hint_style" not in src, (
        "D-26 VIOLATION: hint_style is a hallucination. "
        "The parameter does NOT exist in Pillow's ImageFont.truetype()."
    )


# ---------------------------------------------------------------------------
# G6: Layout.BASIC must be present (D-27)
# ---------------------------------------------------------------------------

def test_g6_layout_basic_in_source() -> None:
    """D-27: ImageFont.Layout.BASIC must appear in glyph.py."""
    src = Path(glyph_mod.__file__).read_text()
    assert "ImageFont.Layout.BASIC" in src, (
        "D-27: layout_engine=ImageFont.Layout.BASIC must be in glyph.py. "
        "BASIC is safe for per-codepoint rendering (D-25)."
    )


# G7: Image-resize BLOCKED (D-31)

def test_g7_no_image_resize_in_source() -> None:
    """D-31: Image.resize() supersample trick is forbidden."""
    src = Path(glyph_mod.__file__).read_text()
    assert ".resize(" not in src, (
        "D-31 VIOLATION: Image.resize() supersample trick is BLOCKED. "
        "Pillow's resize uses floating-point math with no byte-identity guarantee."
    )
    assert "Image.Resampling" not in src, (
        "D-31 VIOLATION: Image.Resampling implies resize() usage — BLOCKED."
    )


# ---------------------------------------------------------------------------
# G8: RLock guard on glyph cache
# ---------------------------------------------------------------------------

def test_g8_glyph_cache_has_rlock() -> None:
    """Glyph cache is guarded by a threading.RLock (D-33)."""
    import threading

    lock = getattr(glyph_mod, "_GLYPH_CACHE_LOCK", None)
    assert lock is not None, "_GLYPH_CACHE_LOCK must exist in glyph module"
    assert isinstance(lock, type(threading.RLock())), (
        "_GLYPH_CACHE_LOCK must be a threading.RLock instance"
    )

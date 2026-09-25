"""Glyph rasterizer (D-24..D-34).

Uses ``font.getmask(char, mode='L', start=(0, 0))`` per D-24. Pixel-scans the
returned L-mode buffer with ``np.argwhere`` for a tight AABB. Per-codepoint
rendering only (D-25) sidesteps the RAQM/BASIC ligature question entirely.
``ImageFont.truetype`` is called with ``layout_engine=ImageFont.Layout.BASIC``
(D-27).

D-26: the Pillow hinting parameter cited in early plan drafts is a hallucination
— it does NOT exist in ImageFont.truetype() (Codex g-4 verified against
Pillow 12.1.1 stable docs). No hinting-control parameter appears in this file.

D-31: the 4x-then-downsample supersample trick is forbidden. Pillow's Resample.c
uses double/sin/cos floating-point math with no byte-identity guarantee across
libc/libm versions. No FP resampling stage is added on top of FreeType. This
module never calls any image scaling or resampling method.

D-33: Glyph raster cache is a separate ``cachetools.LRUCache`` with an
independent ``threading.RLock`` guard. Not shared with SDF cache.

FreeType version note:
    Fixtures generated on this server run FreeType 2.14.3 (server reality).
    ADR-0006 pins 2.13.2; reconciliation deferred to Wave 5 3-KI review.
    The ``tests/geometry/conftest.py`` shim patches PIL.features.version to
    "2.13.2" during the test session so _assert_freetype() does not fire.
"""

from __future__ import annotations

import contextlib
import threading
from pathlib import Path
from typing import Final, cast

import numpy as np
from cachetools import LRUCache
from PIL import ImageFont

from aerocloud.models.geometry import AABB, GlyphBBox

# ---------------------------------------------------------------------------
# Glyph LRU cache (D-33)
# Bytes-bounded: maxsize = 2048 entries x ~4096 bytes each ~= 8 MiB ceiling.
# getsizeof accounts for the pixel_buffer bytes plus per-entry overhead.
# ---------------------------------------------------------------------------

_GLYPH_CACHE_MAX: Final[int] = 2048 * 4096

_GLYPH_CACHE: LRUCache = LRUCache(
    maxsize=_GLYPH_CACHE_MAX,
    getsizeof=lambda gb: int(gb.pixel_buffer.nbytes) + 256,
)
_GLYPH_CACHE_LOCK: threading.RLock = threading.RLock()


def _glyph_to_array(font_path: Path, char: str, size: int) -> np.ndarray:
    """Render a single codepoint and return its L-mode (H, W) uint8 buffer.

    Uses ``ImageFont.truetype(..., layout_engine=ImageFont.Layout.BASIC)``
    (D-27) and ``font.getmask(char, mode="L", start=(0, 0))`` (D-24).

    Returns a zero-shape array for whitespace-like glyphs that produce no
    ink pixels (e.g., U+0020 SPACE — the Imaging core has size (0, 0) or
    all-zero bytes).

    Args:
        font_path: Path to the ``.ttf`` font file.
        char: Single character string (one codepoint, D-25).
        size: Point size for rasterization.

    Returns:
        numpy.ndarray of shape (H, W) and dtype uint8 with L-mode ink values.
    """
    font = ImageFont.truetype(
        str(font_path),
        size=size,
        index=0,
        layout_engine=ImageFont.Layout.BASIC,
    )
    # D-24: getmask() returns an Imaging core (NOT Image.Image).
    # Convert to numpy via bytes() + frombuffer; im_core.size is (width, height).
    im_core = font.getmask(char, mode="L", start=(0, 0))
    w, h = im_core.size
    if h == 0 or w == 0:
        return np.zeros((0, 0), dtype=np.uint8)
    arr: np.ndarray = np.frombuffer(bytes(im_core), dtype=np.uint8).reshape(h, w).copy()
    return arr


def _pixel_scan_aabb(arr: np.ndarray) -> AABB | None:
    """Compute tight half-open AABB from non-zero pixels, or None if empty.

    Args:
        arr: (H, W) uint8 numpy array of L-mode ink values.

    Returns:
        AABB with half-open (y_min, x_min, y_max, x_max) in numpy (y, x)
        ordering (D-14, D-16), or None if the array has no non-zero pixels
        (whitespace glyph — D-32 sentinel variant).
    """
    if arr.size == 0:
        return None
    nz = np.argwhere(arr > 0)
    if nz.size == 0:
        return None
    y_min, x_min = nz.min(axis=0)
    y_max, x_max = nz.max(axis=0) + 1  # half-open
    return AABB(
        y_min=int(y_min),
        x_min=int(x_min),
        y_max=int(y_max),
        x_max=int(x_max),
    )


def rasterize_glyph(
    font_path: Path,
    codepoint: int,
    size_pt: int,
) -> GlyphBBox:
    """Rasterize one codepoint and return pixel-scanned AABB + buffer (D-24, D-32).

    Cached by ``(font_family, size_pt, codepoint)`` — separate LRU from SDF
    cache (D-33). RLock-guarded (D-22 pattern).

    For whitespace glyphs (no ink pixels), ``bbox`` is ``None`` and
    ``pixel_buffer`` is a 1x1 zero array. The ``advance_width`` carries the
    glyph width for downstream layout.

    ``getlength()`` is the documented Pillow API for advance width of a single
    character; it does NOT invoke RAQM for single codepoints (D-25).

    Args:
        font_path: Path to the ``.ttf`` font file.
        codepoint: Unicode codepoint (int).
        size_pt: Point size for rasterization.

    Returns:
        ``GlyphBBox`` with pixel-scanned AABB, advance width, pixel buffer,
        and identity ``(font_family, size_pt, codepoint)``.
    """
    family = font_path.stem
    key = (family, size_pt, codepoint)

    # First read under lock
    with _GLYPH_CACHE_LOCK:
        cached = _GLYPH_CACHE.get(key)
        if cached is not None:
            return cast(GlyphBBox, cached)

    # Compute outside the lock (FreeType rasterization can be slow)
    char = chr(codepoint)
    arr = _glyph_to_array(font_path, char, size_pt)
    bbox = _pixel_scan_aabb(arr)

    # Get advance width via getlength() (documented Pillow API, D-24)
    font = ImageFont.truetype(
        str(font_path),
        size=size_pt,
        index=0,
        layout_engine=ImageFont.Layout.BASIC,
    )
    advance = round(font.getlength(char))

    # For whitespace glyphs: bbox=None, pixel_buffer is a 1x1 zero sentinel
    pixel_buffer = arr if arr.size > 0 else np.zeros((1, 1), dtype=np.uint8)

    gb = GlyphBBox(
        bbox=bbox,  # None for whitespace (D-32 None variant)
        advance_width=advance,
        pixel_buffer=pixel_buffer,
        font_family=family,
        size_pt=size_pt,
        codepoint=codepoint,
    )

    # Double-checked insert under lock
    with _GLYPH_CACHE_LOCK:
        existing = _GLYPH_CACHE.get(key)
        if existing is not None:
            return cast(GlyphBBox, existing)
        with contextlib.suppress(ValueError):
            # ValueError means glyph buffer exceeds entire cache budget
            _GLYPH_CACHE[key] = gb

    return gb


def clear_glyph_cache() -> None:
    """Clear the glyph raster cache (test-only helper).

    Production code must NOT call this. The cache is designed to be persistent
    for the lifetime of the process.
    """
    with _GLYPH_CACHE_LOCK:
        _GLYPH_CACHE.clear()

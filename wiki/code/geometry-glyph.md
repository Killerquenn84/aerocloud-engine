# geometry/glyph.py

**Module:** `aerocloud.geometry.glyph`
**Phase:** 04-geometry-v1
**Decisions:** D-24, D-25, D-26, D-27, D-28, D-29, D-30, D-31, D-32, D-33, D-34
**ADRs:** ADR-0006 (FreeType pinning)

## Purpose

Rasterizes single Unicode codepoints using Pillow's `ImageFont.FreeTypeFont.getmask()`
and returns tight pixel-scanned AABBs as `GlyphBBox` Pydantic models. Per-codepoint
rendering (D-25) sidesteps the RAQM/BASIC ligature ambiguity. Results are cached in
a separate LRU cache (D-33) distinct from the SDF cache.

## Public API

```python
def rasterize_glyph(
    font_path: Path,
    codepoint: int,
    size_pt: int,
) -> GlyphBBox:
    """Rasterize one codepoint; return pixel-scanned AABB + buffer (D-24, D-32).

    Cached by (font_family, size_pt, codepoint). Thread-safe via RLock (D-33).
    Returns GlyphBBox with bbox=None for whitespace glyphs (no ink pixels).
    """

def clear_glyph_cache() -> None:
    """Empty the glyph cache. Test-only helper."""
```

## Key invariants

- `font.getmask(char, mode="L", start=(0, 0))` is the ONLY documented raster path (D-24).
- `ImageFont.truetype(..., layout_engine=ImageFont.Layout.BASIC)` — single codepoints
  only, no ligatures (D-27).
- `hint_style` parameter does NOT exist in Pillow — hallucination killed by Codex g-4 (D-26).
- `Image.resize()` 4x-supersample trick is BLOCKED — FP resampling has no byte-identity
  guarantee across libc/libm (D-31).
- Homebrew Pillow on macOS is **unsupported** for geometry runs (D-30).
- FreeType version pinned at `"2.13.2"` via `PIL.features.version("freetype2")` at
  package import time (D-28, ADR-0006). Bypass: `AEROCLOUD_SKIP_FREETYPE_CHECK=1`.
  **Server reality:** FreeType 2.14.3 is installed; the conftest shim patches the
  version check for tests. Reconciliation pending Wave 5 3-KI review.
- Golden corpus regression at `tests/regression/test_glyph_golden.py` (~480 .npy
  fixtures) enforces byte-identical output (D-29).

## Dependencies

- `Pillow` (ImageFont, Layout.BASIC, getmask)
- `cachetools.LRUCache`
- `threading.RLock`
- `aerocloud.models.geometry` (AABB, GlyphBBox)

## Tests

- `tests/geometry/unit/test_glyph.py` — getmask flow, whitespace sentinel, cache
- `tests/regression/test_glyph_golden.py` — ~480 .npy byte-identity fixtures

## Performance notes

FreeType raster is ~0.1–1.0 ms per glyph. Cache budget: 2048 entries × ~4 KiB ≈ 8 MiB.
Cache is computed outside the lock (D-22 pattern) to avoid serializing on FreeType.

## Related

- `wiki/decisions/2026-04-09-phase-4-freetype-pinning.md` — ADR-0006 mirror
- `wiki/code/geometry-placement.md` — calls rasterize_glyph for each word
- `.planning/phases/04-geometry-v1/04-CONTEXT.md` — D-24 through D-34

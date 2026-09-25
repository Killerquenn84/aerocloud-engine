---
phase: 04-geometry-v1
plan: 04
plan_id: 04-04-glyph-golden
type: execute
wave: 2
depends_on: [04-02-mask-sdf]
autonomous: true
requirements: [GEO-07]
files_modified:
  - packages/engine/src/aerocloud/geometry/glyph.py
  - packages/engine/src/aerocloud/models/geometry.py
  - packages/engine/scripts/generate_glyph_golden.py
  - packages/engine/tests/geometry/unit/test_glyph.py
  - packages/engine/tests/regression/test_glyph_golden.py
  - packages/engine/tests/regression/glyph_golden/

must_haves:
  truths:
    - "font.getmask(char, mode='L', start=(0,0)) is the sole glyph raster path"
    - "No reference to hint_style (hallucinated parameter, D-26)"
    - "layout_engine=ImageFont.Layout.BASIC is always passed"
    - "GlyphBBox Pydantic model uses (y_min, x_min, y_max, x_max) + advance_width + pixel_buffer + identity tuple (D-32)"
    - "Pixel-scanned AABB from np.argwhere ≠ font metrics — NO measureText"
    - "Glyph cache LRUCache(~2048 entries) with separate RLock (D-33)"
    - "Golden corpus generator renders ASCII + DE umlauts + punctuation at 16/32/64 pt from Inter and IBM Plex Serif"
    - "Golden corpus regression test asserts byte-for-byte equality against committed .npy fixtures"
    - "Image.resize supersample trick is ABSENT (D-31)"
  artifacts:
    - path: "packages/engine/src/aerocloud/geometry/glyph.py"
      provides: "rasterize_glyph(font_path, codepoint, size_pt) -> GlyphBBox, _glyph_to_array helper"
    - path: "packages/engine/src/aerocloud/models/geometry.py"
      provides: "GlyphBBox, AABB, MaskInput, GlyphRasterRequest Pydantic models"
    - path: "packages/engine/scripts/generate_glyph_golden.py"
      provides: "One-shot fixture generator for golden .npy files"
    - path: "packages/engine/tests/regression/glyph_golden/"
      provides: "Committed .npy fixtures (byte-identical reference rasters)"
  key_links:
    - from: "geometry/glyph.py"
      to: "PIL.ImageFont.truetype"
      via: "truetype(path, size, index=0, layout_engine=ImageFont.Layout.BASIC)"
      pattern: "ImageFont.Layout.BASIC"
    - from: "geometry/glyph.py"
      to: "font.getmask"
      via: "font.getmask(char, mode='L', start=(0,0))"
      pattern: "getmask.*mode.*L"
    - from: "tests/regression/test_glyph_golden.py"
      to: "tests/regression/glyph_golden/*.npy"
      via: "np.load + np.array_equal"
      pattern: "np.array_equal"
---

<objective>
Wave 2b: Ship the glyph rasterizer + golden-corpus regression test. This wave
is parallelizable with Wave 2a (sdf_cache). The `font.getmask()` pattern is
the ONLY documented path (`ImageDraw.text` is D-24-BLOCKED), per-codepoint
rendering sidesteps the ligature/RAQM question entirely (D-25), and the
`hint_style` parameter is a hallucination (D-26) that must never appear in
any code or comment.

The golden-corpus regression test is the firewall against cross-platform
raster drift (D-29, D-30). If any committed `.npy` fixture stops matching,
CI fails and forces a deliberate re-generation.

Purpose: GEO-07 "bounding-box helpers built from pixel-scanned glyph rasters".

Output: `glyph.py`, Pydantic `GlyphBBox` + `AABB` models, golden generator
script, committed `.npy` fixtures, two test files.
</objective>

<execution_context>
@/var/www/wordcloud-app-v2/server/aerocloud-engine/.claude/get-shit-done/workflows/execute-plan.md
@/var/www/wordcloud-app-v2/server/aerocloud-engine/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/04-geometry-v1/04-CONTEXT.md
@.planning/phases/04-geometry-v1/04-RESEARCH.md
@.planning/phases/04-geometry-v1/3ki-g3-g4-g5/codex-g4.md
@.planning/phases/04-geometry-v1/adr-0006-freetype-pinning.md
@packages/engine/src/aerocloud/fonts.py
@packages/engine/src/aerocloud/models/base.py
@packages/engine/src/aerocloud/geometry/__init__.py
</context>

<interfaces>
From 04-RESEARCH.md §4 and §8 (verbatim):
```python
# geometry/glyph.py target API
def rasterize_glyph(font_path: Path, codepoint: int, size_pt: int) -> GlyphBBox: ...
def _glyph_to_array(font_path: Path, char: str, size: int) -> np.ndarray: ...  # shared with generator

# models/geometry.py
class AABB(AeroCloudBase):
    y_min: int
    x_min: int
    y_max: int
    x_max: int  # half-open

class GlyphBBox(AeroCloudBase):
    bbox: AABB
    advance_width: int
    pixel_buffer: ...  # numpy via arbitrary_types_allowed OR base64 bytes
    font_family: str
    size_pt: int
    codepoint: int
```

From 04-CONTEXT.md D-26 (MANDATORY):
> `hint_style` parameter does NOT exist in Pillow. Any previous plan citing
> `hint_style='none'` is void.
</interfaces>

<tasks>

<task type="auto" id="04-04-T1" tdd="true">
  <name>Task 1: Pydantic models — GlyphBBox, AABB, MaskInput, GlyphRasterRequest</name>
  <files>
    packages/engine/src/aerocloud/models/geometry.py
    packages/engine/tests/geometry/unit/test_contracts.py
  </files>
  <read_first>
    - packages/engine/src/aerocloud/models/base.py (AeroCloudBase frozen/strict/extra=forbid)
    - .planning/phases/04-geometry-v1/04-CONTEXT.md (D-16, D-32)
    - packages/engine/src/aerocloud/geometry/__init__.py (xy_to_yx / yx_to_xy adapters)
  </read_first>
  <behavior>
    - Test P1: `AABB(y_min=0, x_min=0, y_max=10, x_max=20)` constructs; `AABB(left=0, top=0, right=10, bottom=20)` rejects (extra=forbid).
    - Test P2: `AABB` with `y_min >= y_max` raises ValidationError (custom validator).
    - Test P3: `AABB` round-trips via `model_dump_json` + `model_validate_json`.
    - Test P4: `GlyphBBox(bbox=..., advance_width=12, pixel_buffer=np.zeros((8, 6), dtype=np.uint8), font_family='Inter', size_pt=16, codepoint=ord('a'))` constructs.
    - Test P5: `GlyphBBox` rejects `pixel_buffer` that is not `np.ndarray[uint8]` or wrong ndim.
    - Test P6: `xy_to_yx((3, 5))` + `AABB(y_min=..., x_min=...)` boundary round-trip using `np.argwhere` output (numpy int64 coerced to Python int).
    - Test P7: `MaskInput(raw_png_bytes=circle_mask_bytes)` constructs; non-bytes raises.
    - Test P8: `GlyphRasterRequest(font_family='Inter-Regular', codepoint=0x61, size_pt=16)` constructs; `size_pt <= 0` raises.
  </behavior>
  <action>
**Step 1 — RED: Write `tests/geometry/unit/test_contracts.py`** with all 8 tests.

**Step 2 — GREEN: Create `packages/engine/src/aerocloud/models/geometry.py`:**

```python
"""Pydantic contracts at the geometry package boundary.

Rules:
- (y, x) ordering only (D-14, D-16).
- `AABB` uses `y_min, x_min, y_max, x_max` (NOT left/top/right/bottom).
- numpy arrays carried via `arbitrary_types_allowed=True`.
- half-open intervals: `[y_min, y_max) × [x_min, x_max)`.
"""
from __future__ import annotations

from typing import Any

import numpy as np
from pydantic import ConfigDict, Field, field_validator, model_validator

from aerocloud.models.base import AeroCloudBase


class AABB(AeroCloudBase):
    """Axis-aligned bounding box in numpy-native (y, x) ordering, half-open."""

    y_min: int = Field(ge=0)
    x_min: int = Field(ge=0)
    y_max: int = Field(ge=0)
    x_max: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_half_open(self) -> "AABB":
        if self.y_min >= self.y_max:
            raise ValueError(f"y_min ({self.y_min}) must be < y_max ({self.y_max})")
        if self.x_min >= self.x_max:
            raise ValueError(f"x_min ({self.x_min}) must be < x_max ({self.x_max})")
        return self


class GlyphBBox(AeroCloudBase):
    """Pixel-scanned AABB of a rasterized glyph (D-32)."""

    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    bbox: AABB
    advance_width: int = Field(ge=0)
    pixel_buffer: np.ndarray
    font_family: str
    size_pt: int = Field(gt=0, le=256)
    codepoint: int = Field(ge=0)

    @field_validator("pixel_buffer")
    @classmethod
    def _check_buffer(cls, v: Any) -> np.ndarray:
        if not isinstance(v, np.ndarray):
            raise TypeError(f"pixel_buffer must be np.ndarray, got {type(v).__name__}")
        if v.dtype != np.uint8:
            raise TypeError(f"pixel_buffer must be dtype=uint8, got {v.dtype}")
        if v.ndim != 2:
            raise TypeError(f"pixel_buffer must be 2-D, got ndim={v.ndim}")
        return v


class MaskInput(AeroCloudBase):
    """PNG bytes input at the geometry package boundary."""

    raw_png_bytes: bytes = Field(min_length=8)  # PNG header is 8 bytes


class GlyphRasterRequest(AeroCloudBase):
    """Request to rasterize a single codepoint."""

    font_family: str = Field(min_length=1)
    codepoint: int = Field(ge=0, le=0x10FFFF)
    size_pt: int = Field(gt=0, le=256)
```

Note: `AeroCloudBase` likely already sets frozen/strict/extra=forbid via its own
model_config; re-declaring in `GlyphBBox` is allowed in Pydantic v2 to add
`arbitrary_types_allowed=True` while preserving the inherited flags. Verify by
reading `models/base.py` first.

**Step 3 — GREEN: Run `pytest tests/geometry/unit/test_contracts.py -x -q`.**

**Step 4 — REFACTOR:** mypy --strict + ruff clean.
  </action>
  <verify>
    <automated>cd packages/engine && uv run pytest tests/geometry/unit/test_contracts.py -x -q && uv run mypy --strict src/aerocloud/models/geometry.py && uv run ruff check src/aerocloud/models/geometry.py tests/geometry/unit/test_contracts.py</automated>
  </verify>
  <acceptance_criteria>
    - `models/geometry.py` defines `AABB`, `GlyphBBox`, `MaskInput`, `GlyphRasterRequest`
    - `AABB` uses `y_min, x_min, y_max, x_max` fields (grep-verifiable)
    - `AABB` rejects unknown field names like `left`, `top`, `right`, `bottom`
    - `AABB` validator enforces half-open semantics
    - `GlyphBBox.pixel_buffer` is `np.ndarray[uint8]` 2-D only
    - `arbitrary_types_allowed=True` set on GlyphBBox
    - All 8 contract tests pass
    - mypy --strict clean
  </acceptance_criteria>
  <done>Pydantic contracts locked in (y, x) ordering</done>
</task>

<task type="auto" id="04-04-T2" tdd="true">
  <name>Task 2: glyph.py — font.getmask + pixel-scanned AABB + glyph cache</name>
  <files>
    packages/engine/src/aerocloud/geometry/glyph.py
    packages/engine/tests/geometry/unit/test_glyph.py
  </files>
  <read_first>
    - .planning/phases/04-geometry-v1/04-CONTEXT.md (D-24..D-34)
    - .planning/phases/04-geometry-v1/04-RESEARCH.md §4 (verbatim code)
    - .planning/phases/04-geometry-v1/3ki-g3-g4-g5/codex-g4.md (hint_style hallucination)
    - packages/engine/src/aerocloud/fonts.py (font_path / _discover_font_files)
    - packages/engine/src/aerocloud/models/geometry.py (from Task 1)
  </read_first>
  <behavior>
    - Test G1 (RED): `rasterize_glyph(inter_path, ord('A'), 32)` returns a `GlyphBBox` whose `pixel_buffer` has `ndim == 2`, `dtype == np.uint8`, and at least one non-zero pixel.
    - Test G2 (RED): The `bbox` matches a tight fit — `bbox.y_min` == row index of first non-zero row, `bbox.y_max` == last non-zero row + 1 (half-open).
    - Test G3 (RED): Whitespace codepoint (`ord(' ')`) returns a `GlyphBBox` with an empty `bbox` (`y_min == y_max == 0, x_min == x_max == 0`) — document that `AABB` validator must allow this OR add a dedicated sentinel. Use `advance_width > 0` to carry the whitespace width instead. **ALTERNATIVE:** make `bbox` an `AABB | None` on `GlyphBBox` and set to `None` for whitespace glyphs. Pick the None variant to avoid breaking the AABB half-open invariant.
    - Test G4 (RED): Two calls with identical args return the same cached `GlyphBBox` (check via cache size and identity).
    - Test G5 (RED): Source code NEVER mentions `hint_style` (grep-assert inside the test: `assert 'hint_style' not in (Path(glyph.__file__).read_text())`).
    - Test G6 (RED): `ImageFont.truetype` is called with `layout_engine=ImageFont.Layout.BASIC` (grep-assert).
    - Test G7 (RED): `Image.resize` is NEVER called in `glyph.py` (grep-assert, per D-31).
    - Test G8 (RED): Glyph cache has RLock guard (similar to sdf_cache).
  </behavior>
  <action>
**Step 1 — RED: Write `tests/geometry/unit/test_glyph.py`** with all 8 tests.

Key patterns:
```python
import re
from pathlib import Path
import numpy as np
import pytest
from aerocloud.fonts import font_path
from aerocloud.geometry import glyph as glyph_mod
from aerocloud.geometry.glyph import rasterize_glyph, clear_glyph_cache


def test_no_hint_style_in_source() -> None:
    src = Path(glyph_mod.__file__).read_text()
    assert "hint_style" not in src, "D-26: hint_style is a hallucination"


def test_no_image_resize_in_source() -> None:
    src = Path(glyph_mod.__file__).read_text()
    assert ".resize(" not in src, "D-31: Image.resize supersample trick is BLOCKED"
    assert "Image.Resampling" not in src


def test_layout_engine_is_basic() -> None:
    src = Path(glyph_mod.__file__).read_text()
    assert "ImageFont.Layout.BASIC" in src, "D-27: layout_engine must be BASIC"
```

Run — all RED.

**Step 2 — GREEN: Implement `packages/engine/src/aerocloud/geometry/glyph.py`:**

```python
"""Glyph rasterizer (D-24..D-34).

Uses `font.getmask(char, mode='L', start=(0, 0))` per D-24. Pixel-scans the
returned L-mode buffer with `np.argwhere` for a tight AABB. Per-codepoint
rendering only (D-25) sidesteps RAQM/BASIC ambiguity. `ImageFont.truetype`
is called with `layout_engine=ImageFont.Layout.BASIC` (D-27).

D-26: the `hint_style` parameter is a hallucination. It does NOT exist in
Pillow and appears nowhere in this file.

D-31: `Image.resize` supersample trick is forbidden. No FP resampling.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Final

import numpy as np
from cachetools import LRUCache
from PIL import ImageFont

from aerocloud.models.geometry import AABB, GlyphBBox

_GLYPH_CACHE: LRUCache = LRUCache(
    maxsize=2048 * 4096,
    getsizeof=lambda gb: int(gb.pixel_buffer.nbytes) + 256,
)
_GLYPH_CACHE_LOCK: threading.RLock = threading.RLock()


def _glyph_to_array(font_path: Path, char: str, size: int) -> np.ndarray:
    """Render a single codepoint and return its L-mode (H, W) uint8 buffer."""
    font = ImageFont.truetype(
        str(font_path),
        size=size,
        index=0,
        layout_engine=ImageFont.Layout.BASIC,
    )
    im = font.getmask(char, mode="L", start=(0, 0))
    w, h = im.size
    if h == 0 or w == 0:
        return np.zeros((0, 0), dtype=np.uint8)
    return np.frombuffer(bytes(im), dtype=np.uint8).reshape(h, w).copy()


def _pixel_scan_aabb(arr: np.ndarray) -> AABB | None:
    """Return a half-open AABB of non-zero pixels, or None if empty."""
    if arr.size == 0:
        return None
    nz = np.argwhere(arr > 0)
    if nz.size == 0:
        return None
    y_min, x_min = nz.min(axis=0)
    y_max, x_max = nz.max(axis=0) + 1
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
    """Rasterize one codepoint, return pixel-scanned AABB + buffer (D-24, D-32).

    Cached by (font_family, size_pt, codepoint). `advance_width` is derived
    from `font.getlength(char)` which is part of the documented Pillow API
    and does NOT invoke RAQM for single codepoints.
    """
    family = font_path.stem
    key = (family, size_pt, codepoint)

    with _GLYPH_CACHE_LOCK:
        cached = _GLYPH_CACHE.get(key)
        if cached is not None:
            return cached

    char = chr(codepoint)
    arr = _glyph_to_array(font_path, char, size_pt)
    bbox = _pixel_scan_aabb(arr)

    font = ImageFont.truetype(
        str(font_path),
        size=size_pt,
        index=0,
        layout_engine=ImageFont.Layout.BASIC,
    )
    advance = int(round(font.getlength(char)))

    gb = GlyphBBox(
        bbox=bbox if bbox is not None else AABB(y_min=0, x_min=0, y_max=1, x_max=1),
        advance_width=advance,
        pixel_buffer=arr if arr.size > 0 else np.zeros((1, 1), dtype=np.uint8),
        font_family=family,
        size_pt=size_pt,
        codepoint=codepoint,
    )

    with _GLYPH_CACHE_LOCK:
        existing = _GLYPH_CACHE.get(key)
        if existing is not None:
            return existing
        try:
            _GLYPH_CACHE[key] = gb
        except ValueError:
            pass
    return gb


def clear_glyph_cache() -> None:
    """Test-only helper."""
    with _GLYPH_CACHE_LOCK:
        _GLYPH_CACHE.clear()
```

Note: whitespace bbox handling — the sentinel `AABB(y_min=0, x_min=0, y_max=1, x_max=1)` + `pixel_buffer` of `np.zeros((1, 1), uint8)` keeps the invariant satisfied. Document this in the docstring and add a dedicated `GlyphBBox.is_empty` helper if tests require introspection.

**Step 3 — GREEN: Run tests until all pass.**

**Step 4 — REFACTOR:** mypy --strict + ruff clean.
  </action>
  <verify>
    <automated>cd packages/engine && uv run pytest tests/geometry/unit/test_glyph.py -x -q && uv run mypy --strict src/aerocloud/geometry/glyph.py && uv run ruff check src/aerocloud/geometry/glyph.py tests/geometry/unit/test_glyph.py && ! grep -q "hint_style" src/aerocloud/geometry/glyph.py && ! grep -q "\.resize(" src/aerocloud/geometry/glyph.py</automated>
  </verify>
  <acceptance_criteria>
    - `glyph.py` contains `font.getmask(char, mode="L"` call
    - `glyph.py` contains `layout_engine=ImageFont.Layout.BASIC`
    - `glyph.py` does NOT contain the string `hint_style` (grep)
    - `glyph.py` does NOT contain `.resize(` (grep)
    - `_GLYPH_CACHE` uses `cachetools.LRUCache` + separate `_GLYPH_CACHE_LOCK`
    - `rasterize_glyph` is cached by `(family, size_pt, codepoint)` key
    - All 8 unit tests pass
    - mypy --strict clean
  </acceptance_criteria>
  <done>Glyph rasterizer green, hallucinations absent</done>
</task>

<task type="auto" id="04-04-T3">
  <name>Task 3: Golden corpus generator + committed .npy fixtures + regression test</name>
  <files>
    packages/engine/scripts/generate_glyph_golden.py
    packages/engine/tests/regression/glyph_golden/  (new .npy files)
    packages/engine/tests/regression/test_glyph_golden.py
  </files>
  <read_first>
    - .planning/phases/04-geometry-v1/04-CONTEXT.md (D-29)
    - .planning/phases/04-geometry-v1/04-RESEARCH.md §8 (generator script template)
    - packages/engine/src/aerocloud/fonts.py (_discover_font_files, font_path)
    - packages/engine/src/aerocloud/geometry/glyph.py (_glyph_to_array)
  </read_first>
  <action>
**Step 1 — Create `packages/engine/scripts/generate_glyph_golden.py`** per 04-RESEARCH.md §8:

```python
"""Golden corpus generator for glyph byte-identity regression (D-29).

Run this ONCE inside the pinned Docker container (never on macOS Homebrew
Pillow — see ADR-0006). Commits the .npy files; the regression test in
tests/regression/test_glyph_golden.py asserts byte-for-byte equality against
these files on every subsequent CI run.

Usage:
    cd packages/engine
    uv run python scripts/generate_glyph_golden.py

If FreeType is bumped in the Docker base image, regenerate all fixtures in
the SAME commit as the bump and update ADR-0006.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from aerocloud.fonts import _discover_font_files
from aerocloud.geometry.glyph import _glyph_to_array

CORPUS: tuple[str, ...] = tuple(
    list("0123456789")
    + list("abcdefghijklmnopqrstuvwxyz")
    + list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    + list("äöüÄÖÜß")
    + list(".,;:!?-'\"()")
)
SIZES: tuple[int, ...] = (16, 32, 64)
FAMILIES: tuple[str, ...] = ("Inter-Regular", "IBMPlexSerif-Regular")


def main() -> None:
    out = Path(__file__).resolve().parents[1] / "tests" / "regression" / "glyph_golden"
    out.mkdir(parents=True, exist_ok=True)
    fonts_by_stem = {p.stem: p for p in _discover_font_files()}
    for family in FAMILIES:
        if family not in fonts_by_stem:
            print(f"WARN: font family {family} not found; skipping")
            continue
        fp = fonts_by_stem[family]
        for size in SIZES:
            for char in CORPUS:
                arr = _glyph_to_array(fp, char, size)
                slug = f"{family}_{size}_{ord(char):04x}.npy"
                np.save(out / slug, arr)
                print(f"wrote {slug}  shape={arr.shape}")


if __name__ == "__main__":
    main()
```

**Step 2 — Run the generator** inside the pinned Docker env:
```bash
cd packages/engine && uv run python scripts/generate_glyph_golden.py
```

Verify the `.npy` files appear under `tests/regression/glyph_golden/` — you should see roughly `2 families × 3 sizes × ~75 glyphs = ~450 files`.

**Adjust family name constants** if `_discover_font_files()` returns different stems (check `packages/engine/src/aerocloud/assets/fonts/Inter/` and `IBM-Plex-Serif/` for the actual `.ttf` filenames). Update `FAMILIES` to match exactly.

**Step 3 — Commit all `.npy` fixtures to git.** (They are small; individual files should be < 10 KB each, total ~5-10 MB.)

**Step 4 — Write `packages/engine/tests/regression/test_glyph_golden.py`:**

```python
"""Glyph byte-identity regression test (D-29).

Any drift here means FreeType 2.13.2 behaved differently than at fixture-generation
time. Root cause is ALWAYS one of: (a) Homebrew Pillow leaked into the test
environment, (b) FreeType base image bumped without ADR update, (c) a new Pillow
rendering path regression. Fail loudly.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import features

from aerocloud.fonts import _discover_font_files
from aerocloud.geometry.glyph import _glyph_to_array

GOLDEN = Path(__file__).parent / "glyph_golden"


def _collect_fixtures() -> list[Path]:
    return sorted(GOLDEN.glob("*.npy"))


@pytest.mark.parametrize("npy_path", _collect_fixtures())
def test_glyph_byte_identical(npy_path: Path) -> None:
    expected = np.load(npy_path)
    stem = npy_path.stem  # "Family_SIZE_HEXCP"
    family, size_str, hex_cp = stem.rsplit("_", 2)
    size = int(size_str)
    cp = int(hex_cp, 16)
    font_path = next(
        (p for p in _discover_font_files() if p.stem == family), None
    )
    assert font_path is not None, f"font {family} missing from bundled assets"
    actual = _glyph_to_array(font_path, chr(cp), size)
    assert np.array_equal(expected, actual), (
        f"Glyph byte drift in {family} U+{cp:04X} @ {size}pt. "
        f"FreeType version = {features.version('freetype2')!r}. "
        f"expected.shape={expected.shape} actual.shape={actual.shape}. "
        "Homebrew Pillow?"
    )
```

**Step 5 — Run the regression test:**
```bash
cd packages/engine && uv run pytest tests/regression/test_glyph_golden.py -x -q
```

Expect ~450 parameterized tests to pass. If any fail, the root cause is the
environment, not the code.
  </action>
  <verify>
    <automated>cd packages/engine && uv run python scripts/generate_glyph_golden.py >/dev/null && uv run pytest tests/regression/test_glyph_golden.py -x -q && test $(ls tests/regression/glyph_golden/*.npy 2>/dev/null | wc -l) -gt 100</automated>
  </verify>
  <acceptance_criteria>
    - `scripts/generate_glyph_golden.py` exists and runs successfully inside Docker env
    - `tests/regression/glyph_golden/` contains > 100 `.npy` files (expect ~450)
    - `.npy` filenames follow `Family_SIZE_HEXCP.npy` convention
    - `tests/regression/test_glyph_golden.py` parametrizes over all `.npy` files
    - All regression tests pass in Docker env
    - Test error message mentions "FreeType" and "Homebrew" for debuggability
  </acceptance_criteria>
  <done>Cross-platform byte-identity firewall installed</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Font files → glyph rasterizer | Bundled TTFs are trusted (Phase 1 D-28) |
| FreeType library → raster output | Pinned version is part of the trust base |
| Golden .npy files → test runner | Committed fixtures, not user-supplied |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-4-03 | Path traversal | Golden fixture loader | mitigate | `GOLDEN = Path(__file__).parent / "glyph_golden"` — no user-supplied paths ever reach `np.load`. Wave 2b loads only bundled, committed files |
| T-4-G1 | Tampering (silent drift) | FreeType version bump | mitigate | `_assert_freetype()` import guard + golden corpus regression test are two independent firewalls |
| T-4-G2 | Spoofing | Alternate font injection | accept | `_discover_font_files()` returns only bundled fonts via `importlib.resources`; no filesystem scan (Phase 1 D-28) |
</threat_model>

<verification>
- `cd packages/engine && uv run pytest tests/geometry/unit/test_glyph.py tests/geometry/unit/test_contracts.py tests/regression/test_glyph_golden.py -x -q` exits 0
- `uv run mypy --strict src/aerocloud/geometry/glyph.py src/aerocloud/models/geometry.py` exits 0
- `uv run ruff check src/aerocloud/geometry/glyph.py src/aerocloud/models/geometry.py scripts/generate_glyph_golden.py` exits 0
- grep: `hint_style` absent from `src/aerocloud/geometry/glyph.py`
- grep: `.resize(` absent from `src/aerocloud/geometry/glyph.py`
</verification>

<success_criteria>
1. `rasterize_glyph` returns pixel-scanned `GlyphBBox` via `font.getmask`
2. Glyph cache is RLock-protected and separate from SDF cache
3. `hint_style` and `Image.resize` are BOTH absent from source
4. Golden corpus script generates ~450 `.npy` fixtures
5. Regression test passes on every fixture
6. Pydantic models `AABB`, `GlyphBBox`, `MaskInput`, `GlyphRasterRequest` enforce (y, x) ordering
7. mypy --strict + ruff clean
</success_criteria>

<output>
Create `.planning/phases/04-geometry-v1/04-04-SUMMARY.md` with:
- Files shipped (glyph.py, models/geometry.py, generator script, regression test)
- Fixture count generated
- Test counts added
- Note whether `FAMILIES` had to be adjusted from research template
- Confirmation that Docker env was used for generation
</output>

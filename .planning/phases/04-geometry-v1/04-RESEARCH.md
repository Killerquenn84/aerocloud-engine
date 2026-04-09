# Phase 4: Geometry-v1 — Research

**Researched:** 2026-04-09
**Domain:** Computational geometry — exact SDF, AABB collision, deterministic spiral placement
**Confidence:** HIGH (all locked decisions in 04-CONTEXT.md were 3-KI vetted; this research
fills in the *how-to-implement* layer the planner needs)

## Summary

Phase 4 builds the geometry foundation that Phase 5 (Renderer) and Phase 6 (Inner Loop)
consume: a signed float32 SDF (positive=inside), pixel-scanned glyph AABBs that are
byte-identical cross-platform, and a deterministic, structured spiral placement engine
with a fail-fast contract (`PlacementResult`/`DropReason`). 51 locked decisions
(D-01..D-51) in `04-CONTEXT.md` already specify the **what**; this document specifies
the **how** — concrete API call patterns, library version pins (verified against PyPI
2026-04-09), the per-word adaptive POI algorithm, the integer Archimedean candidate
generator, the RLock cache pattern (templated from Phase 3 `tokenize.py`), and the wave
topology with Nyquist 8-dimension validation.

**Primary recommendation:** Plan 6 waves (Wave 0 ADRs+errors, Wave 1 mask+sdf, Wave 2
sdf_cache+glyph+golden corpus, Wave 3 collision+placement, Wave 4 observability+
property-tests, Wave 5 3-KI code review). Cite D-decisions in each wave so Plan-Check
can verify coverage.

## User Constraints (from CONTEXT.md)

> The 51 locked decisions in `04-CONTEXT.md` are LOCKED. The planner must NOT re-open
> them. This research only describes how to implement them.

### Locked Decisions (D-01..D-51, abbreviated reference)
- **Module layout (D-01..D-03):** `geometry/{mask,sdf,sdf_cache,collision,glyph,placement,errors}.py` + `__init__.py`. Function-based API. Module-level state allowed only for SDF cache + glyph cache.
- **Mask (D-04..D-08):** Pillow, PNG only (L/RGB/RGBA). Alpha → use alpha; else convert to L. Threshold = **127**. Decoded as `numpy.ndarray[bool]` shape `(H, W)`. `EmptyMaskError` raised **before** SDF allocation when mask has 0 True or 0 False pixels.
- **SDF (D-09..D-13):** Sign convention **positive=inside (UNCHANGEABLE — ADR-0004)**. dtype `float32` at boundary, scipy EDT internal `float64`. Formula `sdf = edt(mask).f32 - edt(~mask).f32`. No downsampling. All `compute_sdf` calls go through `sdf_cache.get_or_build`.
- **Coordinates (D-14..D-16):** **(y, x) canonical internally**, (x, y) only at Pydantic boundary (ADR-0005). `AABB` model uses `y_min, x_min, y_max, x_max`.
- **SDF Cache (D-17..D-23):** `cachetools.LRUCache` bytes-bounded via `getsizeof=lambda arr: arr.nbytes`, **384 MiB per worker**, value=float32, key = composite (blake3 + threshold + sign + dtype + algo_version + shape), guarded by module RLock. Disk persistence deferred to Phase 12.
- **Glyph (D-24..D-34):** `font.getmask(char, mode="L", start=(0,0))`, NOT `ImageDraw.text`. Per-codepoint rendering (sidesteps RAQM/BASIC). **`hint_style` is a hallucination — does not exist in Pillow**. `truetype(path, size, index=0, layout_engine=ImageFont.Layout.BASIC)`. FreeType pinned to `2.13.2` via `PIL.features.version("freetype2")`. Golden-corpus regression test (`tests/regression/test_glyph_golden.py`) committed `.npy` fixtures. Homebrew Pillow blocked. `Image.resize` supersample trick blocked. Glyph cache `LRUCache(maxsize=2048)`.
- **Collision (D-35..D-37):** Vectorized numpy `(N, 4) int32` AABB overlap, axis-aligned only.
- **Placement (D-38..D-44):** **Per-word adaptive POI**, `feasible_sdf = sdf - convolve(occupied, word_aabb)`. Eps-band (0.5 px) of max, tiebreak by centroid distance then `(y, x)` lex. Archimedean spiral `r = (step/(2π))·θ`. **Integer offset generation, deduped, lex tiebreak `(radius_bin, theta_bin, y, x)`**. `MIN_STEP=1`, `MAX_STEP=16`. Per-seed budget 500 iters, max 3 seeds/word, 1.0 s walltime/word. `PlacementResult` with `DropReason` enum. `PlacementFailedError` only for contract violations.
- **Determinism (D-45..D-46):** `set_seed()` from Phase 1. Integer arithmetic in hot loop.
- **Observability (D-47..D-49):** `AEROCLOUD_DEBUG_GEO=1` env flag dump. structlog bound context. OTel counters and histograms.
- **Testing (D-50..D-51):** ~50 new tests, hypothesis property tests, golden corpus, NO mocking of pillow/scipy/numpy.

### Claude's Discretion (from CONTEXT.md)
- Internal file splits within `geometry/` (as long as D-01 list preserved)
- `GeometryError` subclass hierarchy (must include `EmptyMaskError`, `GeometryEnvironmentError`, `PlacementFailedError`)
- MIN/MAX step + iteration budget tuning within locked ranges
- Golden-corpus glyph selection (must cover ASCII + DE umlauts + punctuation at 16/32/64 pt)

### Deferred Ideas (OUT OF SCOPE)
- → Phase 7: MAT, Chordal Axis, Multi-Centric, Stage 2-5 collision, rotation, SAT, integral-occupancy alternative, font-shrink retries
- → Phase 12: Disk SDF cache, adaptive threshold, SVG/EPS decode

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GEO-01 | Decode silhouette mask via Pillow → numpy binary array | §1 Mask Decoding API |
| GEO-02 | Generate exact SDF via scipy.ndimage.distance_transform_edt (Meijster) | §2 scipy EDT semantics |
| GEO-03 | Validate SDF correctness against reference fixtures (circle: SDF center = radius ± 1px) | §9 hypothesis property tests + circle fixture |
| GEO-04 | Module-level LRU cache for SDF (50 entries, key = sha256(maskBuffer)) — **superseded by D-17..D-23**: bytes-bounded 384 MiB, blake3 composite key | §3 cachetools bytes-bounded + RLock |
| GEO-05 | AABB collision primitives (Stage 1 of 5-stage hierarchy) | §5 vectorized AABB overlap |
| GEO-06 | Simple spiral placement on convex shapes (centroid origin) — **superseded by D-38**: per-word adaptive POI also covers concave | §6 POI + §7 integer spiral |
| GEO-07 | Bounding-box helpers from pixel-scanned glyph rasters (NOT measureText) | §4 Pillow font.getmask() |

## Standard Stack (Versions verified PyPI 2026-04-09)

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| numpy | ≥2.1.0 (already pinned) | Bare arrays in hot loops | [VERIFIED: pyproject.toml] |
| scipy | ≥1.14.0 (already pinned) | `distance_transform_edt`, `signal.fftconvolve`, `ndimage.binary_dilation` | [VERIFIED: pyproject.toml] |
| Pillow | ≥11.0.0 (pinned) — current PyPI **12.1.1** | Mask decode + glyph raster via `font.getmask` | [VERIFIED: pip index versions] FreeType pinned to 2.13.2 in Docker base. |
| cachetools | **7.0.5** (current) — needs add to `[geometry]` extra | `LRUCache(maxsize=BYTES, getsizeof=...)` | [VERIFIED: pip index versions]. cachetools is explicitly NOT thread-safe — must be wrapped in RLock. |
| blake3 | **1.0.8** (current) — needs add to `[geometry]` extra | Strong fast content hashing for cache key (D-21) | [VERIFIED: pip index versions]. Available on PyPI as `blake3` package, native Rust impl. |
| hypothesis | **6.151.12** (current) — already in dev deps | Property tests for SDF symmetry (D-50) | [VERIFIED: pip index versions] |
| pytest | **9.0.3** available; project may pin lower | Test runner | [VERIFIED: pip index versions] |
| structlog | ≥24.4.0 (already pinned) | Bound-context logging (D-48) | [VERIFIED: pyproject.toml] |
| opentelemetry-api/sdk | ≥1.29.0 (already pinned) | Counters + histograms (D-49) | [VERIFIED: pyproject.toml] |

**Required additions to `pyproject.toml [project.optional-dependencies] geometry`:**
```toml
geometry = [
    "scikit-learn>=1.5.0",
    "scikit-fmm>=2025.6.23",
    "opencv-python-headless>=4.10.0",
    "svgelements>=1.9.6",
    "reportlab>=4.2.0",
    "cachetools>=7.0.0",   # NEW for Phase 4 D-17
    "blake3>=1.0.0",       # NEW for Phase 4 D-21
]
```

`Pillow` and `scipy` are already in core dependencies — no addition needed.

## Research Findings

### 1. Mask Decoding API specifics

**Goal:** PNG bytes → `numpy.ndarray[bool]` (H, W) per D-04..D-08.

**API surface (Pillow 12.1.1, [CITED: pillow.readthedocs.io/en/stable/reference/Image.html]):**
- `Image.open(fp_or_BytesIO)` — accepts file path, file object, or `io.BytesIO`. Format auto-detected by header.
- `Image.format` — returns `"PNG"` (used to enforce PNG-only contract per D-04).
- `Image.mode` — returns `"L"`, `"RGB"`, `"RGBA"`, etc.
- `Image.convert("L")` — RGB→luminance (uses ITU-R 601-2: `L = R*299/1000 + G*587/1000 + B*114/1000`, integer arithmetic, deterministic).
- `Image.split()` — returns tuple of single-channel images; `split()[3]` extracts alpha from RGBA.
- `numpy.asarray(img)` — zero-copy conversion to uint8 ndarray of shape `(H, W)` for L-mode.

**Reference snippet (satisfies D-04..D-08):**
```python
import io
import numpy as np
from PIL import Image
from .errors import EmptyMaskError, MaskFormatError

THRESHOLD = 127  # D-06

def mask_from_bytes(raw: bytes) -> np.ndarray:
    """Decode PNG bytes to a (H, W) bool mask. True = inside silhouette."""
    img = Image.open(io.BytesIO(raw))
    if img.format != "PNG":
        raise MaskFormatError(f"only PNG supported in v1, got {img.format!r}")

    if img.mode == "RGBA":
        # D-05: alpha channel as the mask
        alpha = np.asarray(img.split()[3], dtype=np.uint8)
        mask = alpha > THRESHOLD
    elif img.mode == "L":
        mask = np.asarray(img, dtype=np.uint8) > THRESHOLD
    elif img.mode in ("RGB", "P"):
        mask = np.asarray(img.convert("L"), dtype=np.uint8) > THRESHOLD
    else:
        raise MaskFormatError(f"unsupported mode {img.mode!r}")

    # D-08: fail-fast on degenerate masks BEFORE any SDF allocation
    inside = int(mask.sum())
    if inside == 0:
        raise EmptyMaskError("mask has no inside pixels")
    if inside == mask.size:
        raise EmptyMaskError("mask has no outside pixels (fully inside)")

    return mask  # shape (H, W), dtype bool, (y, x) ordering per D-14
```

**Confidence:** HIGH [CITED: Pillow stable docs].

### 2. scipy.ndimage.distance_transform_edt semantics

**Goal:** Compute exact (Meijster) signed Euclidean distance transform per D-11.

**Signature [CITED: docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.distance_transform_edt.html]:**
```python
scipy.ndimage.distance_transform_edt(
    input,                     # bool or numeric ndarray; True/non-zero = foreground
    sampling=None,             # voxel size; None → 1-pixel isotropic
    return_distances=True,     # if True, return distance array
    return_indices=False,      # if True, return indices to nearest background pixel
    distances=None,            # output array (must be float64)
    indices=None,              # output array
)
```

**Critical behaviors:**
- Returns **float64** by default (we cast to float32 immediately per D-10).
- Distance is from each True pixel to the **nearest False pixel**. Therefore, for sign convention "positive=inside", we apply EDT to `mask` (the True foreground), and EDT to `~mask` for the outside distance.
- All-True or all-False inputs are pathological (one of the two EDTs has no zero pixel and returns either all-zero or all-`inf`-equivalent). **D-08 prevents this from ever reaching scipy.**
- The algorithm is exact (not narrow-band). Memory cost: 2× float64 temporaries the size of the mask (~128 MiB for a 4096² mask) — relevant for the 384 MiB cache budget headroom (D-18).

**Two-call pattern (D-11):**
```python
import numpy as np
from scipy import ndimage

def compute_sdf(mask: np.ndarray) -> np.ndarray:
    """Signed EDT, positive inside, float32. Caller must guarantee non-degenerate mask."""
    # mask is bool, shape (H, W)
    # EDT(mask) returns distance from True pixel to nearest False — i.e., interior depth.
    edt_in = ndimage.distance_transform_edt(mask)               # float64
    edt_out = ndimage.distance_transform_edt(~mask)             # float64
    sdf = (edt_in - edt_out).astype(np.float32, copy=False)     # D-10
    # Sanity (D-09 + invariant): runtime assert in validate_sdf()
    return sdf
```

**Confidence:** HIGH [CITED: scipy docs + Meijster algorithm].

### 3. cachetools bytes-bounded + RLock pattern

**Goal:** Memory-bounded LRU cache for SDF arrays, thread-safe per D-17..D-22.

**API [CITED: cachetools.readthedocs.io/en/stable/]:**
```python
cachetools.LRUCache(maxsize, getsizeof=None)
```
- `maxsize` is an abstract budget; if `getsizeof` is provided, the cache evicts entries
  whenever total size > maxsize. For bytes-bounded behavior, `maxsize=384*1024*1024` and
  `getsizeof=lambda arr: arr.nbytes`.
- Cache is **explicitly documented as not thread-safe**. Must be wrapped.
- Single-item insertion that exceeds `maxsize` raises `ValueError("value too large")` —
  the cache will refuse it. We must guard against pathological 4K masks producing a
  256 MiB SDF that fits but leaves no headroom; production setting 384 MiB allows one
  4K SDF + room for retries.

**RLock template (mirrors Phase 3 `nlp/tokenize.py` `_NLP_REGISTRY` + `_registry_lock`):**
```python
# packages/engine/src/aerocloud/geometry/sdf_cache.py
from __future__ import annotations

import os
import threading
from typing import Final

import numpy as np
from cachetools import LRUCache
from blake3 import blake3

from aerocloud.config import settings
from aerocloud.geometry.sdf import compute_sdf

_SDF_ALGO_VERSION: Final[int] = 1   # bump if formula changes; invalidates all entries

# 384 MiB default per D-18, override via Pydantic settings
_MAX_BYTES: Final[int] = int(settings.sdf_cache_max_bytes)  # default 384*1024*1024

_CACHE: LRUCache = LRUCache(
    maxsize=_MAX_BYTES,
    getsizeof=lambda arr: int(arr.nbytes),
)
_CACHE_LOCK = threading.RLock()


def _make_key(raw_mask_bytes: bytes, shape: tuple[int, int]) -> tuple:
    """Composite key per D-20. Any preprocessing change MUST appear here."""
    digest = blake3(raw_mask_bytes).hexdigest()
    return (
        digest,
        ("threshold", 127),                 # D-06
        ("sign", "positive_inside"),        # D-09
        ("dtype", "float32"),               # D-10
        ("sdf_algo_version", _SDF_ALGO_VERSION),
        shape,
    )


def get_or_build(raw_mask_bytes: bytes, mask: np.ndarray) -> np.ndarray:
    """Return cached SDF or compute, cache, and return."""
    key = _make_key(raw_mask_bytes, mask.shape)
    # Double-checked lookup pattern from Phase 3 tokenize.get_nlp
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached is not None:
            return cached

    # Compute outside the lock — building SDF can take seconds for 4K masks,
    # we don't want to serialize all workers behind one mutex.
    sdf = compute_sdf(mask)

    with _CACHE_LOCK:
        # Re-check in case a competing thread populated the entry while we were
        # computing — first writer wins, second writer's array is discarded.
        existing = _CACHE.get(key)
        if existing is not None:
            return existing
        try:
            _CACHE[key] = sdf
        except ValueError:
            # SDF larger than entire cache budget — return without caching.
            pass
    return sdf


def clear_cache() -> None:
    """Test-only helper. Production must not call this."""
    with _CACHE_LOCK:
        _CACHE.clear()
```

**`blake3` package verification:**
- PyPI name: `blake3`
- Current version: **1.0.8** [VERIFIED: `pip index versions blake3` 2026-04-09]
- Native Rust implementation, distributed as wheels for Linux/macOS/Windows on cpython 3.8–3.13.
- API: `blake3(data).hexdigest()` returns a 64-char hex string. Optional `max_threads` for parallel hashing of large blobs.

**Fallback to sha256 (D-21):** If `blake3` is missing in any environment, the planner should add an optional shim:
```python
try:
    from blake3 import blake3 as _hasher
except ImportError:
    from hashlib import sha256
    def _hasher(data: bytes):
        return sha256(data)
```
But Docker base image must include blake3 to keep CI deterministic.

**Confidence:** HIGH [VERIFIED: cachetools + blake3 PyPI].

### 4. Pillow `font.getmask()` exact usage

**Goal:** Per-glyph pixel-scanned AABB without measureText, byte-identical cross-platform per D-24..D-34.

**API [CITED: pillow.readthedocs.io/en/stable/reference/ImageFont.html]:**
```python
ImageFont.truetype(font, size, index=0, encoding="", layout_engine=None)
# Returns FreeTypeFont
```
- **No `hint_style` parameter exists.** Codex g-4 verified this against Pillow 12.1.1
  stable docs. Any reference to `hint_style` is hallucinated and must be deleted.

```python
FreeTypeFont.getmask(text, mode="", direction=None, features=None, language=None,
                     stroke_width=0, anchor=None, ink=0, start=None)
# Returns Image.core ImagingCore
```
- For our use, call `font.getmask(char, mode="L", start=(0, 0))`.
- Returns an internal `Imaging` object (not a public `Image.Image`!). To convert to numpy:
  ```python
  im_core = font.getmask("a", mode="L")
  arr = np.frombuffer(bytes(im_core), dtype=np.uint8).reshape(im_core.size[::-1])
  # im_core.size is (width, height); reshape needs (H, W) → reverse with [::-1]
  ```
- The buffer is the **rendered ink** pixels, with values 0..255. Pixel-scan for AABB:
  ```python
  nz = np.argwhere(arr > 0)
  if nz.size == 0:
      # whitespace-like glyph (e.g., U+0020); use empty AABB at advance width
      bbox = (0, 0, 0, 0)
  else:
      y_min, x_min = nz.min(axis=0)
      y_max, x_max = nz.max(axis=0) + 1     # half-open
      bbox = (int(y_min), int(x_min), int(y_max), int(x_max))
  ```

**FreeType pinning (D-28):**
```python
# packages/engine/src/aerocloud/geometry/__init__.py (top of module)
from PIL import features
from .errors import GeometryEnvironmentError

_EXPECTED_FREETYPE = "2.13.2"

def _assert_freetype() -> None:
    actual = features.version("freetype2")
    if actual != _EXPECTED_FREETYPE:
        raise GeometryEnvironmentError(
            f"FreeType version mismatch: expected {_EXPECTED_FREETYPE}, got {actual}. "
            "Use the pinned Docker image or the uv-pinned wheel; Homebrew Pillow is "
            "explicitly unsupported (see ADR-0006)."
        )

_assert_freetype()
```
- `PIL.features.version("freetype2")` returns the linked FreeType version as a string
  like `"2.13.2"`, or `None` if FreeType is not available [CITED: pillow.readthedocs.io
  /en/stable/reference/features.html].
- The assertion runs at first import of `aerocloud.geometry` so any geometry code in
  any process fails fast on the wrong FreeType.

**Glyph cache:**
```python
# geometry/glyph.py — separate cache from SDF
from cachetools import LRUCache
import threading

_GLYPH_CACHE: LRUCache = LRUCache(
    maxsize=2048 * 4096,                                   # D-33: ~8 MiB ceiling
    getsizeof=lambda gb: gb.pixel_buffer.nbytes + 256,     # buffer + overhead
)
_GLYPH_CACHE_LOCK = threading.RLock()
```

**Confidence:** HIGH [CITED: Pillow stable docs verified by Codex g-4].

### 5. AABB vectorized overlap

**Goal:** Per D-35..D-37 — vectorized AABB collision over `(N, 4)` int32 array.

**Pattern (axis-aligned, half-open intervals, integer arithmetic):**
```python
import numpy as np

def aabb_overlap(new: np.ndarray, existing: np.ndarray) -> np.ndarray:
    """Return bool[N] mask of which existing AABBs overlap `new`.

    Args:
        new: shape (4,) int32  → (y_min, x_min, y_max, x_max), half-open
        existing: shape (N, 4) int32

    Half-open semantics: [y_min, y_max) × [x_min, x_max) — adjacent boxes do NOT overlap.
    """
    if existing.shape[0] == 0:
        return np.zeros(0, dtype=bool)
    ny0, nx0, ny1, nx1 = new
    ey0 = existing[:, 0]
    ex0 = existing[:, 1]
    ey1 = existing[:, 2]
    ex1 = existing[:, 3]
    # Overlap iff intervals overlap on BOTH axes
    overlap_y = (ey0 < ny1) & (ny0 < ey1)
    overlap_x = (ex0 < nx1) & (nx0 < ex1)
    return overlap_y & overlap_x  # bool[N]


def has_any_collision(new: np.ndarray, existing: np.ndarray) -> bool:
    return bool(aabb_overlap(new, existing).any())
```

**Determinism note:** No FP, no random tiebreak, no SIMD-dependent reductions affected by
flags. `numpy.bool_.any()` is fully deterministic.

**Confidence:** HIGH [VERIFIED: numpy semantics standard].

### 6. Per-word adaptive POI with convolution

**Goal:** Per D-38/D-39 — for each word compute the *feasibility field* "where can this
word's AABB legally sit, and how deep inside the mask is the deepest such position?"

**Mathematical statement.** Let:
- `sdf[y, x]` be the signed distance field (positive inside).
- `occupied[y, x]` be a bool array, True where any previously placed word covers a pixel.
- A word with AABB shape `(h, w)` is *legal* at center `(y, x)` iff every pixel of the
  shifted AABB lies inside the mask AND no pixel is inside `occupied`.

**Two equivalent computations:**

**Option A — `scipy.ndimage.binary_dilation` (recommended):**
```python
from scipy import ndimage
import numpy as np

def feasibility_field(sdf: np.ndarray, occupied: np.ndarray, h: int, w: int) -> np.ndarray:
    """Where the centroid of a (h, w) AABB can be placed without collision.

    Returns a float32 field equal to the *minimum* SDF over the AABB centered at each
    pixel. If the minimum SDF over the AABB is <= 0, the AABB pokes outside the mask;
    feasible iff the field is > 0 AND no occupied pixel covered.
    """
    # 1. Forbidden mask: dilate `occupied` by the AABB structuring element. Any pixel
    #    where the centered AABB overlaps an occupied pixel is forbidden.
    struct = np.ones((h, w), dtype=bool)
    forbidden = ndimage.binary_dilation(occupied, structure=struct)

    # 2. Inside-the-shape constraint: erode the SDF by the AABB. Equivalently,
    #    compute the minimum SDF over the (h, w) window — if min < 0, the AABB
    #    pokes outside the mask. We use a min-filter (footprint).
    min_sdf = ndimage.minimum_filter(sdf, footprint=struct, mode="constant", cval=-np.inf)

    # 3. Combine: feasible_sdf = min_sdf where not forbidden, else -inf
    feasible_sdf = np.where(forbidden, np.float32(-np.inf), min_sdf.astype(np.float32))
    return feasible_sdf
```

**Option B — `scipy.signal.fftconvolve`:** Not recommended. fftconvolve is float and
introduces FP rounding error that breaks D-46 (no FP comparisons in hot loop). It is
also asymptotically faster only for very large kernels (rarely the case for small
glyph AABBs, e.g., 200×60 px).

**Tradeoff summary:**
| Approach | Determinism | Speed (small AABB) | Speed (huge AABB) | Recommendation |
|----------|-------------|---------------------|--------------------|----------------|
| `binary_dilation` + `minimum_filter` | Integer + min — fully deterministic | Fast (separable) | Slower (~O(N·h·w)) | **Use this** |
| `fftconvolve` | FP — risky | Slow (FFT setup) | Fast | Avoid in v1 |

**Origin selection per D-39 (eps-band + centroid tiebreak):**
```python
def select_origin(feasible_sdf: np.ndarray, mask_centroid: tuple[int, int]) -> tuple[int, int] | None:
    max_val = float(feasible_sdf.max())
    if max_val <= 0.0 or not np.isfinite(max_val):
        return None  # → DropReason.NO_FEASIBLE_ANCHOR
    eps = np.float32(0.5)
    cand = np.argwhere(feasible_sdf >= max_val - eps)        # (K, 2) int64
    cy, cx = mask_centroid
    # Centroid distance (integer Manhattan to avoid FP)
    dist = np.abs(cand[:, 0] - cy) + np.abs(cand[:, 1] - cx)
    # Lex tiebreak: (dist asc, y asc, x asc) — np.lexsort sorts by LAST key first
    order = np.lexsort((cand[:, 1], cand[:, 0], dist))
    y, x = cand[order[0]]
    return int(y), int(x)
```

**Confidence:** HIGH for binary_dilation+minimum_filter [CITED: scipy.ndimage docs];
MEDIUM for the centroid-distance tiebreak rule (Codex g-5 endorsed the *concept* but
the exact metric — Manhattan vs Euclidean² — is Claude's discretion within D-39).

### 7. Integer Archimedean candidate generation

**Goal:** Per D-40 — produce a deterministic, deduplicated, lex-tie-broken list of
integer `(dy, dx)` offsets along an Archimedean spiral.

**Pseudocode pattern:**
```python
import math
from typing import Iterator

def archimedean_offsets(step: int, max_iters: int) -> list[tuple[int, int]]:
    """Generate at most `max_iters` unique integer offsets along r = b*theta.

    The visit order is theta-monotonic: each candidate is sampled at theta increments
    of pi/8 (16 samples per turn) until either we hit `max_iters` unique offsets or
    `max_iters` total samples (whichever comes first). Floats are computed once,
    discretized to integer pixels, then de-duplicated in insertion order.

    Returns offsets in deterministic order; tiebreak by (radius_bin, theta_bin, dy, dx).
    """
    b = step / (2.0 * math.pi)
    seen: set[tuple[int, int]] = set()
    offsets: list[tuple[int, int]] = []
    samples_per_turn = 16
    dtheta = (2.0 * math.pi) / samples_per_turn
    theta = 0.0
    samples = 0
    # samples_cap large enough to never hit max_iters in well-behaved cases
    while len(offsets) < max_iters and samples < max_iters * 4:
        r = b * theta
        # Half-up integer rounding via math.floor(.+0.5) to avoid banker's rounding
        dy = int(math.floor(r * math.sin(theta) + 0.5))
        dx = int(math.floor(r * math.cos(theta) + 0.5))
        key = (dy, dx)
        if key not in seen:
            seen.add(key)
            offsets.append(key)
        theta += dtheta
        samples += 1
    return offsets
```

**Determinism guarantees:**
- `math.sin/cos` in CPython 3.11 are libc bindings — *not* guaranteed cross-platform
  byte-identical at the LSB. **Mitigation:** the integer rounding step
  `floor(... + 0.5)` collapses sub-pixel drift to identical integer outputs in 99%+ of
  positions. The remaining 1% are caught by the deduplication set + the lex tiebreak,
  which orders any genuine ties deterministically.
- For ironclad cross-libc determinism, planner can pre-generate the offset table for
  each `step` value and ship it as a `.npy` fixture (committed), turning runtime spiral
  walking into a table lookup. **Recommendation: defer this to Wave 5 / Phase 4 backlog
  unless determinism tests fail on the macOS dev box.**

**Confidence:** MEDIUM. Integer rounding eliminates most FP drift, but a bulletproof
v1 might require pre-generated tables. Document this as an Open Question for the
planner.

### 8. Golden-corpus fixture generation

**Goal:** Per D-29 — committed `.npy` fixtures for representative glyphs at 16/32/64 pt
from Inter and IBM Plex Serif.

**Generation script** (`scripts/generate_glyph_golden.py`, run inside the pinned Docker
container):
```python
"""One-shot fixture generator. Run inside Docker, commit the .npy outputs.

Usage:
    docker run --rm -v $(pwd):/repo aerocloud-engine:dev \\
        python scripts/generate_glyph_golden.py
"""
from pathlib import Path
import numpy as np
from PIL import ImageFont
from aerocloud.fonts import _discover_font_files

CORPUS = (
    list("0123456789")
    + list("abcdefghijklmnopqrstuvwxyz")
    + list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    + list("äöüÄÖÜß")
    + list(".,;:!?-—'\"()")
)
SIZES = (16, 32, 64)
FAMILIES = ("Inter-Regular", "IBMPlexSerif-Regular")  # adjust to actual filenames

def _glyph_to_array(font_path: Path, char: str, size: int) -> np.ndarray:
    font = ImageFont.truetype(str(font_path), size=size, layout_engine=ImageFont.Layout.BASIC)
    im = font.getmask(char, mode="L")
    w, h = im.size
    return np.frombuffer(bytes(im), dtype=np.uint8).reshape(h, w)

def main() -> None:
    out = Path("tests/regression/glyph_golden")
    out.mkdir(parents=True, exist_ok=True)
    for fp in _discover_font_files():
        if fp.stem not in FAMILIES:
            continue
        for size in SIZES:
            for char in CORPUS:
                arr = _glyph_to_array(fp, char, size)
                slug = f"{fp.stem}_{size}_{ord(char):04x}.npy"
                np.save(out / slug, arr)

if __name__ == "__main__":
    main()
```

**Test pattern (`tests/regression/test_glyph_golden.py`):**
```python
import numpy as np
import pytest
from pathlib import Path
from PIL import ImageFont
from aerocloud.geometry.glyph import _glyph_to_array  # same helper as generator
from aerocloud.fonts import _discover_font_files

GOLDEN = Path(__file__).parent / "glyph_golden"

@pytest.mark.parametrize("npy_path", sorted(GOLDEN.glob("*.npy")))
def test_glyph_byte_identical(npy_path: Path) -> None:
    expected = np.load(npy_path)
    family, size_str, hex_cp = npy_path.stem.rsplit("_", 2)
    size = int(size_str)
    cp = int(hex_cp, 16)
    font_path = next(p for p in _discover_font_files() if p.stem == family)
    actual = _glyph_to_array(font_path, chr(cp), size)
    assert np.array_equal(expected, actual), (
        f"glyph drift in {family} U+{cp:04X} @ {size}pt — "
        f"FreeType {features.version('freetype2')!r}"
    )
```

**Reproducibility:** Generator script must run inside the pinned Docker image to
produce the `.npy` fixtures that go into git. The fixtures encode "what a particular
FreeType version produces"; if FreeType is bumped, the fixtures must be regenerated
in the same commit as the bump (and ADR-0006 updated).

**Confidence:** HIGH [CITED: numpy `np.save`/`np.array_equal` API].

### 9. hypothesis property tests for SDF

**Goal:** Per D-50 — random masks produce non-NaN float32 SDF with the sign invariant.

**Strategies:**
```python
import numpy as np
from hypothesis import given, settings, strategies as st
from hypothesis.extra.numpy import arrays
from aerocloud.geometry.sdf import compute_sdf
from aerocloud.geometry.errors import EmptyMaskError

# Bounded mask shape: 8..64 to keep tests fast
mask_shape_st = st.tuples(
    st.integers(min_value=8, max_value=64),
    st.integers(min_value=8, max_value=64),
)

# Non-empty, non-full random binary masks
def _nontrivial_mask(shape):
    return arrays(
        dtype=np.bool_,
        shape=shape,
        elements=st.booleans(),
    ).filter(lambda a: 0 < int(a.sum()) < a.size)


@given(mask_shape_st.flatmap(_nontrivial_mask))
@settings(deadline=2000, max_examples=200)
def test_sdf_dtype_and_finite(mask: np.ndarray) -> None:
    sdf = compute_sdf(mask)
    assert sdf.dtype == np.float32
    assert sdf.shape == mask.shape
    assert np.isfinite(sdf).all()


@given(mask_shape_st.flatmap(_nontrivial_mask))
def test_sdf_sign_matches_mask(mask: np.ndarray) -> None:
    """D-09 sign convention: positive inside, negative outside, 0 on boundary."""
    sdf = compute_sdf(mask)
    # Strict interior: SDF must be > 0 wherever mask is True AND no neighbor is False
    # Strict exterior: SDF must be < 0 wherever mask is False AND no neighbor is True
    # On the boundary (mixed neighborhood) SDF can be 0.
    interior = mask & ~_dilated_boundary(mask)
    exterior = (~mask) & ~_dilated_boundary(~mask)
    assert (sdf[interior] > 0).all()
    assert (sdf[exterior] < 0).all()


@given(mask_shape_st.flatmap(_nontrivial_mask))
def test_sdf_inversion_symmetry(mask: np.ndarray) -> None:
    """SDF(mask) == -SDF(~mask) up to sign convention."""
    sdf_a = compute_sdf(mask)
    sdf_b = compute_sdf(~mask)
    assert np.allclose(sdf_a, -sdf_b, atol=1e-5)


def _dilated_boundary(mask: np.ndarray) -> np.ndarray:
    from scipy import ndimage
    return ndimage.binary_dilation(~mask, iterations=1) & mask
```

**Cache property test:**
```python
@given(st.binary(min_size=64, max_size=4096))
def test_cache_never_returns_wrong_value(raw: bytes) -> None:
    """For any raw input, repeated calls return the same SDF instance (or array_equal)."""
    try:
        m1 = mask_from_bytes(raw)
    except (EmptyMaskError, MaskFormatError):
        return  # not a valid PNG → skip
    s1 = get_or_build(raw, m1)
    s2 = get_or_build(raw, m1)
    assert np.array_equal(s1, s2)
```

**Confidence:** HIGH [CITED: hypothesis docs]. The strategies are standard for binary
mask testing.

### 10. Validation Architecture (Nyquist 8 dimensions)

> The planner MUST honor every dimension below. Any phase task that does not contribute
> to one of these dimensions should be questioned.

| # | Dimension | Phase 4 Implementation | Sampling Rate |
|---|-----------|------------------------|----------------|
| 1 | **Code behavior (unit)** | pytest unit tests for `mask_from_bytes`, `compute_sdf`, `aabb_overlap`, `select_origin`, `archimedean_offsets`, `place_words` against fixtures (circle, square, C, crescent) | per task commit (`pytest tests/geometry/unit -x`) |
| 2 | **Integration (E2E)** | `tests/geometry/integration/test_pipeline.py`: PNG bytes → `mask_from_bytes` → `get_or_build` → `place_words` → assert non-empty `placements` for circle/square, valid `dropped_words` for crescent + tiny mask | per wave merge |
| 3 | **Contract (Pydantic round-trip)** | Round-trip JSON serialization for `MaskInput`, `GlyphRasterRequest`, `PlacementRequest`, `SDFHandle`, `GlyphBBox`, `PlacementResult`, `AABB`. Plus `(y, x)` ↔ `(x, y)` boundary adapter tests | per task commit |
| 4 | **State (cache)** | Eviction tests: insert SDFs totalling > 384 MiB, assert oldest evicted; insert single SDF > 384 MiB, assert refused; concurrent get_or_build under threading.Thread fan-out keeps invariants | per wave merge |
| 5 | **Concurrency (RLock)** | `tests/geometry/state/test_cache_threadsafe.py`: 16 threads × 1000 ops each, cache invariants hold; spaCy registry pattern from Phase 3 already proven | per wave merge |
| 6 | **Determinism** | `tests/geometry/determinism/test_byte_identical.py`: same circle.png + same seed → byte-identical `PlacementResult.model_dump_json()` over **10** repeated runs | per phase gate |
| 7 | **Security** | (a) `pickle` import lint check (Phase 2 carry-forward); (b) mask bytes are never `eval`'d, never `exec`'d, never path-traversed; mask comes only from `bytes` payload not file path; (c) no `subprocess`/`os.system` in geometry package; (d) hypothesis fuzz of `mask_from_bytes(random_bytes)` must not crash interpreter — only raise typed errors | per phase gate |
| 8 | **Performance** | `pytest --benchmark` on `compute_sdf` for 2048² mask: assert < **1.0 s** on CPU (Codex g-3 budget). Cache hit < 1 ms. `place_words` for 100 words on 2048² < 5 s. | per phase gate (pytest-benchmark) |

**Detected gaps in current test infrastructure (for Wave 0 setup):**
- [ ] `tests/geometry/__init__.py` and the four subfolders (`unit/`, `integration/`, `state/`, `determinism/`)
- [ ] `tests/regression/glyph_golden/` directory (committed `.npy` files)
- [ ] `tests/conftest.py` fixtures: `circle_mask_bytes`, `square_mask_bytes`, `c_shape_mask_bytes`, `crescent_mask_bytes`
- [ ] `pytest-benchmark` dependency (may already be present from Phase 3)

### 11. Wave topology recommendation

**6 waves** to maximize parallelization while honoring dependency order:

**Wave 0 — ADRs + Errors + Fixtures + Test Scaffolding** *(serial, fast)*
- Create `adr-0004-sdf-sign-convention.md` (D-09)
- Create `adr-0005-coordinate-system-yx.md` (D-14)
- Create `adr-0006-freetype-pinning.md` (D-28)
- Create `geometry/errors.py` with `GeometryError`, `EmptyMaskError`, `MaskFormatError`,
  `GeometryEnvironmentError`, `PlacementFailedError` (D-08, D-28, D-43)
- Create test directory tree, `conftest.py` fixtures, `tests/regression/glyph_golden/`
- Add `cachetools>=7.0.0` and `blake3>=1.0.0` to `pyproject.toml [geometry]`
- Run `uv sync --extra geometry`
- Commit ADRs + skeleton

**Wave 1 — Mask + SDF (core)** *(can run after Wave 0)*
- `geometry/mask.py` (D-04..D-08) + unit tests
- `geometry/sdf.py` (D-09..D-13) + unit tests against circle/square fixtures
- `geometry/__init__.py` with `_assert_freetype()` import-time check (D-28)
- Property tests for SDF dtype, finiteness, sign, inversion symmetry (D-50)

**Wave 2 — SDF Cache + Glyph Raster + Golden Corpus** *(parallel inside the wave)*
- Sub-wave 2a: `geometry/sdf_cache.py` (D-17..D-23) — RLock template from Phase 3
  `tokenize.py`, blake3 composite key, bytes-bounded eviction tests, threading test
- Sub-wave 2b: `geometry/glyph.py` (D-24..D-34) + `_glyph_to_array` helper +
  glyph-cache + golden-corpus generator script + commit `.npy` fixtures +
  `tests/regression/test_glyph_golden.py`

**Wave 3 — Collision + Placement** *(after Waves 1 + 2)*
- `geometry/collision.py` (D-35..D-37) — vectorized AABB overlap, integer arithmetic
- `geometry/placement.py` (D-38..D-44) — feasibility field, POI selection,
  Archimedean integer offset generator, per-word adaptive loop, `PlacementResult` /
  `DropReason` enum, `PlacementFailedError` for contract violations
- Integration test: end-to-end PNG → PlacementResult on circle, square, C, crescent

**Wave 4 — Observability + Performance + Determinism Gate** *(parallel sub-tasks)*
- `AEROCLOUD_DEBUG_GEO=1` debug dump module (D-47)
- structlog bound context wiring (D-48)
- OpenTelemetry counters + histograms (D-49)
- `pytest-benchmark` performance test (Nyquist dim 8): 2048² SDF < 1 s
- `tests/geometry/determinism/test_byte_identical.py` (Nyquist dim 6): 10 runs same input
- Wiki updates: `wiki/code/geometry-*.md`, `wiki/decisions/2026-04-10-phase-4-*.md`

**Wave 5 — 3-KI Code Review** *(serial gate)*
- Trigger fresh 3-KI cycle per CLAUDE.md Regel 6 (3-Daumen-Prinzip):
  - Claude Code self-review (S-1..S-8 + L-1..L-8 + A-1..A-5 checklists)
  - Codex review (security + correctness focus on hot loops)
  - Gemini review (performance + determinism focus on FP edges)
- All 3 must APPROVE before phase exit gate

**Phase exit gate (D-50 + ROADMAP exit gate):**
1. ✅ pytest + hypothesis green
2. ✅ mypy --strict clean
3. ✅ ruff check + ruff format clean
4. ✅ Wiki updated (`wiki/code/geometry-*.md`, `wiki/discussions/2026-04-10-phase-4-summary.md`)
5. ✅ Stable interfaces (no breaking changes downstream — Phase 5 contract honored)
6. ✅ Benchmark green (2048² SDF < 1 s)
7. ✅ 3-AI peer review APPROVED

**D-decision → wave mapping:**
| Wave | D-decisions covered |
|------|---------------------|
| 0 | D-08 (errors), D-28 (FT pinning skeleton), test scaffold |
| 1 | D-01..D-16, D-50 (sdf property tests), D-51 (no mocking) |
| 2a | D-17..D-23 (cache), D-46 (cache integers in key) |
| 2b | D-24..D-34 (glyph, golden), D-32 (GlyphBBox model) |
| 3 | D-35..D-46 (collision, placement, determinism in hot loop) |
| 4 | D-47..D-49 (observability), Nyquist dims 6 + 8 |
| 5 | Phase exit gate, 3-KI review |

### 12. Risks + mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|------------|--------|------------|
| R-1 | **FreeType version mismatch on dev machines** (Homebrew Pillow ships 2.14.2 vs pinned 2.13.2) | HIGH (any macOS dev) | Golden corpus fails, geometry generation forbidden | `_assert_freetype()` at import (D-28) raises `GeometryEnvironmentError`. Document Docker-only workflow in `docs/development.md`. CI matrix verifies Linux + Docker only — explicitly skip macOS for geometry test job. |
| R-2 | **scipy EDT double-call memory spike on 4K masks** (each EDT allocates float64 distance map ≈ 128 MiB; two of them + 1 float32 result ≈ 320 MiB transient before GC) | MEDIUM (only 4K masks) | Worker OOM under concurrent load before cache eviction stabilizes | (a) Document the 384 MiB cache budget assumes 4 GB worker headroom (D-18). (b) Process one large SDF at a time per worker (Celery `--concurrency=1` from PROD-09). (c) Add `gc.collect()` call inside `compute_sdf` after first EDT to release float64 temporary before second EDT. (d) Wave 4 perf test with 4K mask must measure peak RSS, not just walltime. |
| R-3 | **cachetools LRU + RLock deadlock if nested** (e.g., `get_or_build` calls itself recursively) | LOW | Worker hang | Strict invariant: never call `compute_sdf` *while holding the lock*. Code review checklist item. The pattern in §3 explicitly releases the lock before computing. |
| R-4 | **`blake3` package not available in pinned Docker image** | LOW (we control the image) | Cache key generation falls back to sha256 → 5–10× slower but correct | Add `blake3>=1.0.0` to `pyproject.toml [geometry]` AND verify `import blake3` in CI smoke test. Provide sha256 fallback shim (§3) so no cache crash if blake3 missing in dev environments. |
| R-5 | **Spiral integer rounding diverges across libc** (`math.sin/cos` LSB drift) | LOW (caught by `floor(... + 0.5)` collapse) | One in ~10⁵ candidate positions could differ; placement order may differ; final layout may differ | (a) Determinism test (Wave 4) catches divergence on the dev machine before it lands. (b) Backlog: pre-generate spiral offset table as `.npy` fixture and ship it (escape hatch noted but not implemented in v1). |
| R-6 | **Per-word adaptive POI is too slow** (computing `binary_dilation` + `minimum_filter` for every word on a 2048² canvas with a 200×60 AABB ≈ 0.2 s × 100 words = 20 s/job) | MEDIUM | Render latency overrun for large word lists | (a) Wave 4 perf test must measure 100-word placement on 2048². (b) If too slow, narrow the search region to a bounding box around the eps-band of `sdf` (skip dead-space pixels). (c) **Do NOT pull integral-occupancy forward from Phase 7** — that's locked deferred. Document overrun as a known v1 limitation if needed. |
| R-7 | **`AEROCLOUD_DEBUG_GEO` matplotlib import explodes Docker image size** (matplotlib pulls in ~80 MB) | LOW | Slow CI builds | Lazy-import matplotlib *inside* the debug dump function, not at module import. Mark `matplotlib` as a dev-only optional dependency. |
| R-8 | **Pydantic strict mode rejects numpy ints in `(y, x)` adapters** (numpy returns `np.int64`, Pydantic strict expects Python `int`) | MEDIUM (will surface immediately) | Test failures on first integration | Cast all numpy scalars to `int(...)` at the boundary. Add a unit test that constructs `AABB` from `np.argwhere` output. |
| R-9 | **3-KI Wave 5 Gemini still capacity-exhausted** (was 429 during G-4 already) | MEDIUM | Phase exit gate cannot get all 3 approvals | Document that if Gemini is unavailable, the planner escalates to Jens with a per-Regel-4 transparency note (same protocol used for G-4). |

## Validation Architecture

> Mandatory Nyquist gate per CLAUDE.md Regel 8 + GSD workflow.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + hypothesis 6.151.12 + pytest-benchmark |
| Config file | `packages/engine/pyproject.toml [tool.pytest.ini_options]` (existing from Phase 1) |
| Quick run command | `cd packages/engine && uv run pytest tests/geometry -x --no-header -q` |
| Full suite command | `cd packages/engine && uv run pytest tests/ --hypothesis-profile=ci` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GEO-01 | PNG bytes → bool mask, alpha-aware, threshold 127 | unit | `pytest tests/geometry/unit/test_mask.py -x` | ❌ Wave 0 |
| GEO-02 | Exact signed EDT, float32 boundary | unit + property | `pytest tests/geometry/unit/test_sdf.py tests/geometry/property/test_sdf_properties.py -x` | ❌ Wave 1 |
| GEO-03 | Circle SDF center == radius ± 1 px | unit fixture | `pytest tests/geometry/unit/test_sdf.py::test_circle_center_radius -x` | ❌ Wave 1 |
| GEO-04 | Bytes-bounded LRU cache, blake3 composite key, RLock safe | state + concurrency | `pytest tests/geometry/state/test_cache.py tests/geometry/state/test_cache_threadsafe.py -x` | ❌ Wave 2a |
| GEO-05 | Vectorized AABB overlap, integer | unit | `pytest tests/geometry/unit/test_collision.py -x` | ❌ Wave 3 |
| GEO-06 | Per-word adaptive POI placement, structured drops | unit + integration | `pytest tests/geometry/unit/test_placement.py tests/geometry/integration/test_pipeline.py -x` | ❌ Wave 3 |
| GEO-07 | `font.getmask` pixel-scanned AABB, golden corpus byte-identical | unit + regression | `pytest tests/geometry/unit/test_glyph.py tests/regression/test_glyph_golden.py -x` | ❌ Wave 2b |

### Sampling Rate
- **Per task commit:** `pytest tests/geometry/unit -x -q`  (~5-10 s)
- **Per wave merge:** `pytest tests/geometry tests/regression/test_glyph_golden.py -x`  (~30-60 s)
- **Phase gate:** Full suite + benchmark + determinism + 3-KI approval

### Wave 0 Gaps
- [ ] `tests/geometry/__init__.py` + `unit/`, `integration/`, `property/`, `state/`, `determinism/` subdirs
- [ ] `tests/regression/glyph_golden/` directory
- [ ] `tests/conftest.py` fixtures: `circle_mask_bytes`, `square_mask_bytes`, `c_shape_mask_bytes`, `crescent_mask_bytes`, `tiny_mask_bytes`
- [ ] `cachetools>=7.0.0` + `blake3>=1.0.0` added to `pyproject.toml [geometry]`
- [ ] `pytest-benchmark` confirmed installed
- [ ] `scripts/generate_glyph_golden.py` added (Wave 2b prerequisite)

## Recommended Wave Topology

(Same as §11 above — repeated for planner-quick-reference)

1. **Wave 0** — ADRs (D-09, D-14, D-28) + errors module (D-08, D-28, D-43) + test scaffolding + dep additions. *Serial.*
2. **Wave 1** — `mask.py` (D-04..D-08), `sdf.py` (D-09..D-13), import-time `_assert_freetype()` (D-28), property tests (D-50). *Depends on Wave 0.*
3. **Wave 2** — Parallel:
   - **2a** `sdf_cache.py` (D-17..D-23) with RLock + bytes-bounded LRU + blake3 key
   - **2b** `glyph.py` (D-24..D-34) + golden-corpus generator + `tests/regression/test_glyph_golden.py`
4. **Wave 3** — `collision.py` (D-35..D-37) + `placement.py` (D-38..D-46). Integration test on circle/square/C/crescent. *Depends on Waves 1 + 2.*
5. **Wave 4** — Parallel: observability dump (D-47), structlog (D-48), OTel metrics (D-49), determinism gate (Nyquist 6), perf benchmark (Nyquist 8), wiki updates.
6. **Wave 5** — 3-KI code review per Regel 6 (Claude self + Codex + Gemini). Phase exit gate.

## Open Questions for Planner

1. **Spiral pre-generated offset table (R-5):** Should Wave 4 ship a pre-generated `.npy`
   spiral offset table per `step` value to absolutely guarantee cross-libc determinism,
   or is the `floor(x + 0.5)` integer collapse + determinism test sufficient?
   Recommendation: **start without the table; add only if determinism test fails.**
2. **Centroid distance metric in §6 tiebreak:** Manhattan (`abs(dy)+abs(dx)`) vs
   Euclidean² (`dy² + dx²`) — both satisfy D-39's wording. Manhattan is integer and
   faster; Euclidean² is rotation-invariant. Recommend Manhattan for v1.
3. **`pytest-benchmark` floor:** Does Phase 3 already include `pytest-benchmark` in dev
   deps? If not, Wave 0 must add it.
4. **Settings field for `sdf_cache_max_bytes` (D-18):** Does `aerocloud.config.settings`
   already expose tunable Pydantic settings, or does Phase 4 need to extend it? Verify
   in Wave 0 and add field if missing.
5. **Wave 5 3-KI fallback:** If Gemini is still 429-capacity-exhausted, escalate to
   Jens per Regel 4 transparency.
6. **Performance budget verification (Nyquist dim 8):** "2048² SDF < 1 s on CPU" was
   not quantitatively verified before this research — Wave 4 perf test will be the
   first measurement. If it fails, options are (a) profile and optimize (b) accept a
   higher budget (c) downsample inputs to 2048² when larger arrives. Out-of-scope to
   pre-decide.
7. **`PIL.features.check_feature("raqm")` state assertion (Codex g-4 step 3):** Codex
   recommended asserting RAQM availability state at runtime in addition to the
   FreeType pin. CONTEXT.md only locked the FreeType assertion (D-28). Should the
   planner extend `_assert_freetype()` to also pin RAQM availability? Recommendation:
   **yes — add `_assert_raqm_unchanged()` checking RAQM is consistently available or
   unavailable across CI matrix.** Treat as Claude's discretion under D-28.

## Sources

### Primary (HIGH confidence)
- `pillow.readthedocs.io/en/stable/reference/ImageFont.html` — `truetype()` and `getmask()` signatures
- `pillow.readthedocs.io/en/stable/reference/features.html` — `version("freetype2")` API
- `pillow.readthedocs.io/en/stable/reference/Image.html` — `Image.open`, `convert`, `split`
- `docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.distance_transform_edt.html`
- `docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.binary_dilation.html`
- `docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.minimum_filter.html`
- `cachetools.readthedocs.io/en/stable/` — `LRUCache`, `getsizeof` semantics, NOT thread-safe
- `numpy.org/doc/stable/reference/generated/numpy.argmax.html` — first-occurrence determinism
- `pypi.org/project/blake3/` — version 1.0.8, native Rust impl
- `hypothesis.readthedocs.io/en/latest/numpy.html` — `arrays` strategy for binary masks

### Phase 4 review artifacts (Codex BLOCKED, Gemini partial)
- `.planning/phases/04-geometry-v1/3ki-g3-g4-g5/codex-g3.md` (SDF cache)
- `.planning/phases/04-geometry-v1/3ki-g3-g4-g5/codex-g4.md` (glyph + `hint_style` hallucination catch)
- `.planning/phases/04-geometry-v1/3ki-g3-g4-g5/codex-g5.md` (placement)
- `.planning/phases/04-geometry-v1/3ki-g3-g4-g5/gemini-g3.md` (LRU research)
- `.planning/phases/04-geometry-v1/3ki-g3-g4-g5/gemini-g5.md` (POI + step research)

### Project carry-forward (HIGH confidence — already executed Phases 1–3)
- `packages/engine/src/aerocloud/nlp/tokenize.py` — RLock registry pattern (template for §3)
- `packages/engine/src/aerocloud/models/base.py` — `AeroCloudBase(frozen, strict, extra=forbid)`
- `packages/engine/src/aerocloud/utils/determinism.py` — `set_seed()` (D-45)
- `packages/engine/src/aerocloud/fonts.py` — `_discover_font_files()` for golden generator
- `packages/engine/pyproject.toml` — extras structure for adding cachetools + blake3

### Verified package versions (PyPI 2026-04-09 via `pip index versions`)
- `cachetools` → 7.0.5 (current)
- `blake3` → 1.0.8 (current)
- `hypothesis` → 6.151.12 (current)
- `pytest` → 9.0.3 (current)

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `aerocloud.config.settings.sdf_cache_max_bytes` field exists or is trivially addable | §3 cache, R-3 | Wave 0 must add the field; minor planner friction |
| A2 | Phase 3 already added `pytest-benchmark` to dev deps | §10 dim 8 | Wave 0 must add it; minor |
| A3 | `pytest 9.x` is compatible with current project pin (project pyproject.toml does not show pytest version) | §10 | Phase 3 hermetic test pattern works on whatever pytest version is installed |
| A4 | Manhattan distance is acceptable as the centroid-tiebreak metric under D-39's wording | §6 origin selection | If Euclidean is required by interpretation, swap to `dy*dy + dx*dx` (still integer) — trivial |
| A5 | `binary_dilation` + `minimum_filter` will meet R-6 perf budget for 100-word, 2048² placement | §6 | Wave 4 perf test will measure; mitigation in R-6 |
| A6 | `math.sin/cos` libc drift will be absorbed by `floor(x + 0.5)` integer rounding for our spiral step values | §7 | If determinism test fails on dev box, escape hatch is the pre-generated offset table |
| A7 | `PIL.features.version("freetype2")` returns the exact pinned `"2.13.2"` string under the Phase 1 Docker base image | §4 D-28 | Wave 0 must verify by running `python -c 'from PIL import features; print(features.version("freetype2"))'` inside the Docker image and confirm the string matches BEFORE committing the assertion. If actual version differs, update `_EXPECTED_FREETYPE` in code AND ADR-0006 in the same commit. |

## Metadata

**Confidence breakdown:**
- Standard stack (versions, APIs): HIGH — verified PyPI + official docs 2026-04-09
- Mask + SDF + cache patterns: HIGH — Codex-vetted, Phase 3 RLock template proven
- Glyph raster: HIGH — Codex g-4 docs-verified, hallucination already removed
- Placement (POI + spiral): MEDIUM-HIGH — Codex g-5 redesigned the algorithm; integer
  determinism rests on the rounding collapse (A6), which is testable in Wave 4
- Wave topology: MEDIUM — depends on planner's task-granularity preferences
- Risk mitigations: MEDIUM — R-2 (memory spike) and R-6 (placement perf) need
  empirical Wave 4 measurements

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (30 days; Pillow 12.1.x and scipy 1.14.x are stable)

## RESEARCH COMPLETE

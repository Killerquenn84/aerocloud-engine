# Export Pipeline

**Phase:** 12-production-v1
**Plans:** 12-01, 12-02
**Requirements:** PROD-01, PROD-02, PROD-03, PROD-04, PROD-05, PROD-06
**Source package:** `packages/engine/src/aerocloud/export/`

---

## Overview

The export pipeline converts word cloud render output into deliverable formats. It
consists of five modules, each with a single responsibility:

| Module | Responsibility | Formats |
|--------|---------------|---------|
| `seam_carving.py` | Adaptive canvas resizing (Blueprint Teil VI) | ndarray |
| `png_export.py` | Tensor-to-PNG conversion | PNG bytes |
| `svg_export.py` | BezierGlyph to SVG document (PROD-03) | SVG string |
| `pdf_export.py` | BezierGlyph to PDF at 300 DPI (PROD-04) | PDF bytes |
| `boolean_union.py` | Bezier polygon boolean union via Shapely (PROD-06) | Shapely geometry |

**Coordinate convention:** All engine internals use `(y, x)` ordering. The flip to
`(x, y)` happens exactly once per export module — in the private helper function.
This is a hard invariant; violating it produces mirrored output.

---

## Module: seam_carving.py

**Blueprint Teil VI** — Energy-based adaptive canvas resizing.

### build_energy_map

```python
def build_energy_map(
    canvas_h: int,
    canvas_w: int,
    word_positions: list[tuple[int, int]],  # (y, x) pixel coords
    word_weights: list[float],
    sigma: float = 15.0,
) -> np.ndarray:  # shape (canvas_h, canvas_w), float64
```

Builds a Gaussian-weighted energy map. Each word contributes:
`E(y,x) = sum_i(w_i * exp(-dist^2 / (2*sigma^2)))`

**DoS guard:** `canvas_h` and `canvas_w` must be <= 4096 (T-12-01-01). Raises
`ValueError` on violation.

**Usage:**
```python
energy = build_energy_map(512, 512, [(64, 64), (128, 200)], [1.0, 0.8])
# energy.shape == (512, 512)
```

---

### find_vertical_seam

```python
def find_vertical_seam(energy: np.ndarray) -> np.ndarray:  # shape (H,), dtype int64
```

Finds the minimum-energy vertical seam via Dynamic Programming, O(w*h).

**Implementation detail:** The DP inner loop is vectorized using `np.minimum` on
shifted arrays — no Python loop over columns. This gives ~10x speedup vs naive
row-by-row iteration.

**Returns:** Array of column indices `seam[row]` — one x-index per row of the canvas.

---

### remove_vertical_seam

```python
def remove_vertical_seam(
    arr: np.ndarray,   # 2D (H, W) or 3D (H, W, C)
    seam: np.ndarray,  # shape (H,) — column indices from find_vertical_seam
) -> np.ndarray:       # shape (H, W-1) or (H, W-1, C)
```

Removes the seam from a 2D or 3D array, shrinking width by 1. Supports both
grayscale energy maps (2D) and RGB images (3D).

**Usage (full pipeline):**
```python
energy = build_energy_map(h, w, positions, weights)
seam = find_vertical_seam(energy)
canvas_rgb = remove_vertical_seam(canvas_rgb, seam)
```

---

## Module: png_export.py

### export_png

```python
def export_png(
    tensor: torch.Tensor,   # (H, W), (1, H, W), (1, 1, H, W), or (3, H, W) float32
    mode: str = "L",        # "L" = grayscale, "RGB" = color
) -> bytes:                 # PNG-encoded bytes
```

Converts a PyTorch float32 tensor (range [0, 1]) to PNG bytes via PIL.

**Pipeline:** clamp to [0,1] → scale by 255 → `uint8` → `PIL.Image` → PNG bytes.

**Roundtrip guarantee:** Maximum error per pixel is 1/255 (uint8 quantization).

**DoS guard:** None at this layer — tensor size is bounded upstream by the renderer.

**Usage:**
```python
density = renderer.forward(128, 128)   # (1, 1, H, W)
png_bytes = export_png(density, mode="L")
```

---

## Module: svg_export.py

### export_svg

```python
def export_svg(
    glyphs: list[BezierGlyph],
    width: int = 512,
    height: int = 512,
    fill: str = "#000000",    # hex color — validated by validate_hex_color
) -> str:                     # SVG XML string
```

Converts a list of `BezierGlyph` objects to an SVG document string via `lxml.etree`.

**Output attributes:** `viewBox="0 0 {width} {height}"`, `width`, `height`, `fill`.

**Coordinate flip:** `(y, x)` → `(x, y)` is applied in `_bezier_curve_to_svg_cmd`
(private, single flip point).

**SVG path format:** Each contour becomes `M ... C ... Z`. Cubic Bezier control
points are serialized with 6 decimal places.

---

### glyph_to_svg_path

```python
def glyph_to_svg_path(glyph: BezierGlyph) -> str:  # SVG d-attribute string
```

Converts a single `BezierGlyph` to an SVG path `d` attribute. Used internally by
`export_svg` and available for custom SVG assembly.

**Usage:**
```python
svg_str = export_svg(glyphs, width=1024, height=768, fill="#1a1a1a")
# Returns: '<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="768" ...>'
```

---

## Module: pdf_export.py

### export_pdf

```python
def export_pdf(
    glyphs: list[BezierGlyph],
    width_px: int = 512,
    height_px: int = 512,
    fill: str = "#000000",    # hex color — validated by validate_hex_color
) -> bytes:                   # PDF bytes starting with b'%PDF-'
```

Converts a list of `BezierGlyph` objects to PDF bytes via ReportLab at 300 DPI.

**Coordinate conversion:** `PX_TO_PT = 0.24` (pixels to ReportLab points at 300 DPI).
The `(y, x)` → `(x, y)` flip is applied in `_build_glyph_path`.

**Constants exported:**
- `DPI = 300` — dots per inch for print-quality output
- `PX_TO_PT = 0.24` — pixel to ReportLab point conversion factor

**Usage:**
```python
pdf_bytes = export_pdf(glyphs, width_px=1024, height_px=768)
assert pdf_bytes[:4] == b'%PDF'
```

---

## Module: boolean_union.py

### bezier_curve_to_points

```python
def bezier_curve_to_points(
    curve: BezierCurve,
    n: int = 20,           # tessellation segments — capped at 50 (T-12-01-03)
) -> list[tuple[float, float]]:  # (x, y) Shapely convention
```

Tessellates a cubic Bezier curve into `n+1` points via De Casteljau's algorithm.

**Coordinate flip:** Engine `(y, x)` → Shapely `(x, y)` applied here. This is the
single flip point for the boolean union pipeline.

**DoS guard:** `n` is capped at 50 (T-12-01-03). Raises `ValueError` on violation.

---

### glyph_to_polygon

```python
def glyph_to_polygon(
    glyph: BezierGlyph,
    n: int = 20,
) -> Polygon:  # shapely.geometry.Polygon
```

Converts a `BezierGlyph` to a Shapely `Polygon`. The first contour is the outer
ring; subsequent contours become holes.

---

### union_glyphs

```python
def union_glyphs(
    glyphs: list[BezierGlyph],
    n: int = 20,
) -> BaseGeometry:  # shapely.geometry.base.BaseGeometry
```

Computes the boolean union of all glyphs via `shapely.ops.unary_union`. Prevents
double-cuts in print output.

**Return type:** `BaseGeometry` (not converted back to `BezierGlyph`) — the
round-trip back to Bezier form is lossy and is an explicit anti-pattern.

**Usage:**
```python
from shapely.geometry import MultiPolygon
merged = union_glyphs(glyphs)
if isinstance(merged, MultiPolygon):
    for poly in merged.geoms:
        # process each connected region
        ...
```

---

## Security Validators (security.py)

Located at `packages/engine/src/aerocloud/models/security.py`. Wired into
`RenderRequest` field validators.

| Function | Rule | Validates |
|----------|------|-----------|
| `validate_hex_color(v)` | `^#[0-9a-fA-F]{3,8}$` | SVG/PDF fill colors (D-15) |
| `validate_font_name(v)` | assets/fonts/ allow-list | Font family names (D-16) |
| `validate_no_path_traversal(v)` | rejects `../`, `..\`, `\x00` | File-like inputs (D-17) |
| `get_allowed_fonts()` | cached frozenset | Returns allowed font names |

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `numpy` | pinned | Energy map, seam DP |
| `torch` | 2.7.1 | Tensor input for PNG export |
| `Pillow` | 12.1.1 | PNG encoding |
| `lxml` | >=5.0.0 | SVG document generation |
| `reportlab` | pinned | PDF generation at 300 DPI |
| `shapely` | >=2.1.2 | Boolean union (GEOS-backed) |

---

*Last updated: Phase 12 Plan 09 release gate*
*Owner: AeroCloud Engine Phase 12 — Production v1*

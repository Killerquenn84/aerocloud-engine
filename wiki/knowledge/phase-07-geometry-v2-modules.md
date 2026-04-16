# Phase 07 Geometry-v2: Module Documentation

**Phase:** 07-geometry-v2
**Completed:** 2026-04-16
**Requirements:** GEO2-01 to GEO2-09

---

## Overview

Phase 7 added 5 new modules to `packages/engine/src/aerocloud/geometry/`:
- `mat.py` — Medial Axis Transform skeleton extraction (GEO2-01, GEO2-02)
- `mat_cache.py` — LRU cache for MATResult objects (GEO2-02)
- `quadtree.py` — Quadtree spatial index, Stage 3 collision (GEO2-05)
- `bezier.py` — Bezier path representation for glyph boundaries (GEO2-09)
- `multi_centric.py` — Multi-centric word placement per MAT branch (GEO2-03)

And extended 3 existing modules:
- `collision.py` — BVH (Stage 2), SAT (Stage 4), Bitmap (Stage 5) added (GEO2-04, GEO2-06, GEO2-07, GEO2-08)
- `renderer/_renderer.py` — Dual-mode forward pass (mode='both') (D-20)
- `optimizer/inner_loop.py` — Consumes (density, additive) tuple (D-21)
- `optimizer/loss.py` — `compute_additive_density` deleted (D-21)

---

## Module: `mat.py`

### API

```python
def extract_mat(sdf: np.ndarray, min_branch_radius: float = 3.0) -> MATResult
```

Extracts the Medial Axis Transform from an SDF.

```python
class MATResult(AeroCloudBase):
    branches: tuple[MATBranch, ...]  # ordered by branch_id ascending
    branch_map: np.ndarray  # int32 (H, W) — branch_id per inside pixel, -1 outside
    travel_time: np.ndarray  # float32 (H, W) — Eikonal travel time, NaN outside

class MATBranch(AeroCloudBase):
    branch_id: int  # 1-based
    origin_yx: tuple[int, int]  # deepest inside point of branch (argmax SDF)
    sdf_volume: float  # sum of SDF values in this branch's Voronoi cell
    pixel_count: int  # number of pixels in this branch's Voronoi cell
```

### Algorithm

1. Ridge extraction: `scipy.ndimage.maximum_filter(sdf, size=3)` — local maxima above `min_branch_radius`
2. Ridge dilation: `binary_dilation(ridge, iterations=2)` — closes 1-pixel gaps
3. Labelling: `scipy.ndimage.label(ridge_connected)` — connected component labels
4. Branch origins: argmax SDF per component with lexicographic (y,x) tiebreak (D-15)
5. Travel time: `skfmm.travel_time` from mask centroid (float64 → float32 cast, D-03/Pitfall 1)
6. Branch map: nearest-origin Voronoi via per-origin `distance_transform_edt`

### Known Limits

- **ML-7-01:** Ridge extraction uses `maximum_filter` with `size=3` (3×3 neighbourhood). Thin structures thinner than 3 pixels may not produce ridge points. Mitigated: `binary_dilation(iterations=2)` closes 1-pixel gaps.
- **ML-7-02:** `_build_branch_map_voronoi` calls `distance_transform_edt` k times for k branches — O(N*k). k bounded by `min_branch_radius` threshold (typically 2-8 branches).
- **ML-7-03:** skfmm fallback (ValueError on pathological masks): returns zero-filled `travel_time` — still valid for branch origin selection. Hypothesis property tests verify this.

### SDF Contract

- Input SDF must be float32, 2D, positive inside (ADR-0004)
- Any NaN/inf in SDF raises `PlacementFailedError`
- Empty mask raises `GeometryError`

---

## Module: `mat_cache.py`

### API

```python
def get_or_build_mat(sdf: np.ndarray, min_branch_radius: float = 3.0) -> MATResult
def clear_mat_cache() -> None  # test helper
```

### Cache Policy

- **Storage:** `cachetools.LRUCache` bounded by bytes (`settings.mat_cache_max_bytes`, default 128 MiB)
- **Key:** `(blake3_digest, ("min_branch_radius", value), ("mat_algo_version", N), shape_tuple)`
- **Thread safety:** Module-level `RLock` with double-checked locking (D-22)
- **Eviction:** LRU; items larger than budget silently not cached (ValueError suppressed)
- **Version salt:** `_MAT_ALGO_VERSION = 1` — bump to invalidate all entries when `extract_mat` changes

### Key Structure (T-07-01-01)

Every parameter that affects the result is in the key:
- `blake3_digest`: Content-addressed SDF bytes
- `min_branch_radius`: Pruning threshold
- `mat_algo_version`: Algorithm version salt
- `shape_tuple`: Ensures shape changes bust cache (even with same bytes for different sizes)

---

## Module: `quadtree.py`

### API

```python
def build_quadtree(bounds: tuple[int,int,int,int], max_depth: int = 8, split_threshold: int = 8) -> QuadtreeNode
def insert_aabb(node: QuadtreeNode, idx: int, aabb: np.ndarray, max_depth: int = 8, split_threshold: int = 8) -> None
def query_region(node: QuadtreeNode, region: np.ndarray) -> list[int]

@dataclass
class QuadtreeNode:
    bounds: tuple[int, int, int, int]  # (y0, x0, y1, x1) half-open
    items: list[tuple[int, np.ndarray]]  # (index, aabb) pairs at leaf
    children: list[QuadtreeNode] | None  # 4-element list [NW, NE, SW, SE] or None
    depth: int
```

### Design Notes

- **max_depth default = 8 reasoning:** 8 levels of subdivision = 4^8 = 65536 cells for a 512×512 canvas → each cell covers ~2×2 pixels. Sufficient for 200-word placement density. Prevents excessive recursion on duplicate AABBs (T-07-02-03).
- **AABB duplication:** An AABB that straddles a quadrant boundary appears in multiple children. `query_region` returns duplicates — deduplicate at call site if needed.
- **IMPORTANT API NOTE:** `build_quadtree` accepts `max_depth` and `split_threshold` but does NOT store them on the root. These must be passed again to `insert_aabb` at insertion time. This is a usability trade-off: keeps node struct minimal.

### Stage 3 in 5-Stage Pipeline

Stage 3 (Quadtree) is inserted after Stage 2 (BVH broadphase):
1. AABB: fast vectorized numpy check
2. BVH: binary tree broadphase (build once, query O(log N))
3. Quadtree: spatial index for dense local neighborhoods
4. SAT: rotated rectangle exact test
5. Bitmap: pixel-exact uint32 packed test

---

## Module: `bezier.py`

### API

```python
def glyph_to_bezier(glyph: GlyphBBox, tolerance: float = 1.0) -> BezierGlyph

class BezierCurve(AeroCloudBase):
    p0: tuple[float, float]  # (y, x) start — float64
    p1: tuple[float, float]  # (y, x) control 1
    p2: tuple[float, float]  # (y, x) control 2
    p3: tuple[float, float]  # (y, x) end

class BezierGlyph(AeroCloudBase):
    font_family: str
    size_pt: int
    codepoint: int
    contours: tuple[tuple[BezierCurve, ...], ...]  # outer = contours, inner = segments
    tolerance: float
```

### Algorithm

1. Empty check: `pixel_buffer.max() == 0` → return BezierGlyph with empty contours
2. Binarize: `(pixel_buffer > 0).astype(uint8) * 255`
3. `cv2.findContours(RETR_LIST, CHAIN_APPROX_SIMPLE)` — extracts all contours including holes
4. `cv2.approxPolyDP(epsilon=tolerance, closed=True)` — Douglas-Peucker simplification
5. **Coordinate flip:** `pts[:, ::-1]` converts cv2 (x,y) → (y,x) canonical (D-14/T-07-05-01)
6. Catmull-Rom to cubic Bezier conversion: `P1_ctrl = P1 + (P2-P0)/6; P2_ctrl = P2 - (P3-P1)/6`

### Known Limits

- **ML-7-04:** `cv2.RETR_LIST` returns all contours flat — no hierarchy. Nested holes and outer contours are all at the same level. Hierarchy (inner/outer) is not preserved. Phase 12 SVG export may need `cv2.RETR_TREE` for correct fill rules.
- **ML-7-05:** `tolerance=1.0` (default) gives sub-millimeter precision at typical DPI. Higher tolerance reduces curve count but loses fine detail.
- **ML-7-06:** Catmull-Rom gives C1-continuous curves — tangent-continuous at vertices. Not C2 (curvature-discontinuous at vertices). Acceptable for glyph approximation.

### Coordinate Convention (D-14)

All `BezierCurve` control points are in (y, x) float64 ordering. The cv2 flip is applied at the `approxPolyDP → Bezier` boundary. This is tested by `test_bezier_coordinate_flip_applied`.

### Integration with Phase 12

`BezierGlyph` is consumed by Phase 12 SVG/PDF export. The `contours` tuple serializes cleanly via Pydantic's `model_dump_json()` → flat JSON for streaming to the export pipeline.

---

## Module: `multi_centric.py`

### API

```python
def place_words_multi_centric(
    sdf: np.ndarray,
    mask: np.ndarray,
    words: list[tuple[str, int, int]],  # (text, h, w) sorted descending by weight
    seed: int = 0,
    mat_min_branch_radius: float = 3.0,
) -> MultiCentricResult

class MultiCentricResult(AeroCloudBase):
    placements: list[PlacedWord]
    dropped_words: list[DroppedWord]
    stats: PlacementStats
    branch_count: int
    words_per_branch: tuple[int, ...]  # indexed by branch position, not branch_id
```

### Word-to-Branch Assignment Algorithm (D-13)

1. Compute `target_i = round(sdf_volume_i / total_volume * n_words)` per branch
2. Sum of `round(x)` may differ from `n_words` by ±k due to floating-point rounding
3. `_fix_rounding_drift` adjusts: add to highest-volume branches first (deficit), subtract from lowest-volume branches first (surplus)
4. Lexicographic `branch_id` tiebreak on equal volumes — deterministic (Pitfall 4)

### Determinism Guarantees (D-15)

- `set_seed(seed)` called once at entry (global seed)
- `set_seed(seed)` called again per branch in `_place_words_on_arrays` — same seed per branch
- All sort operations use `branch_id` ascending as explicit tiebreak
- `words_per_branch` tuple is derived from `assignment` list in branch_id order
- 10-run identity test verifies exact byte-identical results

### D-14 Single-Branch Fallback

When `mat.n_branches <= 1`:
- Falls back to `_place_words_on_arrays(sdf, mask, words, seed)` — same as single-centric
- Returns `branch_count=1`, `words_per_branch=(len(words),)` in result
- Transparent to callers — same API

### Known Limits

- **ML-7-07:** `_place_words_on_arrays` imports private functions (`_place_one_word`, `_compute_centroid`) from `placement.py`. Any internal refactor of `placement.py` may silently break `multi_centric.py`. Phase 12 should expose a public `place_words_on_arrays` function.
- **ML-7-08:** Using the same `seed` for all branches means each branch's spiral search is independently seeded identically. Words in branch 2 start with the same random offsets as branch 1. This is intentional for determinism but means the layouts may look similar across branches.
- **ML-7-09:** Sub-SDF masking: `sub_sdf = np.where(branch_map == bid, sdf, 0.0)` — pixels outside the branch get SDF=0, which the placement pipeline treats as "on boundary" (not inside, not outside). Words cannot be placed there. This is correct but means the boundary between branches has a 1-pixel neutral zone.

---

## Collision Module Extensions (collision.py)

### Stage 2: BVH

```python
def build_bvh(aabbs: np.ndarray, depth: int = 0, max_depth: int = 20) -> BVHNode
def bvh_query_overlap(tree: BVHNode, query_aabb: np.ndarray, aabbs: np.ndarray) -> list[int]
def get_or_build_bvh(aabbs: np.ndarray) -> BVHNode
```

Split heuristic: longest axis, median centroid split (EdWordle/RESEARCH.md Pattern 3).
Cache: `maxsize=128` entries (BVH trees are small Python dicts — byte-bounded doesn't apply).

### Stage 4: SAT

```python
def sat_overlap_rotated_rect(cy1, cx1, h1, w1, theta1, cy2, cx2, h2, w2, theta2) -> bool
```

4-corners + 4-edge-normal axes per rectangle. Degenerate edge guard: `norm < 1e-10`.
NOT differentiable (D-09) — hard reject only.

### Stage 5: Bitmap

```python
def pack_bitmap_uint32(pixel_buffer: np.ndarray) -> np.ndarray  # (H, W) uint8 → (H, ceil(W/32)) uint32
def bitmap_collision(packed_a, ay_min, ax_min, a_h, a_w, packed_b, by_min, bx_min, b_h, b_w) -> bool
```

Key implementation: `bit_shift = (ax_min % 32) - (bx_min % 32)` corrects for misaligned 32-pixel word boundaries (RESEARCH.md Pitfall 3). `_shift_packed_row_right` uses uint64 arithmetic for carry propagation.

---

## Test Coverage Summary

| Module | Unit | Integration | Determinism | Property | Total |
|--------|------|-------------|-------------|----------|-------|
| mat.py + mat_cache.py | 9 | 7 | 0 | 4 | 20 |
| collision.py (BVH/Quadtree/SAT/Bitmap) | 15+19 | 3+3 | 0 | 0 | 40 |
| quadtree.py | 6 | 0 | 1 | 0 | 7 |
| bezier.py | 10 | 3 | 0 | 0 | 13 |
| multi_centric.py | 8 | 4 | 2 | 0 | 14 |
| renderer dual-mode | 8 | 0 | 0 | 0 | 8 |
| optimizer dual-mode | 4 | 0 | 0 | 0 | 4 |
| **Total Phase 7** | **79** | **20** | **3** | **4** | **106** |

All 787+ tests GREEN (including 481 pre-Phase-7 tests from Phases 4-6).

---

*Phase: 07-geometry-v2*
*Completed: 2026-04-16*
*Next phase: 08-semantic-vector-space*

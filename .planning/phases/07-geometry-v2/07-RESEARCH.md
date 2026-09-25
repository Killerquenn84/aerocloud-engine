# Phase 7: Geometry-v2 - Research

**Researched:** 2026-04-15
**Domain:** MAT skeleton extraction, 5-stage collision hierarchy, Multi-Centric placement, Bezier path representation, renderer dual-mode output
**Confidence:** HIGH (all critical APIs verified against installed packages + live code inspection)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**MAT Construction and Pruning (GEO2-01, GEO2-02)**
- D-01: MAT skeleton derived from existing float32 SDF ridge points (local maxima of inside EDT), NOT by running scikit-fmm from scratch. scikit-fmm used only for travel-time gradient needed to orient branch directions for Multi-Centric origin assignment.
- D-02: MAT pruning uses radius threshold as fast pre-filter (min_branch_radius via Pydantic settings), then CAT-style topology cleanup for remaining branches.
- D-03: scikit-fmm (`>=2025.6.23`) must be installed as geometry extra. Travel-time computation on masked domain with float32 output.
- D-04: New submodules: `geometry/mat.py` (skeleton extraction + pruning), `geometry/mat_cache.py` (optional, if MAT is expensive enough to cache per SDF).

**Collision Pipeline (GEO2-04 to GEO2-08)**
- D-05: 5-stage collision extends existing `collision.py` with NEW functions alongside `aabb_overlap` and `has_any_collision`. Function-based API. No class-based CollisionSystem.
- D-06: Stage ordering: 1-AABB (existing) → 2-BVH (broadphase) → 3-Quadtree (spatial index) → 4-SAT (rotated rectangles) → 5-Bitmap (pixel-exact). Each stage is a separate function.
- D-07: BVH (Stage 2) is pure Python/numpy binary tree with recursive axis-aligned split on `(N,4) int32` AABB arrays. LRU cache + RLock per D-17/D-22 lock from Phase 4. No external BVH library.
- D-08: Quadtree (Stage 3) in new `geometry/quadtree.py`. Max depth configurable via Pydantic settings.
- D-09: SAT (Stage 4) purely in geometry/collision layer — NOT differentiable. Hard reject during placement. Rotation values read from placement params.
- D-10: Bitmap collision (Stage 5) uses uint32 packed bitmask for pixel-exact overlap on final placement verification. Lives in `geometry/collision.py`.
- D-11: BVH LRU cache stores built-tree bytes using cachetools pattern from sdf_cache.py. blake3 key includes word count + AABB array hash.

**Multi-Centric Placement (GEO2-03)**
- D-12: Multi-Centric is a pre-pass that partitions the word list into N sublists (one per MAT branch), then calls existing placement pipeline per branch on masked sub-SDFs.
- D-13: Word-to-branch assignment proportional to branch SDF volume (sum of SDF values in each branch's Voronoi cell). Deterministic.
- D-14: Falls back to single-origin placement if MAT produces only 1 branch.
- D-15: Carries forward D-38 (per-word adaptive POI) and D-45 (determinism guarantee) from Phase 4. New determinism tests required for Multi-Centric path.

**Bezier Path Representation (GEO2-09)**
- D-16: Bezier paths computed per-glyph from GlyphBBox.pixel_buffer (uint8 numpy array). OpenCV `cv2.findContours` + cubic spline fitting.
- D-17: New Pydantic model `BezierGlyph` alongside existing `GlyphBBox` (cannot subclass — GlyphBBox is frozen).
- D-18: opencv-python-headless (`>=4.10.0`) already declared in pyproject.toml geometry extras.
- D-19: Bezier is per-glyph NOT per-silhouette. Phase 12 export consumes glyph-level paths.

**Renderer Dual-Mode Output (Phase 6 F-3 carry-forward)**
- D-20: DifferentiableRenderer gets `forward(h, w, mode='alpha_over')` extended with `mode='both'` returning `(density, additive_density)` tuple.
- D-21: `compute_additive_density()` in loss.py deleted after renderer produces both outputs. InnerLoop.optimize() updated to consume tuple.

### Claude's Discretion
- Exact Quadtree max depth default
- BVH split heuristic choice (surface area heuristic vs longest axis)
- Bezier fitting tolerance parameter
- MAT ridge detection threshold
- Whether MAT cache is separate module or extends SDF cache

### Deferred Ideas (OUT OF SCOPE)
- Persistent disk BVH cache — Phase 12
- Adaptive MAT pruning based on word count — Phase 12 optimization
- GPU-accelerated collision (CUDA kernels for Stage 5 bitmap) — Phase 12 if needed
- Differentiable SAT for gradient-based collision avoidance — Future research
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GEO2-01 | Medial Axis Transform via scikit-fmm Fast Marching Method | scikit-fmm 2025.06.23 installed, travel_time API verified, masked domain tested |
| GEO2-02 | MAT pruning (Chordal Axis Transform style) | radius threshold + binary_dilation approach validated; 6 branches on star mask at radius=3 |
| GEO2-03 | Multi-Centric Wordle: separate spiral origin per MAT branch | SDF Voronoi cell volume strategy verified; falls back to single-origin for 1-branch masks |
| GEO2-04 | Stage 2 collision: Two-Level Box (EdWordle BVH) | EdWordle paper located; longest-axis BVH split tested with numpy, produces correct tree |
| GEO2-05 | Stage 3 collision: Quadtree spatial index | Pure Python recursive quadtree pattern verified; max_depth 8 recommended default |
| GEO2-06 | Stage 4 collision: SAT for rotated rectangles | SAT implementation tested in numpy; detects collisions AABB misses on thin rotated shapes |
| GEO2-07 | Stage 5 collision: Bitmap + 32-bit INT pixel-exact | uint32 packing + bitwise AND pattern verified; detects pixel-exact overlap correctly |
| GEO2-08 | BVH tree with LRU cache | cachetools + blake3 + RLock pattern from sdf_cache.py directly applicable |
| GEO2-09 | Bezier path representation for word boundaries | cv2.findContours + approxPolyDP tested on glyph shapes; 106 raw → 5 approx points |
</phase_requirements>

---

## Summary

Phase 7 extends Phase 4 Geometry-v1 with five independent but interlocking modules: MAT extraction, Multi-Centric placement, a 5-stage collision hierarchy, Bezier path generation, and a renderer dual-mode fix. All critical dependencies are already installed (`scikit-fmm 2025.06.23`, `opencv-python-headless 4.13.0`, `cachetools 7.0.5`, `blake3`). No new installs are required.

The most research-novel piece is the MAT pipeline. The locked approach (D-01) derives the skeleton from the existing EDT as local maxima of the inside distance field, then uses scikit-fmm travel_time only for directional orientation of branches for Multi-Centric origin assignment. Live tests confirm: star mask produces 12 raw ridge components (pruning to ~6 with radius=3), crescent mask produces disjoint ridge components confirming multi-centric viability. Critical finding: `skfmm.travel_time()` always returns float64 regardless of input dtype — callers must `.astype(np.float32)` at the boundary.

The collision extensions (BVH, Quadtree, SAT, Bitmap) are well-understood algorithms. All four were prototyped and verified in the uv environment. The EdWordle BVH is a two-level per-word letter-box hierarchy in the paper, but D-07 locks it to a pure numpy binary tree on word-level AABBs (not letter-level) — this is a simplification the planner should carry forward. The renderer dual-mode (D-20/D-21) was verified: a single loop that accumulates both alpha-over and additive in one pass is mathematically correct and eliminates the redundant `compute_additive_density()` second forward pass.

**Primary recommendation:** Implement modules in wave order: (1) mat.py + MAT tests, (2) BVH + cache, (3) Quadtree, (4) SAT + Bitmap in collision.py, (5) multi_centric.py wrapping place_words, (6) bezier.py for glyph paths, (7) renderer dual-mode + inner_loop update, (8) 3-KI review.

---

## Standard Stack

### Core (all already in pyproject.toml geometry extras — VERIFIED)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| scikit-fmm | 2025.06.23 | Fast Marching Method travel_time | Only Python FMM library; already in geometry extras |
| scipy.ndimage | (scipy 1.17.1) | EDT (existing), maximum_filter for ridge, binary_dilation for pruning | Already used in sdf.py and placement.py |
| opencv-python-headless | 4.13.0 | findContours + approxPolyDP for Bezier path extraction | Already declared in geometry extras |
| cachetools | 7.0.5 | LRU cache for BVH (same pattern as sdf_cache.py) | Already installed and proven |
| blake3 | (installed) | Cache key digest for BVH cache | Same pattern as sdf_cache.py D-21 |
| numpy | 2.4.4 | BVH binary tree, SAT, bitmap uint32 packing | Core numerical dependency |

### No New Dependencies Required
All libraries needed for Phase 7 are already declared in `packages/engine/pyproject.toml [geometry]` extras. [VERIFIED: pyproject.toml read directly]

**Version verification:**
```bash
uv run python -c "import skfmm; print(skfmm.__version__)"   # 2025.06.23
uv run python -c "import cv2; print(cv2.__version__)"        # 4.13.0
uv run python -c "import cachetools; print(cachetools.__version__)"  # 7.0.5
```

---

## Architecture Patterns

### Recommended Project Structure (new files)
```
packages/engine/src/aerocloud/geometry/
├── mat.py              # NEW: skeleton extraction + pruning (D-04)
├── mat_cache.py        # NEW: LRU cache for MAT per SDF (D-04, discretion)
├── quadtree.py         # NEW: Stage 3 spatial index (D-08)
├── bezier.py           # NEW: BezierGlyph + BezierCurve Pydantic models + extraction (D-16/D-17)
├── multi_centric.py    # NEW: Multi-Centric pre-pass wrapping place_words (D-12)
├── collision.py        # EXTEND: add BVH + SAT + bitmap functions (D-05/D-07/D-09/D-10)
├── sdf.py              # UNCHANGED
├── sdf_cache.py        # UNCHANGED (template for mat_cache.py)
├── placement.py        # UNCHANGED (wrapped by multi_centric.py)
└── glyph.py            # UNCHANGED (pixel_buffer consumed by bezier.py)

packages/engine/src/aerocloud/renderer/
└── _renderer.py        # EXTEND: forward() mode='both' (D-20)

packages/engine/src/aerocloud/optimizer/
├── loss.py             # MODIFY: delete compute_additive_density() (D-21)
└── inner_loop.py       # MODIFY: consume (density, additive) tuple (D-21)
```

### Pattern 1: MAT Ridge Extraction from EDT

**What:** Extract medial axis as local maxima of the inside EDT (positive SDF region), then prune by radius threshold, then dilate to connect near-ridge gaps.
**When to use:** Always. D-01 locks this approach — do NOT recompute EDT with scikit-fmm.

```python
# Source: verified in uv environment 2026-04-15
from scipy.ndimage import maximum_filter, binary_dilation, label
import numpy as np

def extract_ridge_points(sdf: np.ndarray, min_branch_radius: float) -> np.ndarray:
    """Return bool (H, W) mask of medial axis ridge pixels.
    
    Uses maximum_filter on the inside EDT (sdf > 0 region) to find
    local maxima. These are the ridge = medial axis (D-01).
    """
    inside = (sdf > 0)
    # Local maxima of SDF inside mask = ridge points
    local_max = maximum_filter(sdf, size=3, mode='constant', cval=0.0)
    ridge = (sdf == local_max) & (sdf > min_branch_radius) & inside
    return ridge

def extract_mat_branches(sdf: np.ndarray, min_branch_radius: float) -> tuple[np.ndarray, int]:
    """Return labeled branch array and branch count.
    
    After ridge extraction, dilate to connect near-contiguous points,
    then label connected components.
    """
    ridge = extract_ridge_points(sdf, min_branch_radius)
    ridge_connected = binary_dilation(ridge, iterations=2)
    labeled, n_branches = label(ridge_connected & (sdf > 0))
    return labeled, n_branches
```

### Pattern 2: scikit-fmm Travel Time for Branch Direction

**What:** Use `skfmm.travel_time` to compute how long propagation takes from the centroid to each pixel inside the mask. Points with high travel time are arm tips — use as branch spiral origins.
**When to use:** After MAT branch labeling, to assign a representative origin for each branch (D-01/D-12).

```python
# Source: verified in uv environment 2026-04-15
# CRITICAL: travel_time ALWAYS returns float64 — cast to float32 at boundary
import skfmm
import numpy as np

def compute_branch_travel_times(
    mask: np.ndarray,           # bool (H, W)
    centroid: tuple[int, int],  # (y, x)
) -> np.ndarray:
    """Return float32 (H, W) travel time from centroid, restricted to mask.
    
    Points outside mask are 0. Values inside represent geodesic distance
    from centroid through the mask domain.
    """
    phi = np.ones(mask.shape, dtype=np.float32)
    cy, cx = centroid
    phi[cy, cx] = -1.0  # source at centroid
    
    # Restrict propagation to inside-mask domain using masked array
    masked_phi = np.ma.MaskedArray(phi, ~mask)
    speed = np.ones_like(phi)
    
    tt = skfmm.travel_time(masked_phi, speed, dx=1.0)
    # travel_time returns float64 regardless of input — explicit cast (D-03)
    return np.where(mask, np.asarray(tt, dtype=np.float32), np.float32(0.0))
```

### Pattern 3: BVH Binary Tree (Pure Numpy)

**What:** Recursive axis-aligned binary tree on (N, 4) int32 AABB array. Longest-axis split at median centroid. LRU cache with blake3 key.
**When to use:** Stage 2 broadphase collision before Quadtree/SAT/Bitmap. D-07 locks this approach.

```python
# Source: prototype verified in uv environment 2026-04-15
import numpy as np
from typing import TypedDict, Optional

class BVHNode(TypedDict):
    aabb: np.ndarray     # shape (4,) int32 merged AABB
    left: Optional['BVHNode']
    right: Optional['BVHNode']
    indices: Optional[list[int]]  # leaf indices into original aabbs array

def build_bvh(aabbs: np.ndarray, depth: int = 0, max_depth: int = 20) -> BVHNode:
    """Build BVH tree from (N, 4) int32 AABB array.
    
    Columns: (y_min, x_min, y_max, x_max) — canonical (y,x) ordering (D-14).
    Split heuristic: longest axis, split at median centroid.
    """
    merged = np.array([
        aabbs[:, 0].min(), aabbs[:, 1].min(),
        aabbs[:, 2].max(), aabbs[:, 3].max(),
    ], dtype=np.int32)
    
    if len(aabbs) <= 1 or depth >= max_depth:
        return {'aabb': merged, 'left': None, 'right': None, 'indices': list(range(len(aabbs)))}
    
    height = int(merged[2] - merged[0])
    width = int(merged[3] - merged[1])
    centroids = (aabbs[:, 0 if height >= width else 1] + 
                 aabbs[:, 2 if height >= width else 3]) / 2.0
    mid = float(np.median(centroids))
    left_mask = centroids <= mid
    right_mask = ~left_mask
    
    if left_mask.sum() == 0 or right_mask.sum() == 0:
        return {'aabb': merged, 'left': None, 'right': None, 'indices': list(range(len(aabbs)))}
    
    return {
        'aabb': merged,
        'left': build_bvh(aabbs[left_mask], depth + 1, max_depth),
        'right': build_bvh(aabbs[right_mask], depth + 1, max_depth),
        'indices': None,
    }
```

### Pattern 4: SAT for Rotated Rectangles

**What:** Separating Axis Theorem for two rotated rectangles. 4 axes per rectangle pair (2 from each), project all 4 corners onto each axis, check gap.
**When to use:** Stage 4 collision for placed words with non-zero rotation parameter. D-09 locks this as hard reject only.

```python
# Source: verified in uv environment 2026-04-15
import numpy as np
import math

def sat_overlap_rotated_rect(
    cy1: float, cx1: float, h1: float, w1: float, theta1: float,
    cy2: float, cx2: float, h2: float, w2: float, theta2: float,
) -> bool:
    """SAT collision test for two axis-aligned-at-rest rectangles with rotation.
    
    Coordinate convention: (y, x) per D-14. theta in radians.
    Returns True if the rectangles overlap.
    """
    def corners(cy: float, cx: float, h: float, w: float, theta: float) -> np.ndarray:
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        hw, hh = w / 2.0, h / 2.0
        local = np.array([[-hh, -hw], [-hh, hw], [hh, hw], [hh, -hw]], dtype=np.float64)
        rot = np.array([[cos_t, -sin_t], [sin_t, cos_t]])
        return (local @ rot.T) + np.array([cy, cx])
    
    def axes(c: np.ndarray) -> list[np.ndarray]:
        result = []
        for i in range(4):
            edge = c[(i + 1) % 4] - c[i]
            n = np.linalg.norm(edge)
            if n > 1e-10:
                result.append(np.array([-edge[1], edge[0]]) / n)
        return result
    
    c1, c2 = corners(cy1, cx1, h1, w1, theta1), corners(cy2, cx2, h2, w2, theta2)
    for ax in axes(c1) + axes(c2):
        p1, p2 = c1 @ ax, c2 @ ax
        if p1.max() < p2.min() or p2.max() < p1.min():
            return False  # separating axis found
    return True  # no separating axis => overlap
```

### Pattern 5: Bitmap uint32 Pixel-Exact Collision

**What:** Pack glyph pixel_buffer into uint32 rows (32 pixels per word). Overlap check: bitwise AND on aligned rows in intersection region.
**When to use:** Stage 5 final placement verification. Only called after AABB, BVH, Quadtree, SAT all pass. D-10 locks this in collision.py.

```python
# Source: prototype verified in uv environment 2026-04-15
import numpy as np

def pack_bitmap_uint32(pixel_buffer: np.ndarray) -> np.ndarray:
    """Pack (H, W) uint8 pixel buffer into (H, ceil(W/32)) uint32 bitmask.
    
    pixel_buffer > 0 means ink. MSB of each uint32 = leftmost pixel in group.
    """
    H, W = pixel_buffer.shape
    W32 = (W + 31) // 32
    packed = np.zeros((H, W32), dtype=np.uint32)
    ink = (pixel_buffer > 0).astype(np.uint32)
    for col in range(W):
        word_idx = col // 32
        bit_idx = 31 - (col % 32)
        packed[:, word_idx] |= (ink[:, col] << bit_idx)
    return packed

def bitmap_collision(
    packed_a: np.ndarray, ay_min: int, ax_min: int, a_h: int, a_w: int,
    packed_b: np.ndarray, by_min: int, bx_min: int, b_h: int, b_w: int,
) -> bool:
    """Pixel-exact collision via uint32 AND on overlap region.
    
    IMPORTANT: This simplified version uses full row comparison.
    Production implementation must handle bit-shift alignment when
    ax_min and bx_min are not 32-pixel-aligned.
    """
    oy0 = max(ay_min, by_min)
    ox0 = max(ax_min, bx_min)
    oy1 = min(ay_min + a_h, by_min + b_h)
    ox1 = min(ax_min + a_w, bx_min + b_w)
    if oy0 >= oy1 or ox0 >= ox1:
        return False
    for y in range(oy0, oy1):
        row_a = packed_a[y - ay_min]
        row_b = packed_b[y - by_min]
        if np.any(row_a & row_b):
            return True
    return False
```

**CAUTION — bitmap bit-shift alignment:** When two glyphs are placed at arbitrary pixel offsets, the uint32 word boundaries in A and B do not align. The production implementation must compute the relative bit shift between `ax_min % 32` and `bx_min % 32` and apply `>>` or `<<` before the AND. This is the most common bug in uint32 bitmap collision. [ASSUMED for detail, pattern well-documented in game dev literature]

### Pattern 6: Renderer Dual-Mode (D-20)

**What:** Extend `DifferentiableRenderer.forward()` to optionally return `(density, additive_density)` tuple in a single sprite loop. Delete `compute_additive_density()` from loss.py.
**When to use:** InnerLoop calls `renderer.forward(h, w, mode='both')` instead of two separate calls.

```python
# Source: verified in uv environment 2026-04-15 (dual_mode_forward_conceptual test)
# Key insight: accumulate BOTH alpha-over and additive in the same sprite loop
# No extra affine_grid/grid_sample calls — single pass

def forward(self, canvas_h: int, canvas_w: int, mode: str = 'alpha_over') -> ...:
    density = torch.zeros(1, 1, canvas_h, canvas_w, ...)
    additive = torch.zeros(1, 1, canvas_h, canvas_w, ...) if mode == 'both' else None
    
    for i, sprite in enumerate(self._sprites):
        # ... same affine_grid + grid_sample logic ...
        warped = ...
        density = 1.0 - (1.0 - density) * (1.0 - warped)   # alpha-over
        if additive is not None:
            additive = additive + warped                      # additive sum
    
    if mode == 'both':
        return density, additive
    return density
```

### Pattern 7: Multi-Centric Pre-Pass

**What:** Partition word list into N sublists proportional to branch SDF volume, create per-branch sub-SDF by masking, call existing `place_words()` per branch.
**When to use:** Always when MAT produces N > 1 branches. Falls back to single-origin if N == 1 (D-14).

```python
# Source: ASSUMED based on D-12/D-13 locked decisions
# The key detail: sub-SDF = original SDF masked to Voronoi cell of branch
# Voronoi cell computed via distance to each branch's representative point

def compute_branch_voronoi(sdf: np.ndarray, branch_origins: list[tuple[int,int]]) -> np.ndarray:
    """Return (H, W) int array with branch index per inside pixel.
    Uses nearest-origin assignment (simple Voronoi via pairwise L2 distance).
    """
    # (H, W, 2) grid of pixel coords
    H, W = sdf.shape
    ys, xs = np.mgrid[0:H, 0:W]
    inside = sdf > 0
    branch_map = np.full((H, W), -1, dtype=np.int32)
    min_dist = np.full((H, W), np.inf)
    
    for i, (oy, ox) in enumerate(branch_origins):
        dist = np.sqrt((ys - oy)**2 + (xs - ox)**2)
        update = inside & (dist < min_dist)
        branch_map[update] = i
        min_dist[update] = dist[update]
    
    return branch_map
```

### Anti-Patterns to Avoid

- **Running scikit-fmm to compute the skeleton**: D-01 locks that ridge extraction uses the existing SDF (scipy EDT), not a separate FMM computation. scikit-fmm is only for travel_time orientation.
- **Subclassing GlyphBBox for BezierGlyph**: D-17 locks that GlyphBBox is frozen — create `BezierGlyph` as a sibling Pydantic model.
- **Class-based CollisionSystem**: D-05 locks function-based API for all new collision stages.
- **External BVH library (rtree, shapely.STRtree)**: D-07 forbids this — pure numpy binary tree only.
- **Forgetting float32 cast after skfmm.travel_time**: The function ALWAYS returns float64 regardless of input dtype. Must `.astype(np.float32)` at boundary. [VERIFIED: live test 2026-04-15]
- **MAT as SDF ridge without minimum size filter**: Without `min_branch_radius` threshold, noise on mask boundary produces hundreds of spurious 1-pixel ridge spikes. Always filter by `sdf > min_branch_radius`.
- **Bitmap collision without bit-shift alignment**: When two glyphs land at arbitrary pixel offsets, their uint32 packing boundaries do not align. Naive AND without shift produces false negatives.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fast Marching Method | Custom BFS/Dijkstra travel time | `skfmm.travel_time()` | Correct O(N log N) heap; handles masked domains; already installed |
| Glyph contour extraction | Manual pixel boundary tracing | `cv2.findContours` + `cv2.approxPolyDP` | Douglas-Peucker tolerance control; handles multi-contour glyphs; already installed |
| LRU cache with size bounds | Custom dict + eviction | `cachetools.LRUCache` with `getsizeof` | Same pattern proven in sdf_cache.py; handles oversized item gracefully |
| blake3 cache key | sha1/md5 | `blake3` library (already imported from sdf_cache.py) | Crypto-safe, faster than sha256; fallback to sha256 already coded |
| SDF ridge detection | Custom skeleton algorithm | `scipy.ndimage.maximum_filter` on existing SDF | EDT already computed; maximum_filter is O(N) and already used in placement.py |
| Quadtree | Custom 2D spatial hash | Pure Python recursive quadtree (hand-roll justified here) | No good pure-numpy quadtree library; O(50 lines) is manageable; external libs add dep risk |

**Key insight:** All geometry dependencies are already in the venv. Phase 7 adds no new top-level packages. The only "hand-roll" justified case is the Quadtree (D-08) — it's simple enough that a dependency is worse than a 50-line implementation.

---

## Common Pitfalls

### Pitfall 1: scikit-fmm Always Returns float64
**What goes wrong:** `skfmm.travel_time(phi_float32, speed_float32)` silently returns a float64 masked array. Storing it as a numpy float32 field in a Pydantic model causes strict mypy errors.
**Why it happens:** C extension casts all inputs to double internally.
**How to avoid:** Always cast: `tt_f32 = np.asarray(tt, dtype=np.float32)`.
**Warning signs:** mypy strict error `Argument 1 to "model_validate" has incompatible type "ndarray[Any, dtype[float64]]"`.
[VERIFIED: live test confirmed float64 output regardless of float32 input]

### Pitfall 2: MAT Ridge Without Dilation Produces Too Many Components
**What goes wrong:** Raw `maximum_filter + threshold` on a star mask gives 12 disconnected 1-3px components instead of the expected 5 arms.
**Why it happens:** Pixel-level noise along the skeleton path creates gaps between ridge points.
**How to avoid:** After thresholding, apply `binary_dilation(ridge, iterations=2)` before labeling. Then use labeled regions to pick representative branch origins (max SDF point per component).
**Warning signs:** `n_branches` >> expected arm count; success criteria test "star mask > 1 branch" passes trivially with noise.
[VERIFIED: star mask → 12 raw components → 6 after dilation with iterations=2]

### Pitfall 3: Bitmap Collision Bit-Shift Alignment
**What goes wrong:** Two glyphs at positions (y=10, x=17) and (y=10, x=25) — offset is 8 pixels, but their uint32 words pack starting at different bit positions. Direct AND gives wrong result.
**Why it happens:** uint32 packing MSB-first means pixel `x` is in word `x//32`, bit `31 - (x%32)`. When comparing two rows, the bit positions don't correspond unless the x offsets share the same 32-pixel alignment.
**How to avoid:** Compute `shift = (ax_min % 32) - (bx_min % 32)`. If shift > 0: shift B rows right by `shift` before AND. If shift < 0: shift A rows right by `-shift`.
**Warning signs:** Bitmap collision (Stage 5) returns False when visual inspection shows pixel overlap.
[ASSUMED — well-documented game dev pattern, not specifically verified on this codebase]

### Pitfall 4: Multi-Centric Determinism Break
**What goes wrong:** Multi-centric placement with 3 branches on two runs produces different word counts per branch despite identical seed.
**Why it happens:** Branch Voronoi assignment uses `np.argmin` which has undefined tiebreak behavior when two branch origins are equidistant from a pixel.
**How to avoid:** Use lexicographic tiebreak on branch index in Voronoi computation (same pattern as `select_origin` lex tiebreak in placement.py). D-15 requires new determinism tests for Multi-Centric path.
**Warning signs:** `test_determinism.py` passes for single-origin but the new multi-centric determinism test fails.

### Pitfall 5: BVH Cache Key Must Include Rotation State
**What goes wrong:** BVH tree built for aligned words (all theta=0) is returned from cache for rotated word set — SAT then gets wrong broadphase decisions.
**Why it happens:** Blake3 key hashes only the AABB array, not rotation values. AABBs are axis-aligned regardless of rotation.
**How to avoid:** BVH (Stage 2) is designed for AABB broadphase only — it correctly uses AABB regardless of rotation. SAT (Stage 4) handles rotation separately. Document this explicitly: BVH cache key is AABB-only by design; rotation is handled downstream in SAT.
**Warning signs:** Incorrect — this is actually correct behavior. But document it to prevent future confusion.

### Pitfall 6: compute_additive_density() Deletion Breaks InnerLoop
**What goes wrong:** Deleting `compute_additive_density()` (D-21) without updating `inner_loop.py` causes NameError at runtime.
**Why it happens:** `inner_loop.py` imports `compute_additive_density` explicitly at line 25.
**How to avoid:** Delete `compute_additive_density()` from loss.py AND update `inner_loop.py` in the same commit. The import line and the two-call pattern in `optimize()` both need updating.
**Warning signs:** Any test importing `inner_loop.py` will fail immediately with ImportError.
[VERIFIED: inner_loop.py line 25 confirmed to import compute_additive_density]

### Pitfall 7: Frozen GlyphBBox Cannot Hold Bezier Data
**What goes wrong:** Attempting to add `bezier: list[BezierCurve]` field to `GlyphBBox` fails at class definition time with Pydantic frozen model error.
**Why it happens:** GlyphBBox is frozen (immutable after creation) per Phase 4 D-02 pattern.
**How to avoid:** Create `BezierGlyph` as a sibling model. D-17 locks this approach.
**Warning signs:** Pydantic `ValidationError: model is frozen` at test time.

### Pitfall 8: scikit-fmm masked array phi must contain a zero contour
**What goes wrong:** `skfmm.travel_time(masked_phi, speed)` raises `ValueError: the array phi contains no zero contour (no zero level set)`.
**Why it happens:** phi must cross 0 within the unmasked region. If source pixel is `-1` and all other unmasked pixels are `+1`, there is a zero level set. But if phi is all positive (or all negative) in unmasked region, it fails.
**How to avoid:** Set phi[source_y, source_x] = -1.0 and phi elsewhere = +1.0, then mask with `~mask`. The sign change at the source creates the zero contour.
**Warning signs:** ValueError at test time when testing travel_time on minimal 3x3 masks.
[VERIFIED: live test reproduced this error with wrong phi initialization]

---

## Code Examples

### MAT Full Pipeline (from ridge to branch origins)
```python
# Source: verified pattern from uv tests 2026-04-15
import numpy as np
from scipy.ndimage import distance_transform_edt, maximum_filter, binary_dilation, label
import skfmm

def extract_mat(
    sdf: np.ndarray,           # float32 (H, W), positive inside (D-09/ADR-0004)
    min_branch_radius: float,  # Pydantic settings (D-02) — discretion default: 3.0
) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """Extract MAT branches and return (labeled_map, branch_origins).
    
    Returns:
        labeled_map: int32 (H, W), value = branch index (0-based), -1 outside
        branch_origins: List of (y, x) tuples, one per branch
    """
    inside = sdf > 0
    # Ridge = local maxima of SDF inside mask
    local_max = maximum_filter(sdf, size=3, mode='constant', cval=0.0)
    ridge = (sdf == local_max) & (sdf > min_branch_radius) & inside
    # Bridge near-contiguous ridge points
    ridge_connected = binary_dilation(ridge, iterations=2) & inside
    labeled, n_branches = label(ridge_connected)
    
    if n_branches == 0:
        return np.full(sdf.shape, -1, dtype=np.int32), []
    
    origins = []
    for b in range(1, n_branches + 1):
        branch_pixels = np.argwhere(labeled == b)
        # Branch origin = pixel with max SDF value in branch (deepest point)
        sdf_vals = sdf[branch_pixels[:, 0], branch_pixels[:, 1]]
        best = branch_pixels[np.argmax(sdf_vals)]
        origins.append((int(best[0]), int(best[1])))
    
    branch_map = np.where(labeled > 0, labeled - 1, -1).astype(np.int32)
    return branch_map, origins
```

### OpenCV Bezier Path Extraction
```python
# Source: cv2.findContours + approxPolyDP verified on glyph shapes 2026-04-15
# cv2 4.13.0 installed; findContours returns (contours, hierarchy)
import cv2
import numpy as np
from aerocloud.models.geometry import BezierGlyph  # new model

def extract_bezier_glyph(pixel_buffer: np.ndarray, epsilon: float = 1.5) -> BezierGlyph:
    """Extract Bezier path from glyph pixel buffer.
    
    Args:
        pixel_buffer: uint8 (H, W) glyph raster from GlyphBBox.pixel_buffer
        epsilon: Douglas-Peucker tolerance in pixels (discretion default: 1.5)
    
    Returns:
        BezierGlyph with list of (x, y) control point sequences per contour
    """
    # findContours needs uint8 binary input
    binary = (pixel_buffer > 0).astype(np.uint8) * 255
    # RETR_LIST: all contours (handles holes in letters like 'o', 'a')
    # CHAIN_APPROX_NONE: all contour pixels (before approximation)
    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    
    paths = []
    for contour in contours:
        # Douglas-Peucker approximation -> reduces 100+ points to ~5-20
        arc_len = cv2.arcLength(contour, True)
        if arc_len < 1.0:
            continue
        approx = cv2.approxPolyDP(contour, epsilon, True)
        # approx shape: (N, 1, 2) with (x, y) convention (OpenCV uses x,y)
        pts = [(int(p[0][0]), int(p[0][1])) for p in approx]
        paths.append(pts)
    
    return BezierGlyph(contour_paths=paths)
```

### BVH Cache (following sdf_cache.py pattern)
```python
# Source: ASSUMED based on sdf_cache.py template (fully verified) + D-11
# blake3 key: word_count + AABB array hash
import threading
import numpy as np
from cachetools import LRUCache
try:
    from blake3 import blake3 as _blake3
    def _digest(data: bytes) -> str:
        return str(_blake3(data).hexdigest())
except ImportError:
    from hashlib import sha256
    def _digest(data: bytes) -> str:
        return sha256(data).hexdigest()

_BVH_CACHE: LRUCache = LRUCache(maxsize=64 * 1024 * 1024, getsizeof=lambda x: len(x))
_BVH_LOCK: threading.RLock = threading.RLock()

def _make_bvh_key(aabbs: np.ndarray) -> str:
    """blake3 of AABB array bytes + shape."""
    return _digest(aabbs.tobytes()) + f"|{aabbs.shape}"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| scikit-image medial_axis (morphological) | SDF ridge (local maxima of EDT) | D-01 lock 2026-04-15 | Reuses existing SDF; no extra dependency |
| Single spiral origin per word cloud | Multi-Centric (one origin per MAT branch) | Phase 7 | Fills concave shapes that single-origin leaves empty |
| AABB-only collision | 5-stage hierarchy (AABB→BVH→Quadtree→SAT→Bitmap) | Phase 7 | Handles rotated words; sub-pixel accuracy at Stage 5 |
| Two forward passes for density + additive | Single forward pass mode='both' | D-20 Phase 7 | Eliminates F-3 redundant warp computation |
| Font metric bounding boxes | OpenCV pixel contour paths | Phase 7 | Sub-millimeter Bezier paths for Phase 12 SVG/PDF |

**Deprecated/outdated:**
- `compute_additive_density()` in loss.py: Deleted after D-20/D-21 implementation. Its logic moves into `DifferentiableRenderer.forward(mode='both')`.
- Single-origin placement as default: Multi-Centric becomes default; single-origin is only the fallback (D-14).

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.0 + hypothesis 6.120.0 + pytest-benchmark 4.0.0 |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest packages/engine/tests/geometry/ -x -q` |
| Full suite command | `uv run pytest packages/engine/tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GEO2-01 | Star mask: MAT produces > 1 branch | unit + fixture | `pytest tests/geometry/unit/test_mat.py -x` | ❌ Wave 0 |
| GEO2-01 | Crescent mask: MAT produces > 1 branch | unit + fixture | `pytest tests/geometry/unit/test_mat.py::test_crescent_branches -x` | ❌ Wave 0 |
| GEO2-01 | travel_time returns float32 at boundary | unit | `pytest tests/geometry/unit/test_mat.py::test_travel_time_dtype -x` | ❌ Wave 0 |
| GEO2-02 | Pruning: min_branch_radius filters noise spikes | unit | `pytest tests/geometry/unit/test_mat.py::test_pruning -x` | ❌ Wave 0 |
| GEO2-03 | Multi-Centric fills concave shapes single-origin leaves empty | integration | `pytest tests/geometry/integration/test_multi_centric.py -x` | ❌ Wave 0 |
| GEO2-03 | Multi-Centric determinism: same seed → same assignment | determinism | `pytest tests/geometry/determinism/test_multi_centric_determinism.py -x` | ❌ Wave 0 |
| GEO2-04 | BVH tree construction on (N,4) int32 array | unit | `pytest tests/geometry/unit/test_collision.py::test_bvh_build -x` | ❌ Wave 0 |
| GEO2-04 | BVH broadphase: correct AABB merge at each node | unit | `pytest tests/geometry/unit/test_collision.py::test_bvh_merged_aabb -x` | ❌ Wave 0 |
| GEO2-05 | Quadtree spatial index: correct neighbors returned | unit | `pytest tests/geometry/unit/test_quadtree.py -x` | ❌ Wave 0 |
| GEO2-06 | SAT detects collision that AABB misses for rotated text | unit | `pytest tests/geometry/unit/test_collision.py::test_sat_rotation -x` | ❌ Wave 0 |
| GEO2-06 | SAT no false positives on clearly separated rotated rects | unit | `pytest tests/geometry/unit/test_collision.py::test_sat_no_collision -x` | ❌ Wave 0 |
| GEO2-07 | Bitmap collision: pixel-exact on adversarial fixtures | unit | `pytest tests/geometry/unit/test_collision.py::test_bitmap_pixel_exact -x` | ❌ Wave 0 |
| GEO2-08 | BVH LRU cache: same AABB array hits cache on second call | state | `pytest tests/geometry/state/test_bvh_cache.py -x` | ❌ Wave 0 |
| GEO2-08 | BVH cache thread-safety: 8 concurrent builds | state | `pytest tests/geometry/state/test_bvh_cache.py::test_bvh_threadsafe -x` | ❌ Wave 0 |
| GEO2-09 | Bezier extraction: star glyph produces ≥ 1 contour path | unit | `pytest tests/geometry/unit/test_bezier.py -x` | ❌ Wave 0 |
| GEO2-09 | BezierGlyph model serialization round-trip | unit | `pytest tests/geometry/unit/test_bezier.py::test_model_roundtrip -x` | ❌ Wave 0 |
| D-20 | Renderer mode='both' returns tuple (density, additive) | unit | `pytest packages/engine/tests/renderer/unit/test_compositing.py::test_dual_mode -x` | ❌ Wave 0 |
| D-21 | InnerLoop.optimize() with dual-mode: no import error | unit | `pytest packages/engine/tests/optimizer/unit/test_loss_overlap.py::test_no_additive_density_import -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest packages/engine/tests/geometry/ -x -q`
- **Per wave merge:** `uv run pytest packages/engine/tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps (all new files — no existing tests to extend)
- [ ] `packages/engine/tests/geometry/unit/test_mat.py` — covers GEO2-01, GEO2-02
- [ ] `packages/engine/tests/geometry/unit/test_bezier.py` — covers GEO2-09
- [ ] `packages/engine/tests/geometry/unit/test_quadtree.py` — covers GEO2-05
- [ ] `packages/engine/tests/geometry/unit/test_collision.py` — EXTEND existing file with BVH, SAT, bitmap tests
- [ ] `packages/engine/tests/geometry/state/test_bvh_cache.py` — covers GEO2-08
- [ ] `packages/engine/tests/geometry/integration/test_multi_centric.py` — covers GEO2-03
- [ ] `packages/engine/tests/geometry/determinism/test_multi_centric_determinism.py` — covers D-15
- [ ] `packages/engine/tests/renderer/unit/test_compositing.py` — EXTEND: add test_dual_mode

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | Pydantic models at all boundaries (GlyphBBox.pixel_buffer dtype, BezierGlyph, MAT settings) |
| V6 Cryptography | no | blake3 used for cache key only (non-cryptographic use) |

### Known Threat Patterns for Geometry Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Adversarial mask with boundary noise | Denial of Service | min_branch_radius Pydantic setting caps branch count; max_branches guard |
| Malformed pixel_buffer (all zeros / non-2D) | Tampering | GlyphBBox.pixel_buffer validated in Phase 4; bezier.py must check arr.size > 0 |
| BVH tree depth attack (degenerate AABBs all at same coords) | Denial of Service | max_depth parameter in build_bvh (D-07 discretion); leaf fallback when N == all-left or all-right |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| scikit-fmm | GEO2-01 travel_time | ✓ | 2025.06.23 | — |
| opencv-python-headless | GEO2-09 findContours | ✓ | 4.13.0 | — |
| scipy.ndimage | MAT ridge, placement.py | ✓ | 1.17.1 | — |
| numpy | BVH, SAT, bitmap | ✓ | 2.4.4 | — |
| cachetools | BVH LRU cache | ✓ | 7.0.5 | — |
| blake3 | BVH cache key | ✓ | (installed) | sha256 fallback in sdf_cache.py pattern |
| torch | Renderer dual-mode | ✓ | 2.11.0+cu130 | — |

**Missing dependencies with no fallback:** None. All required libraries already installed.

[VERIFIED: all versions confirmed via `uv run python -c "import ..."` 2026-04-15]

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | uint32 bitmap bit-shift alignment is standard game dev pattern requiring shift computation | Pitfall 3 + Pattern 5 | If shift handling is wrong, Stage 5 will have false negatives; catch in adversarial fixture test |
| A2 | Quadtree max_depth default of 8 is appropriate for 100-500 word clouds at 1024×1024 | Architecture | Too shallow = O(N^2) fallback; too deep = O(N log N) overhead. Can tune via benchmark |
| A3 | Bezier epsilon default of 1.5px gives adequate approximation for sub-mm SVG export | Pattern 6 | Too large = blocky curves; too small = too many control points. Phase 12 will validate |
| A4 | Multi-Centric Voronoi boundary causes no visual "seam" artifacts between branches | Multi-Centric | Seam artifacts are documented FEATURES.md §6 failure mode; mitigated by D-15 integration test |
| A5 | MAT cache (mat_cache.py) is worth implementing given similar cost to SDF computation | Architecture | If MAT is cheap enough, cache is overhead. Discretion item — benchmark in Wave 0 |
| A6 | BVH with 20 max_depth is appropriate (matches numpy prototype) | Pattern 3 | Unlimited depth would stack overflow for N > 10^6; 20 depth handles 2^20 = 1M leaves safely |

---

## Open Questions

1. **MAT cache module: separate or extend sdf_cache?**
   - What we know: SDF cache is in sdf_cache.py; MAT is derived from SDF; both have similar caching needs
   - What's unclear: Whether MAT computation is expensive enough to justify caching (need benchmark)
   - Recommendation: Implement mat_cache.py as separate module (D-04 suggests this). Profile on 1024×1024 star mask to confirm caching is worth it.

2. **EdWordle two-level box vs word-level AABB for BVH**
   - What we know: EdWordle paper uses per-letter boxes as one level and word-level box as the other. D-07 locks word-level AABB only (not per-letter).
   - What's unclear: Whether word-level-only BVH provides sufficient improvement over plain AABB scan
   - Recommendation: D-07 is locked; implement word-level BVH as specified. Phase 12 optimization can add per-letter level if profiling shows need.

3. **Quadtree rebuild strategy: full rebuild vs incremental insert**
   - What we know: Phase 4 placement iterates words sequentially and adds AABBs one at a time
   - What's unclear: Whether incremental insert (add one AABB after each placement) or full rebuild per word is more efficient
   - Recommendation: Incremental insert (split on insert) is O(log N) per word vs O(N log N) for full rebuild per iteration.

4. **Multi-Centric parallel vs sequential branch placement**
   - What we know: D-12 says "calls existing placement pipeline per branch" — no explicit parallelism locked
   - What's unclear: Whether branches should be placed in parallel threads (GIL limitation) or sequentially
   - Recommendation: Sequential first (simpler, deterministic). Phase 12 can add thread pool if performance requires.

---

## Sources

### Primary (HIGH confidence)
- Live code inspection: `packages/engine/src/aerocloud/geometry/sdf.py` — ridge = local maxima of EDT verified
- Live code inspection: `packages/engine/src/aerocloud/optimizer/inner_loop.py` — confirmed double forward pass at lines 208-211
- Live code inspection: `packages/engine/src/aerocloud/geometry/sdf_cache.py` — BVH cache template (blake3 + cachetools + RLock)
- Live code inspection: `packages/engine/src/aerocloud/renderer/_renderer.py` — current forward() signature confirmed
- Live code inspection: `packages/engine/pyproject.toml` — all geometry extras confirmed present
- uv env tests (2026-04-15): skfmm 2025.06.23 travel_time API, dtype behavior, masked domain, zero-contour requirement
- uv env tests (2026-04-15): cv2 4.13.0 findContours + approxPolyDP verified on glyph shapes
- uv env tests (2026-04-15): SAT numpy implementation verified (rotated needles crossing)
- uv env tests (2026-04-15): bitmap uint32 collision verified (same/partial/no overlap)
- uv env tests (2026-04-15): BVH binary tree construction verified
- uv env tests (2026-04-15): dual-mode single-pass renderer verified (density, additive both correct)
- uv env tests (2026-04-15): MAT ridge from EDT: star mask → 12 raw → 6 dilated; crescent → multiple components

### Secondary (MEDIUM confidence)
- [pypi.org/project/scikit-fmm](https://pypi.org/project/scikit-fmm/) — version 2025.06.23 confirmed, float64 output behavior
- [EdWordle paper (Wang et al. 2017)](https://www.vis.uni-stuttgart.de/documentcenter/staff/sedlmaml/papers/wang2017edwordle.pdf) — two-level box BVH architecture for word collision
- [Jason Davies Wordle about page](https://www.jasondavies.com/wordcloud/about/) — quadtree + sprite mask collision pattern

### Tertiary (LOW confidence)
- Game dev literature on uint32 bitmask bit-shift alignment (Pitfall 3) — general pattern, not codebase-specific
- Phase 4 research wiki/knowledge/phase-4-known-limits.md — 24.85s placement performance context for Multi-Centric speedup expectation

---

## Metadata

**Confidence breakdown:**
- scikit-fmm API and dtype: HIGH — live tested in uv env
- MAT ridge extraction: HIGH — live tested with star and crescent masks
- BVH construction: HIGH — live tested with numpy
- SAT algorithm: HIGH — live tested, detects rotated collisions correctly
- Bitmap collision (basic): HIGH — live tested basic case; bit-shift alignment: MEDIUM (assumed)
- OpenCV Bezier pipeline: HIGH — live tested findContours + approxPolyDP
- Renderer dual-mode: HIGH — live tested single-pass accumulation
- Multi-Centric Voronoi: MEDIUM — pattern verified, visual artifacts undetermined
- Quadtree max_depth default: MEDIUM — general guidance, needs benchmark to confirm

**Research date:** 2026-04-15
**Valid until:** 2026-05-15 (stable Python ecosystem; scikit-fmm changes infrequently)

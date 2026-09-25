# wiki/code/outer-loop-metrics.md — Quality Metrics

**Phase:** 09-outer-loop-v1
**Module:** `packages/engine/src/aerocloud/outer_loop/metrics.py`
**Implements:** 7 quality metric functions (D-05 geometric + D-06 semantic + D-07 aggregator)

---

## Overview

Pure numpy/scipy functions computing quality signals from a rendered word cloud layout. All return `float` in `[0.0, 1.0]`. NaN/Inf inputs are caught per T-09-04; degenerate geometry is caught per T-09-03.

All functions are **pure** — no side effects, no I/O, safe for concurrent evaluation.

---

## Geometric Metrics (D-05)

### compute_lc(density, sdf_mask) -> float

**Layout Coverage** — ratio of ink pixels inside silhouette to silhouette area.

```
LC = sum(density[sdf_mask] > 0) / sum(sdf_mask)
```

| Param | Type | Description |
|-------|------|-------------|
| `density` | `np.ndarray (H, W)` | Ink intensity per pixel, values in [0, 1] |
| `sdf_mask` | `np.ndarray (H, W) bool` | True = inside silhouette |

Returns 0.0 if silhouette area is 0.

### compute_lu(density, sdf_mask, k=8) -> float

**Layout Uniformity** — 1 - normalized std dev of local density.

```
Subdivide into K x K cells.
For each cell overlapping the mask: compute mean density.
LU = 1 - std(cell_densities) / (max - min + eps)
```

| Param | Type | Description |
|-------|------|-------------|
| `density` | `np.ndarray (H, W)` | Ink intensity |
| `sdf_mask` | `np.ndarray (H, W) bool` | Silhouette mask |
| `k` | `int` | Grid subdivision count per dimension (default 8) |

Returns 1.0 if fewer than 2 cells overlap the mask (perfectly uniform by definition).

### compute_ss(density, sdf_mask) -> float

**Space Saving** — fraction of silhouette interior covered by ink.

```
whitespace = sum((sdf_mask > 0) & (density <= 0))
SS = 1 - whitespace / sum(sdf_mask)
```

Note: LC and SS differ — LC counts ink pixels, SS measures absence of whitespace. They are equal only when density is binary.

### compute_compactness(word_positions_yx, word_sizes) -> float

**Compactness** — isoperimetric quotient of placed word bounding hull.

```
Build AABB corners for all words (4 corners per word).
hull = ConvexHull(corners)
C = 4 * pi * hull.volume / hull.area^2
```

| Param | Type | Description |
|-------|------|-------------|
| `word_positions_yx` | `np.ndarray (N, 2)` | Word centres (y, x) |
| `word_sizes` | `np.ndarray (N, 2)` | Bounding boxes (height, width) |

**Degenerate guards (T-09-03):**
- Returns 0.0 if `< 3 unique corner points`
- Returns 0.0 on `QhullError` (collinear points)
- Returns 0.0 if perimeter < 1e-12

**scipy convention:** In 2D, `ConvexHull.volume = polygon area`, `ConvexHull.area = perimeter`.

### compute_aspect_ratio(bbox_width, bbox_height) -> float

**Aspect Ratio** — proximity of layout bounding box to the golden ratio.

```
phi = 1.618
actual = max(w, h) / min(w, h)
AR = clamp(1 - |actual - phi| / phi, 0, 1)
```

Returns 0.0 if either dimension is < 1e-12.

---

## Semantic Metrics (D-06)

### compute_realized_adjacencies(cosine_sim_matrix, positions_yx, sizes, sim_threshold=0.7) -> float

**Realized Adjacencies** — fraction of semantically similar word pairs that are spatially adjacent.

```
similar_pairs = pairs where cosine_sim > sim_threshold
adjacent = similar pairs where AABB gap_y <= 0 AND gap_x <= 0
RA = adjacent / similar_pairs
```

Returns 0.0 if no similar pairs exist.

**AABB adjacency:** Computed as gap in both axes (y and x independently):
```
gap_y = |y_i - y_j| - (half_h_i + half_h_j)
gap_x = |x_i - x_j| - (half_w_i + half_w_j)
adjacent iff gap_y <= 0 AND gap_x <= 0
```

| Param | Type | Description |
|-------|------|-------------|
| `cosine_sim_matrix` | `np.ndarray (N, N)` | Pairwise cosine similarities |
| `positions_yx` | `np.ndarray (N, 2)` | Word centres (y, x) |
| `sizes` | `np.ndarray (N, 2)` | Bounding boxes (h, w) |
| `sim_threshold` | `float` | Similarity cutoff for "semantically similar" (default 0.7) |

### compute_distortion(positions_yx, embeddings) -> float

**Distortion Score** — consistency of spatial/embedding distance ratios.

```
For all pairs i<j:
    ratio_ij = spatial_dist_ij / (embedding_dist_ij + eps)
cv = std(ratios) / (mean(ratios) + eps)   # coefficient of variation
score = 1 - clamp(cv, 0, 1)
```

- Perfect proportionality (all ratios equal) → CV = 0 → score = 1.0
- Scrambled positions → high ratio variance → CV ≈ 1 → score ≈ 0.0

**Note on formula:** The plan spec suggested `score = 1 - mean/max` which is semantically inverted (0.0 for perfect proportionality). The CV formula is the correct interpretation of D-06 "low distortion = good". (Auto-fixed bug in Plan 09-02.)

Returns 1.0 if fewer than 2 words.

---

## Aggregator (D-07)

### compute_all_metrics(...) -> QualityMetrics

```python
def compute_all_metrics(
    density: np.ndarray,
    sdf_mask: np.ndarray,
    positions_yx: np.ndarray,
    sizes: np.ndarray,
    embeddings: np.ndarray,
    cosine_sim_matrix: np.ndarray,
    bbox_width: float,
    bbox_height: float,
) -> QualityMetrics
```

Computes all 7 metrics and returns a `QualityMetrics` Pydantic model. Delegates to the 7 individual functions above.

---

## NaN/Inf Guard (T-09-04)

All metric functions check for NaN/Inf at entry:
```python
def _has_nan(arr: np.ndarray) -> bool:
    return bool(np.any(~np.isfinite(arr)))
```
If any NaN/Inf detected: log `structlog.warning` + return 0.0.

---

## Models

### QualityMetrics (Pydantic)

```python
class QualityMetrics(AeroCloudBase):
    layout_coverage: float       # [0, 1]
    layout_uniformity: float     # [0, 1]
    space_saving: float          # [0, 1]
    compactness: float           # [0, 1]
    aspect_ratio: float          # [0, 1]
    realized_adjacencies: float  # [0, 1]
    distortion_score: float      # [0, 1]

    def combined_fitness(self, weights: QualityWeights) -> float
```

### QualityWeights (Pydantic)

```python
class QualityWeights(AeroCloudBase):
    w_lc: float = 1/7
    w_lu: float = 1/7
    w_ss: float = 1/7
    w_compactness: float = 1/7
    w_ar: float = 1/7
    w_ra: float = 1/7
    w_distortion: float = 1/7
```

Default: equal weights (1/7 each). Combined fitness = weighted sum (unnormalized, may exceed 1.0).

---

## Threat Register

| ID | Category | Status |
|----|----------|--------|
| T-09-03 | DoS (degenerate ConvexHull) | Mitigated — < 3 unique pts returns 0.0, QhullError returns 0.0 |
| T-09-04 | NaN propagation | Mitigated — _has_nan() guard at top of every function |

---

*Module: packages/engine/src/aerocloud/outer_loop/metrics.py*
*Phase: 09-outer-loop-v1*
*Updated: 2026-04-18*

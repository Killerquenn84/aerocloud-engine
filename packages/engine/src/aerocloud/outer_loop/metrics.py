"""Quality metrics computation for the Outer Loop (MAP-Elites) subsystem.

Implements all 7 quality/semantic metric functions:
- 5 geometric: LC, LU, SS, Compactness, Aspect Ratio  (D-05)
- 2 semantic: Realized Adjacencies, Distortion         (D-06)
- 1 aggregator: compute_all_metrics → QualityMetrics   (D-07)

All metric functions return float in [0.0, 1.0].
NaN/Inf inputs are caught and return 0.0 with a structlog warning (T-09-04).
ConvexHull degenerate cases return 0.0 (T-09-03).

References:
    - .planning/phases/09-outer-loop-v1/09-02-PLAN.md
    - D-05, D-06, D-07 in 09-RESEARCH.md
"""

from __future__ import annotations

import math

import numpy as np
import structlog
from scipy.spatial import ConvexHull, QhullError

from aerocloud.outer_loop.models import QualityMetrics

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_PHI = 1.618  # golden ratio


def _has_nan(arr: np.ndarray) -> bool:
    """Return True if array contains any NaN or Inf value."""
    return bool(np.any(~np.isfinite(arr)))


# ---------------------------------------------------------------------------
# Geometric metrics (D-05)
# ---------------------------------------------------------------------------


def compute_lc(density: np.ndarray, sdf_mask: np.ndarray) -> float:
    """Layout Coverage: ratio of ink pixels inside silhouette to silhouette area.

    Formula (D-05):
        LC = sum(density[sdf_mask] > 0) / sum(sdf_mask)

    Args:
        density:  2-D float array (H, W), values in [0, 1]. Ink intensity.
        sdf_mask: 2-D bool array (H, W). True = inside silhouette.

    Returns:
        LC in [0.0, 1.0].
    """
    if _has_nan(density):
        log.warning("compute_lc: NaN/Inf in density, returning 0.0")
        return 0.0

    silhouette_area = float(np.sum(sdf_mask))
    if silhouette_area == 0.0:
        return 0.0

    ink_pixels = float(np.sum(density[sdf_mask] > 0))
    return float(np.clip(ink_pixels / silhouette_area, 0.0, 1.0))


def compute_lu(
    density: np.ndarray,
    sdf_mask: np.ndarray,
    k: int = 8,
) -> float:
    """Layout Uniformity: 1 - normalised std-dev of local density.

    Formula (D-05):
        Subdivide into K x K cells. For each cell overlapping the mask, compute
        mean density. LU = 1 - std(cell_densities) / (max - min + eps).

    Args:
        density:  2-D float array (H, W).
        sdf_mask: 2-D bool array (H, W). True = inside silhouette.
        k:        Grid subdivision count per dimension.

    Returns:
        LU in [0.0, 1.0].
    """
    if _has_nan(density):
        log.warning("compute_lu: NaN/Inf in density, returning 0.0")
        return 0.0

    h, w = density.shape
    cell_densities: list[float] = []

    row_edges = np.linspace(0, h, k + 1, dtype=int)
    col_edges = np.linspace(0, w, k + 1, dtype=int)

    for r in range(k):
        for c in range(k):
            r0, r1 = int(row_edges[r]), int(row_edges[r + 1])
            c0, c1 = int(col_edges[c]), int(col_edges[c + 1])
            cell_mask = sdf_mask[r0:r1, c0:c1]
            if not np.any(cell_mask):
                continue  # cell does not overlap silhouette
            cell_densities.append(float(np.mean(density[r0:r1, c0:c1][cell_mask])))

    if len(cell_densities) < 2:
        # Only one (or zero) valid cells — perfectly "uniform" by definition
        return 1.0

    arr = np.array(cell_densities, dtype=float)
    span = float(arr.max() - arr.min()) + 1e-8
    lu = 1.0 - float(arr.std()) / span
    return float(np.clip(lu, 0.0, 1.0))


def compute_ss(density: np.ndarray, sdf_mask: np.ndarray) -> float:
    """Space Saving: 1 - (whitespace inside silhouette / silhouette area).

    Formula (D-05):
        SS = 1 - (sum((sdf_mask > 0) & (density <= 0)) / sum(sdf_mask))

    Whitespace = silhouette pixels with zero ink (density <= 0).

    Args:
        density:  2-D float array (H, W).
        sdf_mask: 2-D bool array (H, W).

    Returns:
        SS in [0.0, 1.0].
    """
    if _has_nan(density):
        log.warning("compute_ss: NaN/Inf in density, returning 0.0")
        return 0.0

    silhouette_area = float(np.sum(sdf_mask))
    if silhouette_area == 0.0:
        return 0.0

    whitespace = float(np.sum(sdf_mask & (density <= 0.0)))
    ss = 1.0 - whitespace / silhouette_area
    return float(np.clip(ss, 0.0, 1.0))


def compute_compactness(
    word_positions_yx: np.ndarray,
    word_sizes: np.ndarray,
) -> float:
    """Compactness: isoperimetric quotient of placed-word bounding hull.

    Formula (D-05):
        Build bounding box corners from (y, x) positions + (h, w) sizes.
        Compute convex hull. C = 4*pi * area / perimeter^2.

    Degenerate cases (< 3 unique points) return 0.0 (T-09-03).

    Args:
        word_positions_yx: (N, 2) float — word centres (y, x).
        word_sizes:        (N, 2) float — bounding box (height, width).

    Returns:
        Compactness in [0.0, 1.0].
    """
    n = word_positions_yx.shape[0]
    if n < 1:
        return 0.0

    # Build corner points for each word's AABB
    # Each word contributes 4 corners
    half = word_sizes / 2.0
    corners: list[list[float]] = []
    for i in range(n):
        cy, cx = float(word_positions_yx[i, 0]), float(word_positions_yx[i, 1])
        hy, hx = float(half[i, 0]), float(half[i, 1])
        corners.extend(
            [
                [cy - hy, cx - hx],
                [cy - hy, cx + hx],
                [cy + hy, cx - hx],
                [cy + hy, cx + hx],
            ]
        )
    pts = np.array(corners, dtype=float)

    # Need at least 3 unique non-collinear points for ConvexHull
    unique_pts = np.unique(pts, axis=0)
    if unique_pts.shape[0] < 3:
        return 0.0

    try:
        hull = ConvexHull(pts)
    except QhullError:
        log.warning("compute_compactness: degenerate hull (collinear points), returning 0.0")
        return 0.0

    # In 2D scipy ConvexHull: hull.volume = polygon area, hull.area = perimeter
    area = hull.volume
    perimeter = hull.area
    if perimeter < 1e-12:
        return 0.0

    compactness = 4.0 * math.pi * area / (perimeter**2)
    return float(np.clip(compactness, 0.0, 1.0))


def compute_aspect_ratio(bbox_width: float, bbox_height: float) -> float:
    """Aspect Ratio proximity to golden ratio.

    Formula (D-05):
        phi = 1.618
        actual = max(w, h) / min(w, h)
        AR = clamp(1 - |actual - phi| / phi, 0, 1)

    Args:
        bbox_width:  Layout bounding box width.
        bbox_height: Layout bounding box height.

    Returns:
        AR in [0.0, 1.0].
    """
    min_dim = min(abs(bbox_width), abs(bbox_height))
    if min_dim < 1e-12:
        return 0.0

    actual = max(abs(bbox_width), abs(bbox_height)) / min_dim
    ar = 1.0 - abs(actual - _PHI) / _PHI
    return float(np.clip(ar, 0.0, 1.0))


# ---------------------------------------------------------------------------
# Semantic metrics (D-06)
# ---------------------------------------------------------------------------


def compute_realized_adjacencies(
    cosine_sim_matrix: np.ndarray,
    positions_yx: np.ndarray,
    sizes: np.ndarray,
    sim_threshold: float = 0.7,
) -> float:
    """Realized Adjacencies: fraction of similar word pairs that are adjacent.

    Formula (D-06):
        "Semantically similar" pairs: cosine_sim > sim_threshold.
        "Spatially adjacent" pairs: AABB overlap or gap <= 0.
        RA = similar_and_adjacent / similar_pairs.
        Returns 0.0 if no similar pairs exist.

    Args:
        cosine_sim_matrix: (N, N) float — pairwise cosine similarities.
        positions_yx:      (N, 2) float — word centres (y, x).
        sizes:             (N, 2) float — bounding box (height, width).
        sim_threshold:     Similarity cutoff for "semantically similar".

    Returns:
        RA in [0.0, 1.0].
    """
    n = positions_yx.shape[0]
    if n < 2:
        return 0.0

    half = sizes / 2.0

    similar_count = 0
    adjacent_and_similar = 0

    for i in range(n):
        for j in range(i + 1, n):
            if cosine_sim_matrix[i, j] <= sim_threshold:
                continue
            similar_count += 1

            # Check AABB overlap/touch: gap <= 0 in both axes
            # y-axis
            gap_y = abs(positions_yx[i, 0] - positions_yx[j, 0]) - (half[i, 0] + half[j, 0])
            # x-axis
            gap_x = abs(positions_yx[i, 1] - positions_yx[j, 1]) - (half[i, 1] + half[j, 1])
            if gap_y <= 0.0 and gap_x <= 0.0:
                adjacent_and_similar += 1

    if similar_count == 0:
        return 0.0

    return float(np.clip(adjacent_and_similar / similar_count, 0.0, 1.0))


def compute_distortion(
    positions_yx: np.ndarray,
    embeddings: np.ndarray,
) -> float:
    """Distortion score: consistency of spatial/embedding distance ratios.

    A layout has low distortion when spatial distances between words are
    proportional to their embedding distances (i.e., semantically similar
    words are placed close together, dissimilar words far apart).

    Formula (D-06, interpreted):
        For all pairs i<j:
            ratio_ij = spatial_dist_ij / (embedding_dist_ij + eps)
        distortion = coefficient of variation = std(ratios) / (mean(ratios) + eps)
        score = 1 - clamp(distortion, 0, 1)

    Perfect proportionality → all ratios equal → CV = 0 → score = 1.0.
    Scrambled positions → high ratio variance → CV → 1+ → score = 0.0.

    Returns 1.0 if fewer than 2 words (no pairs to compare).

    Args:
        positions_yx: (N, 2) float — word centres (y, x).
        embeddings:   (N, D) float — word embedding vectors.

    Returns:
        distortion_score in [0.0, 1.0].
    """
    n = positions_yx.shape[0]
    if n < 2:
        return 1.0

    ratios: list[float] = []
    for i in range(n):
        for j in range(i + 1, n):
            spatial_dist = float(np.linalg.norm(positions_yx[i] - positions_yx[j]))
            emb_dist = float(np.linalg.norm(embeddings[i] - embeddings[j]))
            ratio = spatial_dist / (emb_dist + 1e-8)
            ratios.append(ratio)

    arr = np.array(ratios, dtype=float)
    mean_r = float(arr.mean()) + 1e-8
    cv = float(arr.std()) / mean_r  # coefficient of variation
    score = 1.0 - float(np.clip(cv, 0.0, 1.0))
    return float(np.clip(score, 0.0, 1.0))


# ---------------------------------------------------------------------------
# Aggregator (D-07)
# ---------------------------------------------------------------------------


def compute_all_metrics(
    density: np.ndarray,
    sdf_mask: np.ndarray,
    positions_yx: np.ndarray,
    sizes: np.ndarray,
    embeddings: np.ndarray,
    cosine_sim_matrix: np.ndarray,
    bbox_width: float,
    bbox_height: float,
) -> QualityMetrics:
    """Compute all 7 quality metrics and return a QualityMetrics instance.

    Args:
        density:           2-D float array (H, W) — ink density.
        sdf_mask:          2-D bool array (H, W) — silhouette mask.
        positions_yx:      (N, 2) float — word centres (y, x).
        sizes:             (N, 2) float — word bounding boxes (h, w).
        embeddings:        (N, D) float — word embeddings.
        cosine_sim_matrix: (N, N) float — pairwise cosine similarities.
        bbox_width:        Layout bounding box width (for aspect ratio).
        bbox_height:       Layout bounding box height (for aspect ratio).

    Returns:
        QualityMetrics with all 7 fields populated.
    """
    lc = compute_lc(density, sdf_mask)
    lu = compute_lu(density, sdf_mask)
    ss = compute_ss(density, sdf_mask)
    compactness = compute_compactness(positions_yx, sizes)
    ar = compute_aspect_ratio(bbox_width, bbox_height)
    ra = compute_realized_adjacencies(cosine_sim_matrix, positions_yx, sizes)
    distortion = compute_distortion(positions_yx, embeddings)

    return QualityMetrics(
        layout_coverage=lc,
        layout_uniformity=lu,
        space_saving=ss,
        compactness=compactness,
        aspect_ratio=ar,
        realized_adjacencies=ra,
        distortion_score=distortion,
    )

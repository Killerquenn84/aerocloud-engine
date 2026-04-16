"""Medial Axis Transform (MAT) skeleton extraction and branch labelling.

Derives MAT from the existing Phase 4 EDT-based SDF — no independent EDT is
re-computed. scikit-fmm is used only for directional travel_time orientation
(D-01, Phase 7 CONTEXT.md).

Algorithm:
1. Ridge extraction: local maxima of SDF inside the mask (scipy maximum_filter)
2. Pruning: discard ridges where sdf <= min_branch_radius (noise filter)
3. Dilation: binary_dilation(iterations=2) to close 1-pixel gaps
4. Labelling: scipy.ndimage.label on the connected ridge inside the mask
5. Branch origins: argmax SDF per labelled component
6. Travel time: skfmm.travel_time from the centroid of the whole mask (float32 cast)
7. Branch map: nearest-origin Voronoi assignment (scipy label on dilated origin seeds)

Design decisions (ADR references):
- D-01: skfmm used ONLY for travel_time orientation — not for SDF generation
- D-03: skfmm returns float64 — always cast to float32 at boundary (Pitfall 1)
- D-09: SDF sign convention: positive=inside, negative=outside (ADR-0004)
- D-14: Coordinate convention: (y, x) canonical internally (ADR-0005)
- D-15: All tiebreaks use lexicographic (y, x) ordering (determinism)
- T-07-01-02: scipy.ndimage.maximum_filter is O(N), skfmm is O(N log N)
- T-07-01-04: Validate mask has > 0 inside pixels before calling skfmm
"""

from __future__ import annotations

import numpy as np
import skfmm
from pydantic import ConfigDict
from scipy import ndimage

from aerocloud.geometry.errors import GeometryError, PlacementFailedError
from aerocloud.models.base import AeroCloudBase


class MATBranch(AeroCloudBase):
    """A single labelled branch of the medial axis skeleton.

    Fields:
        branch_id: Integer label (1-based) matching the scipy.ndimage.label output.
        origin_yx: (y, x) pixel with the highest SDF value in this branch —
            the deepest interior point, used as the placement origin.
        sdf_volume: Sum of SDF values within this branch's labelled region
            (a proxy for branch "weight" / capacity).
        pixel_count: Number of pixels assigned to this branch in branch_map.
    """

    branch_id: int
    origin_yx: tuple[int, int]
    sdf_volume: float
    pixel_count: int


class MATResult(AeroCloudBase):
    """Result of MAT skeleton extraction for one SDF.

    Fields:
        branches: Tuple of MATBranch objects, one per labelled component.
            Ordered by branch_id (ascending).
        branch_map: int32 (H, W) array; value == branch_id for inside pixels
            assigned to that branch, -1 for outside pixels.
        travel_time: float32 (H, W) Eikonal travel time from the mask centroid.
            NaN is allowed outside the mask; inside pixels are always finite.
    """

    # Override model_config to allow arbitrary types (numpy arrays) while keeping
    # frozen=True and extra="forbid". strict=False needed because numpy arrays
    # are not "strict" Pydantic types.
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=False,
        arbitrary_types_allowed=True,
    )

    branches: tuple[MATBranch, ...]
    branch_map: np.ndarray  # int32 (H, W)
    travel_time: np.ndarray  # float32 (H, W)

    def model_post_init(self, __context: object) -> None:
        """Validate numpy array dtypes after construction."""
        object.__setattr__(self, "branch_map", np.asarray(self.branch_map, dtype=np.int32))
        object.__setattr__(self, "travel_time", np.asarray(self.travel_time, dtype=np.float32))


def extract_ridge_points(sdf: np.ndarray, min_branch_radius: float) -> np.ndarray:
    """Extract local maxima of SDF inside the mask, filtered by min_branch_radius.

    Uses ``scipy.ndimage.maximum_filter(sdf, size=3)`` to find local maxima in
    the 8-connected neighbourhood. Pixels that equal their local maximum AND
    exceed ``min_branch_radius`` are the ridge candidates.

    Args:
        sdf: Float32 SDF of shape (H, W), positive inside, negative outside.
        min_branch_radius: Minimum SDF value for a ridge pixel. Pixels with
            sdf <= min_branch_radius are treated as noise and discarded.

    Returns:
        Bool (H, W) mask — True at ridge (local-max) pixels that pass the
        radius threshold.
    """
    # Local maximum in 3x3 neighbourhood
    local_max = ndimage.maximum_filter(sdf, size=3)
    # Ridge: at-or-above local max AND above min_branch_radius AND inside mask
    ridge: np.ndarray = (sdf == local_max) & (sdf > min_branch_radius)
    return ridge


def extract_mat_branches(
    sdf: np.ndarray, min_branch_radius: float
) -> tuple[np.ndarray, int]:
    """Connect ridge pixels via binary dilation and label connected components.

    Steps:
    1. ``extract_ridge_points`` to get raw ridge mask
    2. ``scipy.ndimage.binary_dilation(ridge, iterations=2)`` to close 1px gaps
    3. Restrict to inside-mask pixels (sdf > 0)
    4. ``scipy.ndimage.label`` on the connected ridge

    Args:
        sdf: Float32 SDF of shape (H, W).
        min_branch_radius: Passed through to ``extract_ridge_points``.

    Returns:
        Tuple ``(labelled_array, n_labels)`` where ``labelled_array`` is an
        int32 (H, W) array with labels 1..n_labels, and ``n_labels`` is the
        number of connected components found.
    """
    ridge = extract_ridge_points(sdf, min_branch_radius)
    inside = sdf > 0
    # Dilate to close gaps
    ridge_dil = ndimage.binary_dilation(ridge, iterations=2)
    # Keep only inside-mask pixels
    ridge_connected = ridge_dil & inside
    labelled, n_labels = ndimage.label(ridge_connected)
    return labelled.astype(np.int32), int(n_labels)


def _compute_travel_time(mask: np.ndarray, centroid_yx: tuple[int, int]) -> np.ndarray:
    """Compute Eikonal travel time from centroid_yx via skfmm.

    Sets up the phi array per Pitfall 8 (phi must contain a zero level set):
    - phi[cy, cx] = -1.0  (source — zero contour between -1 and +1)
    - phi[inside & others] = +1.0
    - Outside pixels are masked (np.ma.MaskedArray)

    Casts result to float32 (Pitfall 1: skfmm always returns float64).

    Args:
        mask: Bool (H, W) mask — True for inside pixels.
        centroid_yx: (y, x) of the travel-time source point.

    Returns:
        Float32 (H, W) array. Outside pixels are set to NaN.

    Raises:
        GeometryError: If the centroid is not inside the mask.
    """
    cy, cx = centroid_yx
    if not mask[cy, cx]:
        # Snap centroid to nearest inside pixel (defensive)
        inside_yx = np.argwhere(mask)
        if len(inside_yx) == 0:
            raise GeometryError("Mask has no inside pixels — cannot compute travel time")
        # Pick the closest inside pixel to the requested centroid
        dists = (inside_yx[:, 0] - cy) ** 2 + (inside_yx[:, 1] - cx) ** 2
        nearest_idx = int(np.argmin(dists))
        cy, cx = int(inside_yx[nearest_idx, 0]), int(inside_yx[nearest_idx, 1])

    phi = np.ones(mask.shape, dtype=np.float64)
    phi[cy, cx] = -1.0

    # Mask outside pixels (skfmm ignores masked cells)
    masked_phi = np.ma.MaskedArray(phi, ~mask)
    speed = np.ones(mask.shape, dtype=np.float64)

    try:
        tt_raw = skfmm.travel_time(masked_phi, speed, dx=1.0)
    except ValueError:
        # skfmm raises ValueError: "no zero contour" when the mask is pathological
        # (e.g., only 1 inside pixel, disconnected from all others).
        # Fallback: return zero travel_time inside the mask, NaN outside.
        tt_fallback = np.full(mask.shape, np.nan, dtype=np.float32)
        tt_fallback[mask] = 0.0
        return tt_fallback
    except Exception as exc:
        raise GeometryError(f"skfmm.travel_time failed: {exc}") from exc

    # Fill masked (outside) pixels with NaN, cast to float32 (D-03 / Pitfall 1)
    tt_array = np.asarray(tt_raw.filled(np.nan) if hasattr(tt_raw, "filled") else tt_raw)
    result = tt_array.astype(np.float32)

    # Ensure all inside pixels are finite (disconnected regions may get NaN from skfmm).
    # Fill unreachable inside pixels with 0.0 — they are valid placement candidates.
    inside_nan = mask & ~np.isfinite(result)
    if inside_nan.any():
        result[inside_nan] = 0.0

    return result


def _centroid_yx(mask: np.ndarray) -> tuple[int, int]:
    """Return the (y, x) centroid of the inside-mask region (rounded to int).

    Snaps to the nearest inside pixel if the true centroid falls outside.
    Tiebreaks resolved lexicographically (D-15 determinism).
    """
    inside_yx = np.argwhere(mask)
    if len(inside_yx) == 0:
        raise GeometryError("Mask has no inside pixels — cannot compute centroid")
    cy_f = float(inside_yx[:, 0].mean())
    cx_f = float(inside_yx[:, 1].mean())
    cy, cx = round(cy_f), round(cx_f)
    if not mask[cy, cx]:
        dists = (inside_yx[:, 0] - cy) ** 2 + (inside_yx[:, 1] - cx) ** 2
        # Lexicographic tiebreak: sort by dist, then y, then x (D-15)
        order = np.lexsort((inside_yx[:, 1], inside_yx[:, 0], dists))
        cy, cx = int(inside_yx[order[0], 0]), int(inside_yx[order[0], 1])
    return cy, cx


def _build_branch_map_voronoi(
    sdf: np.ndarray,
    origins_yx: list[tuple[int, int]],
    n_branches: int,
) -> np.ndarray:
    """Build a Voronoi branch-map: each inside pixel assigned to the nearest origin.

    Uses scipy.ndimage.label on per-origin seed arrays (nearest-origin distance).
    Pixels with sdf <= 0 are assigned -1.

    Args:
        sdf: Float32 SDF of shape (H, W).
        origins_yx: List of (y, x) branch origins (0-indexed, 1-based branch_id).
        n_branches: Number of branches (len(origins_yx)).

    Returns:
        Int32 (H, W) branch_map; value in [1, n_branches] inside, -1 outside.
    """
    h, w = sdf.shape
    branch_map = np.full((h, w), -1, dtype=np.int32)
    inside = sdf > 0
    if n_branches == 0 or not inside.any():
        return branch_map

    if n_branches == 1:
        # Single branch: all inside pixels get branch_id=1
        branch_map[inside] = 1
        return branch_map

    # Compute Euclidean distance from each pixel to each origin
    # Shape: (n_branches, H, W) — pick minimum-distance origin per pixel
    # Use label seeds for speed: generate EDT from each origin and pick closest
    min_dist = np.full((h, w), np.inf, dtype=np.float64)
    for bid, (oy, ox) in enumerate(origins_yx, start=1):
        seed = np.zeros((h, w), dtype=bool)
        seed[oy, ox] = True
        dist = ndimage.distance_transform_edt(~seed)
        closer = inside & (dist < min_dist)
        branch_map[closer] = bid
        min_dist[closer] = dist[closer]

    # Tiebreaks: any inside pixel still -1 (equidistant) → assign to first origin
    still_unassigned = inside & (branch_map == -1)
    if still_unassigned.any():
        branch_map[still_unassigned] = 1

    return branch_map


def extract_mat(sdf: np.ndarray, min_branch_radius: float = 3.0) -> MATResult:
    """Extract the Medial Axis Transform from an SDF.

    Full pipeline:
    1. Validate inputs (T-07-01-04)
    2. Extract and label ridge branches
    3. Compute per-branch origin (argmax SDF in component, D-15 tiebreak)
    4. Compute Eikonal travel_time from mask centroid
    5. Build branch_map (nearest-origin Voronoi)
    6. Compute sdf_volume and pixel_count per branch

    Args:
        sdf: Float32 SDF of shape (H, W), positive inside, negative outside.
        min_branch_radius: Minimum inscribed-circle radius for branch inclusion.
            Branches with all SDF values <= this threshold are discarded (noise).

    Returns:
        MATResult with branches tuple, branch_map (int32 H,W), travel_time (float32 H,W).

    Raises:
        PlacementFailedError: If sdf has wrong dtype, ndim, or NaN/inf values.
        GeometryError: If sdf has no inside pixels (T-07-01-04).
    """
    # --- Input validation ---
    if sdf.ndim != 2:
        raise PlacementFailedError(f"SDF must be 2D, got ndim={sdf.ndim}")
    if sdf.dtype != np.float32:
        sdf = sdf.astype(np.float32)
    if not np.isfinite(sdf).all():
        raise PlacementFailedError("SDF contains NaN or inf (D-09/D-43)")

    inside = sdf > 0
    # T-07-01-04: fail fast if no inside pixels
    if not inside.any():
        raise GeometryError("SDF has no inside pixels — cannot extract MAT (T-07-01-04)")

    # --- Step 2: Extract labelled branches ---
    labelled, n_labels = extract_mat_branches(sdf, min_branch_radius)

    # --- Fallback: if no branches found, treat entire inside as 1 branch ---
    if n_labels == 0:
        # Single branch: origin is centroid; no separate centroid variable needed
        labelled = np.where(inside, 1, 0).astype(np.int32)
        n_labels = 1

    # --- Step 3: Per-branch origins (argmax SDF within label, D-15 tiebreak) ---
    origins_yx: list[tuple[int, int]] = []
    for bid in range(1, n_labels + 1):
        component_mask = labelled == bid
        if not component_mask.any():
            # Empty label — use centroid as fallback
            centroid_fb = _centroid_yx(inside)
            origins_yx.append(centroid_fb)
            continue
        # Restrict to inside-mask pixels within this component
        valid = component_mask & inside
        if not valid.any():
            valid = component_mask
        # argmax SDF within component (highest SDF = deepest inside)
        sdf_in_component = np.where(valid, sdf, -np.inf)
        max_val = float(np.max(sdf_in_component))
        candidates = np.argwhere(sdf_in_component == max_val)
        # Lexicographic tiebreak (D-15): sort by (y, x) ascending
        candidates_sorted = sorted(
            [(int(r[0]), int(r[1])) for r in candidates]
        )
        origins_yx.append(candidates_sorted[0])

    # --- Step 4: Travel time from mask centroid ---
    centroid_yx = _centroid_yx(inside)
    travel_time = _compute_travel_time(inside, centroid_yx)

    # --- Step 5: Build branch_map (nearest-origin Voronoi) ---
    branch_map = _build_branch_map_voronoi(sdf, origins_yx, n_labels)

    # --- Step 6: sdf_volume and pixel_count per branch ---
    branches: list[MATBranch] = []
    for bid, origin_yx in enumerate(origins_yx, start=1):
        component_pixels = branch_map == bid
        sdf_vol = float(np.sum(sdf[component_pixels]))
        px_count = int(component_pixels.sum())
        branches.append(
            MATBranch(
                branch_id=bid,
                origin_yx=origin_yx,
                sdf_volume=sdf_vol,
                pixel_count=px_count,
            )
        )

    return MATResult(
        branches=tuple(branches),
        branch_map=branch_map,
        travel_time=travel_time,
    )

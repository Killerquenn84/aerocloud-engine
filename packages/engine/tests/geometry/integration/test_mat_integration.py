"""Integration tests for MAT extraction on analytical shape SDFs.

TDD Phase: RED — imports from aerocloud.geometry.mat do not exist yet.

Shapes are generated analytically (no .npy fixture files needed) using the
same SDF formula as Phase 4 (Meijster EDT via scipy.ndimage.distance_transform_edt).

Coverage:
- Circle SDF → single branch (simple shape fallback)
- Star SDF → multi-branch
- Crescent SDF → multi-branch
- All branch origins land inside mask (sdf > 0)
- Single-branch result → origin near geometric centroid
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy import ndimage

from aerocloud.geometry.mat import MATResult, extract_mat  # type: ignore[import-not-found]


# ---------------------------------------------------------------------------
# SDF helper (mirrors Phase 4 compute_sdf formula without the error checking)
# ---------------------------------------------------------------------------


def _compute_sdf_raw(mask: np.ndarray) -> np.ndarray:
    """Compute float32 SDF from bool mask (positive inside)."""
    edt_in = ndimage.distance_transform_edt(mask).astype(np.float32)
    edt_out = ndimage.distance_transform_edt(~mask).astype(np.float32)
    return edt_in - edt_out


def _circle_mask(size: int = 80, radius: int = 32) -> np.ndarray:
    """Bool mask for a filled circle."""
    y, x = np.ogrid[:size, :size]
    return np.array((y - size // 2) ** 2 + (x - size // 2) ** 2 <= radius**2)


def _star_mask(size: int = 128, n_arms: int = 5, outer_r: int = 55, inner_r: int = 22) -> np.ndarray:
    """Bool mask for an n-arm star."""
    cy, cx = size // 2, size // 2
    y, x = np.ogrid[:size, :size]
    angle = np.arctan2(y - cy, x - cx)
    dist = np.sqrt((y - cy) ** 2 + (x - cx) ** 2)
    star_angle = angle * n_arms / 2
    boundary_r = inner_r + (outer_r - inner_r) * (0.5 + 0.5 * np.cos(star_angle))
    return np.array(dist <= boundary_r)


def _crescent_mask(size: int = 96) -> np.ndarray:
    """Bool mask for a crescent (difference of two offset circles)."""
    y, x = np.ogrid[:size, :size]
    outer: np.ndarray = (y - size // 2) ** 2 + (x - size // 2) ** 2 <= (size // 3) ** 2
    # Offset inner circle to create crescent
    inner_cx = size // 2 + size // 8
    inner: np.ndarray = (y - size // 2) ** 2 + (x - inner_cx) ** 2 <= (size // 4) ** 2
    return np.array(outer & ~inner)


# ---------------------------------------------------------------------------
# I1: Circle fixture — single branch
# ---------------------------------------------------------------------------


def test_circle_fixture_single_branch() -> None:
    """I1: Circle SDF (simple shape) → n_branches == 1 after MAT extraction."""
    mask = _circle_mask(size=80, radius=32)
    sdf = _compute_sdf_raw(mask)
    result = extract_mat(sdf, min_branch_radius=3.0)
    assert isinstance(result, MATResult)
    assert len(result.branches) == 1, (
        f"Circle must yield exactly 1 branch, got {len(result.branches)}"
    )


# ---------------------------------------------------------------------------
# I2: Star fixture — multi-branch
# ---------------------------------------------------------------------------


def test_star_fixture_multi_branch() -> None:
    """I2: 5-arm star SDF → n_branches > 1 after MAT extraction."""
    mask = _star_mask(size=128, n_arms=5)
    sdf = _compute_sdf_raw(mask)
    result = extract_mat(sdf, min_branch_radius=3.0)
    assert len(result.branches) > 1, (
        f"Star SDF must yield more than 1 branch, got {len(result.branches)}"
    )


# ---------------------------------------------------------------------------
# I3: Crescent fixture — multi-branch
# ---------------------------------------------------------------------------


def test_crescent_fixture_multi_branch() -> None:
    """I3: Crescent SDF → n_branches > 1 after MAT extraction."""
    mask = _crescent_mask(size=96)
    sdf = _compute_sdf_raw(mask)
    result = extract_mat(sdf, min_branch_radius=3.0)
    assert len(result.branches) > 1, (
        f"Crescent SDF must yield more than 1 branch, got {len(result.branches)}"
    )


# ---------------------------------------------------------------------------
# I4: All branch origins must be inside the mask (sdf > 0)
# ---------------------------------------------------------------------------


def test_branch_origins_inside_mask() -> None:
    """I4: Every branch origin must land on a pixel where sdf > 0."""
    mask = _star_mask(size=128)
    sdf = _compute_sdf_raw(mask)
    result = extract_mat(sdf, min_branch_radius=3.0)
    for branch in result.branches:
        y, x = branch.origin_yx
        assert sdf[y, x] > 0, (
            f"Branch origin ({y}, {x}) is not inside the mask (sdf={sdf[y, x]:.4f})"
        )


# ---------------------------------------------------------------------------
# I5: Single-branch result — origin near geometric centroid
# ---------------------------------------------------------------------------


def test_fallback_single_branch_origin_is_centroid() -> None:
    """I5: Circle (1-branch) → origin is within 10px of geometric centroid."""
    size = 80
    radius = 32
    mask = _circle_mask(size=size, radius=radius)
    sdf = _compute_sdf_raw(mask)
    result = extract_mat(sdf, min_branch_radius=3.0)

    assert len(result.branches) == 1
    oy, ox = result.branches[0].origin_yx
    cy, cx = size // 2, size // 2  # geometric center

    dist = np.sqrt((oy - cy) ** 2 + (ox - cx) ** 2)
    assert dist <= 10, (
        f"Single-branch origin ({oy}, {ox}) should be within 10px of centroid "
        f"({cy}, {cx}), got dist={dist:.2f}"
    )


# ---------------------------------------------------------------------------
# I6: branch_map has correct shape and dtype
# ---------------------------------------------------------------------------


def test_branch_map_shape_and_dtype() -> None:
    """I6: branch_map must be int32 with shape (H, W) and -1 outside mask."""
    mask = _circle_mask(size=80, radius=32)
    sdf = _compute_sdf_raw(mask)
    result = extract_mat(sdf, min_branch_radius=3.0)

    assert result.branch_map.dtype == np.int32, (
        f"branch_map must be int32, got {result.branch_map.dtype}"
    )
    assert result.branch_map.shape == sdf.shape, (
        f"branch_map shape {result.branch_map.shape} != sdf shape {sdf.shape}"
    )
    # Outside pixels must be -1
    outside = sdf <= 0
    assert np.all(result.branch_map[outside] == -1), (
        "branch_map must be -1 for all outside pixels"
    )


# ---------------------------------------------------------------------------
# I7: travel_time shape and dtype (integration-level)
# ---------------------------------------------------------------------------


def test_travel_time_shape_and_float32() -> None:
    """I7: travel_time must be float32 with shape (H, W)."""
    mask = _star_mask(size=128)
    sdf = _compute_sdf_raw(mask)
    result = extract_mat(sdf, min_branch_radius=3.0)

    assert result.travel_time.dtype == np.float32, (
        f"travel_time must be float32, got {result.travel_time.dtype}"
    )
    assert result.travel_time.shape == sdf.shape, (
        f"travel_time shape {result.travel_time.shape} != sdf shape {sdf.shape}"
    )

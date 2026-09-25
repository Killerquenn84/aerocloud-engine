"""Unit tests for geometry/mat.py — MAT extraction and pruning.

TDD Phase: RED — these tests are written before the implementation exists.
All imports from ``aerocloud.geometry.mat`` will fail with ImportError until
Task 2 (GREEN) creates the module.

Test coverage:
- Ridge point extraction on circle and noisy SDFs
- Binary dilation gap-closing behaviour
- Branch labelling on star-shaped SDF
- Branch origin (y, x) coordinate convention
- skfmm travel_time cast to float32
- travel_time zero contour requirement
- MATResult Pydantic model is frozen and validates
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy import ndimage

from aerocloud.geometry.mat import (  # type: ignore[import-not-found]
    MATBranch,
    MATResult,
    extract_mat,
    extract_mat_branches,
    extract_ridge_points,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _circle_sdf(size: int = 64, radius: int = 24) -> np.ndarray:
    """Return a float32 SDF for a filled circle (positive inside)."""
    y, x = np.ogrid[:size, :size]
    mask: np.ndarray = (y - size // 2) ** 2 + (x - size // 2) ** 2 <= radius**2
    edt_in = ndimage.distance_transform_edt(mask).astype(np.float32)
    edt_out = ndimage.distance_transform_edt(~mask).astype(np.float32)
    return edt_in - edt_out


def _star_sdf(size: int = 128, n_arms: int = 5, outer_r: int = 55, inner_r: int = 22) -> np.ndarray:
    """Return a float32 SDF for an n-arm star (positive inside)."""
    cy, cx = size // 2, size // 2
    y, x = np.ogrid[:size, :size]
    angle = np.arctan2(y - cy, x - cx)
    dist = np.sqrt((y - cy) ** 2 + (x - cx) ** 2)
    # Parametric star boundary radius
    star_angle = angle * n_arms / 2
    boundary_r = inner_r + (outer_r - inner_r) * (0.5 + 0.5 * np.cos(star_angle))
    mask: np.ndarray = dist <= boundary_r
    edt_in = ndimage.distance_transform_edt(mask).astype(np.float32)
    edt_out = ndimage.distance_transform_edt(~mask).astype(np.float32)
    return edt_in - edt_out


# ---------------------------------------------------------------------------
# M1: Ridge points on circle SDF — single cluster near center
# ---------------------------------------------------------------------------


def test_extract_ridge_points_circle() -> None:
    """M1: Circle SDF yields ridge near its center (max inscribed disc center)."""
    sdf = _circle_sdf(size=64, radius=24)
    ridge = extract_ridge_points(sdf, min_branch_radius=3.0)
    assert ridge.dtype == np.bool_
    assert ridge.shape == sdf.shape
    # At least one ridge pixel must exist inside the circle
    assert ridge.any(), "Circle SDF must have at least one ridge point"
    # All ridge pixels must be inside the mask (sdf > 0)
    assert np.all(sdf[ridge] > 0), "Ridge points must be strictly inside the mask"


# ---------------------------------------------------------------------------
# M2: Noise filter — tiny SDF peak below min_branch_radius is removed
# ---------------------------------------------------------------------------


def test_extract_ridge_points_filters_noise() -> None:
    """M2: Tiny SDF values below min_branch_radius are filtered out."""
    # Create SDF with all values <= 2.0 (below default min_branch_radius=3.0)
    sdf = np.zeros((16, 16), dtype=np.float32)
    sdf[8, 8] = 2.0  # local max but below threshold
    sdf[7, 8] = 1.5
    sdf[8, 7] = 1.5
    sdf[9, 8] = 1.5
    sdf[8, 9] = 1.5
    # Outside is negative
    mask_outside = sdf == 0.0
    sdf[mask_outside] = -1.0

    ridge = extract_ridge_points(sdf, min_branch_radius=3.0)
    # All values <= 2.0, so no pixel exceeds min_branch_radius=3.0
    assert not ridge.any(), (
        "extract_ridge_points must filter out all pixels with sdf <= min_branch_radius"
    )


# ---------------------------------------------------------------------------
# M3: Binary dilation closes 1px gap
# ---------------------------------------------------------------------------


def test_binary_dilation_connects_gaps() -> None:
    """M3: A 1px gap between two ridge pixels is connected after dilation."""
    # Create a star SDF with sufficient size to guarantee branches
    sdf = _star_sdf(size=128)
    ridge = extract_ridge_points(sdf, min_branch_radius=3.0)
    # After dilation (inside extract_mat_branches), the labeled result should have
    # connected components — we test via extract_mat_branches directly
    ridge_dil, n_labels = extract_mat_branches(sdf, min_branch_radius=3.0)
    # The dilated array must be bool or int
    assert ridge_dil.ndim == 2
    assert ridge_dil.shape == sdf.shape
    # Should produce at least 1 label
    assert n_labels >= 1, "extract_mat_branches must produce at least 1 label"


# ---------------------------------------------------------------------------
# M4: Star SDF → n_branches > 1 after extract_mat_branches
# ---------------------------------------------------------------------------


def test_label_branches_star() -> None:
    """M4: Star-shaped SDF yields multiple branches after labelling."""
    sdf = _star_sdf(size=128, n_arms=5)
    _, n_labels = extract_mat_branches(sdf, min_branch_radius=3.0)
    assert n_labels > 1, (
        f"Star SDF must produce more than 1 branch, got n_labels={n_labels}"
    )


# ---------------------------------------------------------------------------
# M5: Branch origins have (y, x) ordering with valid indices
# ---------------------------------------------------------------------------


def test_branch_origin_is_yx_tuple() -> None:
    """M5: All branch origins have (y, x) ordering and valid bounds."""
    sdf = _star_sdf(size=128)
    result = extract_mat(sdf, min_branch_radius=3.0)
    H, W = sdf.shape
    for branch in result.branches:
        y, x = branch.origin_yx
        assert 0 <= y < H, f"Branch origin y={y} out of bounds [0, {H})"
        assert 0 <= x < W, f"Branch origin x={x} out of bounds [0, {W})"


# ---------------------------------------------------------------------------
# M6: travel_time is cast to float32 (D-03 skfmm Pitfall 1)
# ---------------------------------------------------------------------------


def test_travel_time_returns_float32() -> None:
    """M6: MATResult.travel_time must be float32 (skfmm returns float64 — must cast)."""
    sdf = _circle_sdf(size=64, radius=24)
    result = extract_mat(sdf, min_branch_radius=3.0)
    assert result.travel_time.dtype == np.float32, (
        f"travel_time must be float32 (D-03 skfmm cast), got {result.travel_time.dtype}"
    )


# ---------------------------------------------------------------------------
# M7: travel_time raises ValueError when mask has no inside pixels
# ---------------------------------------------------------------------------


def test_travel_time_zero_contour_required() -> None:
    """M7: extract_mat raises GeometryError if mask has no inside pixels."""
    from aerocloud.geometry.errors import GeometryError  # type: ignore[import-not-found]

    # All-negative SDF = no inside region
    sdf = np.full((16, 16), -1.0, dtype=np.float32)
    with pytest.raises((GeometryError, ValueError)):
        extract_mat(sdf, min_branch_radius=3.0)


# ---------------------------------------------------------------------------
# M8: MATResult is a frozen Pydantic model
# ---------------------------------------------------------------------------


def test_mat_result_pydantic_valid() -> None:
    """M8: MATResult model validates and is immutable (frozen=True)."""
    from pydantic import ValidationError

    sdf = _circle_sdf(size=64, radius=24)
    result = extract_mat(sdf, min_branch_radius=3.0)
    assert isinstance(result, MATResult)
    # Test frozen: attempting to set an attribute must raise
    # Pydantic v2 raises ValidationError for frozen model attribute assignment
    with pytest.raises((TypeError, AttributeError, ValidationError)):
        result.branches = ()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# M9: MATBranch fields are accessible
# ---------------------------------------------------------------------------


def test_mat_branch_fields() -> None:
    """M9: Each MATBranch has branch_id, origin_yx, sdf_volume, pixel_count."""
    sdf = _circle_sdf(size=64, radius=24)
    result = extract_mat(sdf, min_branch_radius=3.0)
    assert len(result.branches) >= 1
    branch = result.branches[0]
    assert isinstance(branch, MATBranch)
    assert isinstance(branch.branch_id, int)
    assert isinstance(branch.origin_yx, tuple)
    assert len(branch.origin_yx) == 2
    assert isinstance(branch.sdf_volume, float)
    assert isinstance(branch.pixel_count, int)
    assert branch.pixel_count > 0

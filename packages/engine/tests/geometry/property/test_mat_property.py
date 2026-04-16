"""Property-based tests for MAT extraction.

TDD Phase: RED — imports from aerocloud.geometry.mat do not exist yet.

Uses Hypothesis to generate random bool masks, compute SDFs analytically,
and verify invariants on extract_mat results:
- Non-NaN float32 travel_time
- All branch origins within valid bounds
- Determinism: same SDF → same result
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
from scipy import ndimage

from aerocloud.geometry.mat import MATResult, extract_mat  # type: ignore[import-not-found]


# ---------------------------------------------------------------------------
# SDF helper (same as integration tests — duplicated to keep tests self-contained)
# ---------------------------------------------------------------------------


def _compute_sdf_from_mask(mask: np.ndarray) -> np.ndarray:
    """Compute float32 SDF from bool mask (positive inside)."""
    edt_in = ndimage.distance_transform_edt(mask).astype(np.float32)
    edt_out = ndimage.distance_transform_edt(~mask).astype(np.float32)
    return edt_in - edt_out


# ---------------------------------------------------------------------------
# Strategy: random valid bool mask (must have both True and False pixels)
# ---------------------------------------------------------------------------


@st.composite
def valid_sdf_strategy(draw: st.DrawFn) -> np.ndarray:
    """Generate a random bool mask and compute its SDF.

    Constraints:
    - Size: 20..80 in each dimension (manageable for CI)
    - Must have at least one True (inside) pixel
    - Must have at least one False (outside) pixel
    - The mask must have enough inside pixels to compute a meaningful SDF
    """
    h = draw(st.integers(min_value=20, max_value=80))
    w = draw(st.integers(min_value=20, max_value=80))

    # Draw a random bool mask as integer array, then convert
    raw = draw(
        st.arrays(
            dtype=np.bool_,
            shape=(h, w),
            elements=st.booleans(),
        )
    )

    # Require at least 20 True pixels and at least 1 False pixel
    assume(raw.sum() >= 20)
    assume((~raw).any())

    return _compute_sdf_from_mask(raw)


# ---------------------------------------------------------------------------
# P1: Random mask → non-NaN float32 travel_time
# ---------------------------------------------------------------------------


@given(sdf=valid_sdf_strategy())
@settings(
    max_examples=20,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=10_000,  # 10 seconds per example (skfmm can be slow on large masks)
)
def test_travel_time_non_nan_float32(sdf: np.ndarray) -> None:
    """P1: extract_mat on any valid random SDF produces non-NaN float32 travel_time."""
    result = extract_mat(sdf, min_branch_radius=3.0)
    assert result.travel_time.dtype == np.float32, (
        f"travel_time must be float32, got {result.travel_time.dtype}"
    )
    # travel_time may be NaN outside the mask — check only inside pixels
    inside = sdf > 0
    if inside.any():
        tt_inside = result.travel_time[inside]
        assert np.all(np.isfinite(tt_inside)), (
            f"travel_time inside mask must be finite, "
            f"got NaN count={np.isnan(tt_inside).sum()}"
        )


# ---------------------------------------------------------------------------
# P2: Branch origins always within bounds
# ---------------------------------------------------------------------------


@given(sdf=valid_sdf_strategy())
@settings(
    max_examples=20,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=10_000,
)
def test_branch_origins_within_bounds(sdf: np.ndarray) -> None:
    """P2: All branch origins have 0 <= y < H and 0 <= x < W."""
    H, W = sdf.shape
    result = extract_mat(sdf, min_branch_radius=3.0)
    for branch in result.branches:
        y, x = branch.origin_yx
        assert 0 <= y < H, f"Branch origin y={y} out of bounds [0, {H})"
        assert 0 <= x < W, f"Branch origin x={x} out of bounds [0, {W})"


# ---------------------------------------------------------------------------
# P3: Determinism — same SDF → same MATResult
# ---------------------------------------------------------------------------


@given(sdf=valid_sdf_strategy())
@settings(
    max_examples=15,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=15_000,
)
def test_determinism(sdf: np.ndarray) -> None:
    """P3: Calling extract_mat twice on the same SDF yields identical results."""
    result1 = extract_mat(sdf, min_branch_radius=3.0)
    result2 = extract_mat(sdf, min_branch_radius=3.0)

    # Same number of branches
    assert len(result1.branches) == len(result2.branches), (
        "extract_mat must be deterministic: same SDF → same n_branches"
    )

    # Same origins (lexicographically sorted)
    origins1 = sorted(b.origin_yx for b in result1.branches)
    origins2 = sorted(b.origin_yx for b in result2.branches)
    assert origins1 == origins2, (
        "extract_mat must be deterministic: same SDF → same branch origins"
    )

    # Same travel_time (bit-for-bit on the inside region)
    inside = sdf > 0
    if inside.any():
        np.testing.assert_array_equal(
            result1.travel_time[inside],
            result2.travel_time[inside],
            err_msg="extract_mat must be deterministic: travel_time must be identical",
        )


# ---------------------------------------------------------------------------
# P4: MATResult is always a valid Pydantic model (never raises ValidationError)
# ---------------------------------------------------------------------------


@given(sdf=valid_sdf_strategy())
@settings(
    max_examples=15,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=10_000,
)
def test_mat_result_always_valid(sdf: np.ndarray) -> None:
    """P4: extract_mat always returns a valid MATResult instance."""
    result = extract_mat(sdf, min_branch_radius=3.0)
    assert isinstance(result, MATResult)
    assert isinstance(result.branches, tuple)
    assert result.branch_map.ndim == 2
    assert result.travel_time.ndim == 2

"""Unit tests for geometry/sdf.py — compute_sdf + validate_sdf.

TDD: Tests written BEFORE implementation (RED phase).
Tests S1..S7 verify D-09..D-13 from 04-CONTEXT.md.
No mocking of scipy or numpy (D-51 — real dependencies only).

GEO-03 is the linchpin: circle SDF center == radius ± 1 pixel.
"""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from aerocloud.geometry.errors import PlacementFailedError
from aerocloud.geometry.mask import mask_from_bytes
from aerocloud.geometry.sdf import compute_sdf, validate_sdf


def _png_from_bool(mask: np.ndarray) -> bytes:
    """Encode a (H, W) bool mask as an L-mode PNG."""
    img = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# S1: compute_sdf returns float32 (H, W)
# ---------------------------------------------------------------------------


def test_s1_sdf_dtype_is_float32(circle_mask_bytes: bytes) -> None:
    """S1: compute_sdf(circle_mask) returns ndarray of dtype float32."""
    mask = mask_from_bytes(circle_mask_bytes)
    sdf = compute_sdf(mask)
    assert sdf.dtype == np.float32, f"expected float32, got {sdf.dtype}"
    assert sdf.shape == mask.shape, f"shape mismatch: {sdf.shape} != {mask.shape}"


# ---------------------------------------------------------------------------
# S2: GEO-03 circle fixture — center SDF == radius ± 1 pixel
# ---------------------------------------------------------------------------


def test_s2_geo03_circle_center_radius(circle_mask_bytes: bytes) -> None:
    """S2 / GEO-03: Circle SDF center value is within [R-1, R+1] pixels.

    Fixture: 64x64 canvas, filled circle radius=24, center=(32, 32).
    The center pixel is maximally inside — SDF should ≈ 24.0 ± 1.0.
    """
    mask = mask_from_bytes(circle_mask_bytes)
    sdf = compute_sdf(mask)
    h, w = sdf.shape  # 64, 64
    cy, cx = h // 2, w // 2  # (32, 32)
    center_val = float(sdf[cy, cx])
    radius = 24.0

    assert center_val > 0, (
        f"SDF at center must be positive (D-09 positive=inside), got {center_val}"
    )
    assert abs(center_val - radius) <= 1.0, (
        f"GEO-03 FAILED: expected SDF[center] ≈ {radius} ± 1 px, got {center_val:.4f}"
    )


# ---------------------------------------------------------------------------
# S3: Square fixture — center SDF == half side ± 0.5
# ---------------------------------------------------------------------------


def test_s3_square_center_sdf(square_mask_bytes: bytes) -> None:
    """S3: Square 40x40 centered in 64x64 — center SDF in [19.5, 20.5].

    The center of a 40x40 square is 20 pixels from each edge.
    exact EDT gives SDF[center] == 20.0 (perfect half-side).
    """
    mask = mask_from_bytes(square_mask_bytes)
    sdf = compute_sdf(mask)
    h, w = sdf.shape  # 64, 64
    cy, cx = h // 2, w // 2  # (32, 32) — center of square
    center_val = float(sdf[cy, cx])
    assert center_val > 0, f"center of square must be positive (D-09), got {center_val}"
    assert 19.5 <= center_val <= 20.5, (
        f"square center SDF should be ≈ 20.0 (half side), got {center_val:.4f}"
    )


# ---------------------------------------------------------------------------
# S4: Sign invariant — strict interior > 0, strict exterior < 0
# ---------------------------------------------------------------------------


def test_s4_sign_invariant_interior_exterior(circle_mask_bytes: bytes) -> None:
    """S4: Strict interior pixel has sdf > 0; strict exterior pixel has sdf < 0.

    D-09: positive=inside, negative=outside, 0 on boundary.
    """
    mask = mask_from_bytes(circle_mask_bytes)
    sdf = compute_sdf(mask)
    h, w = sdf.shape  # 64, 64

    # Strict interior: center (32, 32) and all 4-neighbors are True
    cy, cx = h // 2, w // 2
    assert mask[cy, cx], "center should be inside (True)"
    assert mask[cy - 1, cx], "center-1 row should be inside (True)"
    assert mask[cy + 1, cx], "center+1 row should be inside (True)"
    assert mask[cy, cx - 1], "center-1 col should be inside (True)"
    assert mask[cy, cx + 1], "center+1 col should be inside (True)"
    assert sdf[cy, cx] > 0, f"strict interior SDF must be > 0, got {sdf[cy, cx]}"

    # Strict exterior: corner (0, 0) and all 4-neighbors are False
    assert not mask[0, 0], "corner should be outside (False)"
    assert not mask[0, 1], "corner+1 col should be outside (False)"
    assert not mask[1, 0], "corner+1 row should be outside (False)"
    assert sdf[0, 0] < 0, f"strict exterior SDF must be < 0, got {sdf[0, 0]}"


# ---------------------------------------------------------------------------
# S5: validate_sdf raises PlacementFailedError on NaN
# ---------------------------------------------------------------------------


def test_s5_validate_sdf_raises_on_nan() -> None:
    """S5: validate_sdf(sdf_with_nan) raises PlacementFailedError."""
    sdf = np.array([[1.0, float("nan")], [-1.0, 0.5]], dtype=np.float32)
    with pytest.raises(PlacementFailedError, match="NaN or inf"):
        validate_sdf(sdf)


# ---------------------------------------------------------------------------
# S6: validate_sdf raises PlacementFailedError on inf
# ---------------------------------------------------------------------------


def test_s6_validate_sdf_raises_on_inf() -> None:
    """S6: validate_sdf(sdf_with_inf) raises PlacementFailedError."""
    sdf = np.array([[1.0, float("inf")], [-1.0, 0.5]], dtype=np.float32)
    with pytest.raises(PlacementFailedError, match="NaN or inf"):
        validate_sdf(sdf)


# ---------------------------------------------------------------------------
# S7: compute_sdf contract — assumes non-degenerate input (D-08 pre-validated)
# ---------------------------------------------------------------------------


def test_s7_compute_sdf_contract_requires_bool_mask() -> None:
    """S7: compute_sdf requires bool dtype — non-bool mask raises PlacementFailedError.

    Per D-08, the caller must pre-validate the mask via mask_from_bytes.
    compute_sdf enforces its own dtype contract as a defensive check.
    """
    bad_mask = np.ones((8, 8), dtype=np.uint8)  # uint8, not bool
    with pytest.raises(PlacementFailedError):
        compute_sdf(bad_mask)


# ---------------------------------------------------------------------------
# Additional: verify SDF is finite everywhere on valid masks
# ---------------------------------------------------------------------------


def test_sdf_finite_on_circle(circle_mask_bytes: bytes) -> None:
    """SDF is finite everywhere for the circle fixture."""
    mask = mask_from_bytes(circle_mask_bytes)
    sdf = compute_sdf(mask)
    assert np.isfinite(sdf).all(), "SDF must have no NaN or inf on valid circle mask"


def test_sdf_finite_on_square(square_mask_bytes: bytes) -> None:
    """SDF is finite everywhere for the square fixture."""
    mask = mask_from_bytes(square_mask_bytes)
    sdf = compute_sdf(mask)
    assert np.isfinite(sdf).all(), "SDF must have no NaN or inf on valid square mask"


def test_sdf_finite_on_c_shape(c_shape_mask_bytes: bytes) -> None:
    """SDF is finite everywhere for the concave C-shape fixture."""
    mask = mask_from_bytes(c_shape_mask_bytes)
    sdf = compute_sdf(mask)
    assert np.isfinite(sdf).all(), "SDF must have no NaN or inf on C-shape mask"

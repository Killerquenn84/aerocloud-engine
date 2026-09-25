"""Hypothesis property tests for geometry/sdf.py.

Per 04-RESEARCH.md §9 and D-50 (property test dimension).
Tests random masks to verify:
1. SDF dtype = float32 and finite everywhere
2. SDF sign matches mask (positive=inside, negative=outside)
3. SDF inversion symmetry: SDF(mask) == -SDF(~mask) up to sign

No mocking of scipy or numpy (D-51).
"""

from __future__ import annotations

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays
from scipy import ndimage

from aerocloud.geometry.sdf import compute_sdf

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Bounded mask shapes: 8..64 to keep tests fast per RESEARCH.md §9
_mask_shape_st = st.tuples(
    st.integers(min_value=8, max_value=64),
    st.integers(min_value=8, max_value=64),
)


def _nontrivial_mask(
    shape: tuple[int, int],
) -> st.SearchStrategy[np.ndarray]:
    """Non-empty, non-full random binary bool mask of given shape."""
    return arrays(
        dtype=np.bool_,
        shape=shape,
        elements=st.booleans(),
    ).filter(lambda a: 0 < int(a.sum()) < a.size)


def _dilated_boundary(mask: np.ndarray) -> np.ndarray:
    """Return True for pixels on the boundary (interior pixels next to exterior)."""
    return ndimage.binary_dilation(~mask, iterations=1) & mask


# ---------------------------------------------------------------------------
# Property 1: dtype = float32, shape matches, all finite
# ---------------------------------------------------------------------------


@given(_mask_shape_st.flatmap(_nontrivial_mask))
@settings(deadline=2000, max_examples=200)
def test_sdf_dtype_and_finite(mask: np.ndarray) -> None:
    """For any non-trivial mask, SDF is float32, same shape, all finite."""
    sdf = compute_sdf(mask)
    assert sdf.dtype == np.float32, f"expected float32, got {sdf.dtype}"
    assert sdf.shape == mask.shape, f"shape mismatch: {sdf.shape} != {mask.shape}"
    assert np.isfinite(sdf).all(), "SDF must have no NaN or inf"


# ---------------------------------------------------------------------------
# Property 2: sign matches mask (D-09 sign convention)
# ---------------------------------------------------------------------------


@given(_mask_shape_st.flatmap(_nontrivial_mask))
@settings(deadline=2000, max_examples=200)
def test_sdf_sign_matches_mask(mask: np.ndarray) -> None:
    """D-09 sign convention: positive inside, negative outside.

    Strict interior (all 4-neighbors True): SDF > 0.
    Strict exterior (all 4-neighbors False): SDF < 0.
    Boundary pixels (mixed neighborhood): SDF can be 0.
    """
    sdf = compute_sdf(mask)

    # Strict interior: mask is True AND no neighboring pixel is False
    interior = mask & ~_dilated_boundary(mask)
    # Strict exterior: mask is False AND no neighboring pixel is True
    exterior = (~mask) & ~_dilated_boundary(~mask)

    if interior.any():
        interior_vals = sdf[interior]
        assert (interior_vals > 0).all(), (
            f"strict interior pixels must have sdf > 0 (D-09), min={interior_vals.min():.4f}"
        )
    if exterior.any():
        exterior_vals = sdf[exterior]
        assert (exterior_vals < 0).all(), (
            f"strict exterior pixels must have sdf < 0 (D-09), max={exterior_vals.max():.4f}"
        )


# ---------------------------------------------------------------------------
# Property 3: inversion symmetry — SDF(mask) == -SDF(~mask) up to atol=1e-5
# ---------------------------------------------------------------------------


@given(_mask_shape_st.flatmap(_nontrivial_mask))
@settings(deadline=2000, max_examples=200)
def test_sdf_inversion_symmetry(mask: np.ndarray) -> None:
    """SDF(mask) == -SDF(~mask) up to float32 rounding (atol=1e-5).

    Inverting the mask flips interior/exterior, so the SDF should negate
    exactly (up to fp32 precision) per the two-call EDT formula (D-11).
    """
    sdf_a = compute_sdf(mask)
    sdf_b = compute_sdf(~mask)
    assert np.allclose(sdf_a, -sdf_b, atol=1e-5), (
        f"SDF inversion symmetry failed: max diff={np.abs(sdf_a + sdf_b).max():.6f}"
    )

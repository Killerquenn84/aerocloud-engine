"""Signed Distance Field (D-09..D-13).

**Sign convention (locked, ADR-0004):**
- sdf > 0 inside the silhouette
- sdf == 0 on the boundary
- sdf < 0 outside the silhouette

Computed as ``edt(mask) - edt(~mask)`` via scipy's exact Meijster algorithm,
then cast to float32 at the public boundary (D-10). Two EDT calls; memory
temporarily doubles (float64 distance maps) — see R-2 in RESEARCH.md.

No downsampling (D-12). Resolution = input resolution.
Caller must guarantee non-degenerate mask (D-08 / ``mask_from_bytes`` enforces
this before calling ``compute_sdf``).
"""

from __future__ import annotations

import gc

import numpy as np
from scipy import ndimage

from aerocloud.geometry.errors import PlacementFailedError


def compute_sdf(mask: np.ndarray) -> np.ndarray:
    """Compute signed Euclidean distance field.

    Uses scipy's exact Meijster algorithm via two EDT calls (D-11):
    ``sdf = edt(mask) - edt(~mask)``

    - ``edt(mask)`` returns distance from each True (inside) pixel to the
      nearest False (outside) pixel → positive values inside.
    - ``edt(~mask)`` returns distance from each False (outside) pixel to the
      nearest True (inside) pixel → positive values outside.
    - Subtracting gives positive=inside, negative=outside (ADR-0004 / D-09).

    Args:
        mask: shape (H, W), dtype bool. Caller must guarantee non-degenerate
            mask (D-08 / ``mask_from_bytes`` already enforces this).

    Returns:
        Float32 ndarray of shape (H, W), positive inside, negative outside.

    Raises:
        PlacementFailedError: If ``mask`` has wrong dtype or ndim, or if the
            resulting SDF contains NaN or inf (contract violation).
    """
    if mask.dtype != np.bool_:
        raise PlacementFailedError(f"compute_sdf expects bool mask, got {mask.dtype}")
    if mask.ndim != 2:
        raise PlacementFailedError(f"compute_sdf expects 2D mask, got ndim={mask.ndim}")

    # Two-call EDT pattern (D-11, ADR-0004):
    # edt_in: distance from each True pixel to nearest False pixel (inside depth)
    edt_in: np.ndarray[tuple[int, int], np.dtype[np.float64]] = ndimage.distance_transform_edt(mask)
    # Release the float64 temporary before the second EDT to cap peak RSS.
    gc.collect()
    # edt_out: distance from each False pixel to nearest True pixel (outside depth)
    edt_out: np.ndarray[tuple[int, int], np.dtype[np.float64]] = ndimage.distance_transform_edt(
        ~mask
    )

    # Cast to float32 at the public boundary per D-10
    sdf: np.ndarray[tuple[int, int], np.dtype[np.float32]] = (edt_in - edt_out).astype(
        np.float32, copy=False
    )

    # Validate contract (D-09 + D-10 runtime assertion)
    validate_sdf(sdf)
    return sdf


def validate_sdf(sdf: np.ndarray) -> None:
    """Raise PlacementFailedError on contract violation (NaN, inf, wrong dtype).

    Per D-09 and D-10, the SDF must be float32 and finite everywhere.
    Called automatically by ``compute_sdf``; can also be called externally
    on SDFs loaded from cache.

    Args:
        sdf: Signed distance field array to validate.

    Raises:
        PlacementFailedError: If ``sdf`` is not float32, or contains NaN or
            inf values (non-finite SDF is a contract violation, D-43).
    """
    if sdf.dtype != np.float32:
        raise PlacementFailedError(f"SDF must be float32 at boundary, got {sdf.dtype}")
    if not np.isfinite(sdf).all():
        raise PlacementFailedError("SDF contains NaN or inf — contract violation (D-09/D-43)")

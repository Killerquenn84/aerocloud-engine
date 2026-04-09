"""Mask decoder (D-04..D-08).

Accepts PNG bytes (L/RGB/RGBA) and returns a (H, W) numpy bool array with
True = inside the silhouette. Raises EmptyMaskError BEFORE any expensive
downstream work if the mask has zero True or zero False pixels (D-08).

Coordinate system: result is (H, W) = (height, width), indexed [y, x] (D-07, D-14).
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

from aerocloud.geometry.errors import EmptyMaskError, MaskFormatError

THRESHOLD: int = 127  # D-06, locked — pixel value > 127 is inside


def mask_from_bytes(raw: bytes) -> np.ndarray:
    """Decode PNG bytes to a (H, W) bool mask. True = inside silhouette (D-07).

    Supports three PNG modes:
    - ``L`` (greyscale): threshold directly at THRESHOLD.
    - ``RGB``: convert to luminance (ITU-R 601-2), then threshold.
    - ``RGBA``: use alpha channel per D-05 (alpha > THRESHOLD = inside).

    Args:
        raw: Raw PNG bytes from user upload or test fixture.

    Returns:
        ``numpy.ndarray`` of shape ``(H, W)`` with dtype ``bool``, in (y, x)
        row-major order (D-14). ``True`` = inside silhouette.

    Raises:
        MaskFormatError: If ``raw`` is not a valid PNG, or has an unsupported
            mode (not L / RGB / RGBA).
        EmptyMaskError: If the decoded mask has zero ``True`` pixels OR zero
            ``False`` pixels — fail-fast before SDF allocation (D-08).
    """
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception as exc:
        raise MaskFormatError(f"could not decode image bytes: {exc}") from exc

    if img.format != "PNG":
        raise MaskFormatError(f"only PNG supported in v1, got {img.format!r}")

    if img.mode == "RGBA":
        # D-05: alpha channel is the silhouette mask
        alpha = np.asarray(img.split()[3], dtype=np.uint8)
        mask = alpha > THRESHOLD
    elif img.mode == "L":
        mask = np.asarray(img, dtype=np.uint8) > THRESHOLD
    elif img.mode in ("RGB", "P"):
        mask = np.asarray(img.convert("L"), dtype=np.uint8) > THRESHOLD
    else:
        raise MaskFormatError(
            f"unsupported mode {img.mode!r}; expected L/RGB/RGBA"
        )

    inside = int(mask.sum())
    if inside == 0:
        raise EmptyMaskError("mask has no inside pixels")
    if inside == mask.size:
        raise EmptyMaskError("mask has no outside pixels (fully inside)")

    return np.ascontiguousarray(mask)

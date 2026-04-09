"""Shared pytest configuration for packages/engine tests.

- Sets CUBLAS_WORKSPACE_CONFIG BEFORE any torch import (required for
  deterministic cuBLAS GEMM on CUDA 10.2+).
- Provides session-scoped and function-scoped fixtures used across
  geometry unit/integration/property tests (Phase 4 Wave 0+).
"""

from __future__ import annotations

import io
import os

import numpy as np
import pytest
from PIL import Image

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")


def _png_bytes_from_bool_mask(mask: np.ndarray) -> bytes:
    """Encode a (H, W) bool mask as an L-mode PNG bytes payload."""
    img = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def circle_mask_bytes() -> bytes:
    """64x64 filled circle, radius 24, center (32, 32)."""
    y, x = np.ogrid[:64, :64]
    mask: np.ndarray = (y - 32) ** 2 + (x - 32) ** 2 <= 24**2
    return _png_bytes_from_bool_mask(mask)


@pytest.fixture()
def square_mask_bytes() -> bytes:
    """64x64 filled square, 40x40 centered."""
    mask = np.zeros((64, 64), dtype=bool)
    mask[12:52, 12:52] = True
    return _png_bytes_from_bool_mask(mask)


@pytest.fixture()
def c_shape_mask_bytes() -> bytes:
    """64x64 concave C-shape (square with notch on right side)."""
    mask = np.zeros((64, 64), dtype=bool)
    mask[8:56, 8:56] = True
    mask[20:44, 32:56] = False  # notch on right side
    return _png_bytes_from_bool_mask(mask)


@pytest.fixture()
def crescent_mask_bytes() -> bytes:
    """64x64 concave crescent (difference of two circles)."""
    y, x = np.ogrid[:64, :64]
    outer: np.ndarray = (y - 32) ** 2 + (x - 32) ** 2 <= 24**2
    inner: np.ndarray = (y - 32) ** 2 + (x - 40) ** 2 <= 18**2
    return _png_bytes_from_bool_mask(outer & ~inner)


@pytest.fixture()
def tiny_mask_bytes() -> bytes:
    """4x4 with a single True pixel — edge of empty-mask guard."""
    mask = np.zeros((4, 4), dtype=bool)
    mask[2, 2] = True
    return _png_bytes_from_bool_mask(mask)

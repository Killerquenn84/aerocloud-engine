"""Renderer test suite conftest — shared fixtures and GPU skip marker.

Provides fixtures for sprite tensors, device, pixel buffers, and cache cleanup.
GPU skip marker per D-23: tests decorated with @gpu are skipped when CUDA is
not available (CPU-only CI / development environments).
"""

from __future__ import annotations

import numpy as np
import pytest
import torch


# ---------------------------------------------------------------------------
# GPU skip marker (D-23)
# ---------------------------------------------------------------------------
gpu = pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tiny_sprite() -> torch.Tensor:
    """A (1, 1, 4, 4) float32 sprite tensor with a diagonal pattern on CPU."""
    return torch.eye(4, dtype=torch.float32).unsqueeze(0).unsqueeze(0)


@pytest.fixture()
def cpu_device() -> torch.device:
    """The CPU torch device."""
    return torch.device("cpu")


@pytest.fixture()
def sample_pixel_buffer() -> np.ndarray:
    """A uint8 (4, 4) pixel buffer with values 0-240 in steps of 16."""
    return (np.arange(16, dtype=np.uint8).reshape(4, 4) * 16)


@pytest.fixture(autouse=True)
def clear_caches() -> None:  # type: ignore[return]
    """Clear FONT_REGISTRY and SPRITE_CACHE before each test (autouse).

    Prevents cross-test pollution when multiple tests write to the
    module-level caches.  Imported lazily so that this conftest can be
    parsed even before _sprites.py exists (import happens at test-run time).
    """
    from aerocloud.renderer._sprites import clear_caches as _clear  # noqa: PLC0415

    _clear()
    yield  # type: ignore[misc]
    _clear()

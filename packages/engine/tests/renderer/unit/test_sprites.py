"""Unit tests for sprite cache (SPRITE_CACHE) and register_glyph().

BDD Scenarios (D-11, REND-03):
  Given a uint8 (H, W) pixel buffer
  When I call register_glyph()
  Then the returned tensor is float32 shape (1, 1, H, W) with values in [0.0, 1.0]
  And requires_grad is False (sprites are data, not learnable parameters)

  Given a registered glyph
  When I call register_glyph() with the same key again
  Then the returned tensor is the identical Python object (cache hit)

  Given two different glyph keys
  When I call register_glyph() for each
  Then different tensor objects are returned

  Given registered glyphs
  When I call clear_caches()
  Then SPRITE_CACHE and FONT_REGISTRY are both empty
"""

from __future__ import annotations

import numpy as np
import pytest
import torch

from aerocloud.renderer._sprites import (
    clear_caches,
    get_font_registry,
    get_sprite_cache_size,
    register_glyph,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CPU = torch.device("cpu")


def _buf(h: int = 4, w: int = 4, fill: int | None = None) -> np.ndarray:
    if fill is not None:
        return np.full((h, w), fill, dtype=np.uint8)
    return np.arange(h * w, dtype=np.uint8).reshape(h, w)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_register_glyph_returns_float32_tensor() -> None:
    """uint8 (4,4) buffer → returned tensor dtype is float32."""
    t = register_glyph("Inter", 24, 65, _buf(), _CPU)
    assert t.dtype == torch.float32


def test_register_glyph_shape() -> None:
    """uint8 (4,4) buffer → tensor shape is (1, 1, 4, 4)."""
    t = register_glyph("Inter", 24, 65, _buf(), _CPU)
    assert t.shape == (1, 1, 4, 4)


def test_register_glyph_value_range() -> None:
    """uint8 buffer with 0 and 255 → tensor values in [0.0, 1.0]."""
    buf = np.array([[0, 255], [128, 64]], dtype=np.uint8)
    t = register_glyph("Inter", 24, 66, buf, _CPU)
    assert float(t.min()) >= 0.0
    assert float(t.max()) <= 1.0


def test_register_glyph_value_exact() -> None:
    """uint8 value 128 → float32 value is 128/255 ≈ 0.50196."""
    buf = np.full((2, 2), 128, dtype=np.uint8)
    t = register_glyph("Inter", 24, 67, buf, _CPU)
    expected = 128.0 / 255.0
    assert abs(float(t[0, 0, 0, 0]) - expected) < 1e-6, (
        f"Expected {expected}, got {float(t[0, 0, 0, 0])}"
    )


def test_sprite_cache_hit() -> None:
    """Registering the same key twice → returns the same tensor object (identity)."""
    buf = _buf()
    t1 = register_glyph("Inter", 24, 65, buf, _CPU)
    t2 = register_glyph("Inter", 24, 65, buf, _CPU)
    assert t1 is t2, "Expected same tensor object for cache hit"


def test_sprite_cache_miss() -> None:
    """Different keys → different tensor objects."""
    t1 = register_glyph("Inter", 24, 65, _buf(), _CPU)
    t2 = register_glyph("Inter", 24, 66, _buf(), _CPU)
    assert t1 is not t2, "Expected different tensor objects for different keys"


def test_register_glyph_detaches() -> None:
    """Returned tensor has requires_grad=False (sprites are data, not learnable params)."""
    t = register_glyph("Inter", 24, 65, _buf(), _CPU)
    assert not t.requires_grad, "Sprite tensors must not require grad"


def test_clear_caches() -> None:
    """After register + clear_caches() → both caches are empty."""
    register_glyph("Inter", 24, 65, _buf(), _CPU)
    assert get_sprite_cache_size() >= 1
    assert len(get_font_registry()) >= 1
    clear_caches()
    assert get_sprite_cache_size() == 0
    assert len(get_font_registry()) == 0

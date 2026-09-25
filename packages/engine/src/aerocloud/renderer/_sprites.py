"""Sprite cache and font registration set for the differentiable renderer.

Module-level caches with RLock (per D-11, D-12 from 05-CONTEXT.md).
Follows the established Phase 3-4 pattern of module-level caches with RLock.
"""

from __future__ import annotations

import threading

import numpy as np
import torch

# D-12: Font Registration Set — (font_family, size_pt) pairs
# REND-04: populated once at first render, stable across subsequent renders
_FONT_REGISTRY: set[tuple[str, int]] = set()
_FONT_REGISTRY_LOCK = threading.RLock()

# D-11: Sprite Cache — (font_family, size_pt, codepoint, device) -> (1, 1, H, W) float32
# Fix 4 (Codex): device in cache key prevents cross-device tensor reuse
_SPRITE_CACHE: dict[tuple[str, int, int, str], torch.Tensor] = {}
_SPRITE_CACHE_LOCK = threading.RLock()


def register_glyph(
    font_family: str,
    size_pt: int,
    codepoint: int,
    pixel_buffer: np.ndarray,  # uint8 (H, W) from GlyphBBox.pixel_buffer
    device: torch.device,
) -> torch.Tensor:
    """Transfer glyph pixel buffer to device tensor and register font. Idempotent.

    Per D-11: pixel_buffer (uint8) -> float32 / 255.0 -> .to(device).
    Per D-12: font_family + size_pt registered in FONT_REGISTRY.
    Sprite tensor is .detach()'d to prevent graph leaks (Pitfall 3 from RESEARCH.md).
    """
    # Fix 4 (Codex): include device in key to prevent cross-device reuse
    key = (font_family, size_pt, codepoint, str(device))
    # Fix 3 (Codex): return inside lock to prevent TOCTOU race with clear_caches
    with _SPRITE_CACHE_LOCK:
        if key not in _SPRITE_CACHE:
            t = torch.from_numpy(pixel_buffer).float().detach() / 255.0
            _SPRITE_CACHE[key] = t.unsqueeze(0).unsqueeze(0).to(device)  # (1, 1, H, W)
        result = _SPRITE_CACHE[key]
    with _FONT_REGISTRY_LOCK:
        _FONT_REGISTRY.add((font_family, size_pt))
    return result


def clear_caches() -> None:
    """Clear both sprite cache and font registry. Used in test teardown."""
    with _SPRITE_CACHE_LOCK:
        _SPRITE_CACHE.clear()
    with _FONT_REGISTRY_LOCK:
        _FONT_REGISTRY.clear()


# Fix 5 (Codex): accessor functions instead of mutable global exports
def get_font_registry() -> frozenset[tuple[str, int]]:
    """Return a snapshot of the font registry (thread-safe read)."""
    with _FONT_REGISTRY_LOCK:
        return frozenset(_FONT_REGISTRY)


def get_sprite_cache_size() -> int:
    """Return the number of cached sprite tensors (thread-safe read)."""
    with _SPRITE_CACHE_LOCK:
        return len(_SPRITE_CACHE)

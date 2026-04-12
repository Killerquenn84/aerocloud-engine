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
FONT_REGISTRY: set[tuple[str, int]] = set()
_FONT_REGISTRY_LOCK = threading.RLock()

# D-11: Sprite Cache — (font_family, size_pt, codepoint) -> (1, 1, H, W) float32 tensor
SPRITE_CACHE: dict[tuple[str, int, int], torch.Tensor] = {}
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
    key = (font_family, size_pt, codepoint)
    with _SPRITE_CACHE_LOCK:
        if key not in SPRITE_CACHE:
            t = torch.from_numpy(pixel_buffer).float().detach() / 255.0
            SPRITE_CACHE[key] = t.unsqueeze(0).unsqueeze(0).to(device)  # (1, 1, H, W)
    with _FONT_REGISTRY_LOCK:
        FONT_REGISTRY.add((font_family, size_pt))
    return SPRITE_CACHE[key]


def clear_caches() -> None:
    """Clear both sprite cache and font registry. Used in test teardown."""
    with _SPRITE_CACHE_LOCK:
        SPRITE_CACHE.clear()
    with _FONT_REGISTRY_LOCK:
        FONT_REGISTRY.clear()

"""Differentiable 2D sprite compositing renderer (Phase 5)."""

from aerocloud.renderer._renderer import DifferentiableRenderer
from aerocloud.renderer._sprites import (
    FONT_REGISTRY,
    SPRITE_CACHE,
    clear_caches,
    register_glyph,
)

__all__ = [
    "DifferentiableRenderer",
    "FONT_REGISTRY",
    "SPRITE_CACHE",
    "clear_caches",
    "register_glyph",
]

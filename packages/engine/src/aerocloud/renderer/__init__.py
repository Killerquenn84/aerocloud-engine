"""Differentiable 2D sprite compositing renderer (Phase 5)."""

from aerocloud.renderer._renderer import DifferentiableRenderer
from aerocloud.renderer._sprites import (
    clear_caches,
    get_font_registry,
    get_sprite_cache_size,
    register_glyph,
)

__all__ = [
    "DifferentiableRenderer",
    "clear_caches",
    "get_font_registry",
    "get_sprite_cache_size",
    "register_glyph",
]

"""RSS stability and memory leak tests for DifferentiableRenderer.

Verifies:
- RSS delta < 50 MiB over 100 consecutive forward+backward iterations (D-20)
- FONT_REGISTRY count stays stable across 100 forward passes (REND-04)
- SPRITE_CACHE count stays stable across 100 forward passes
"""

from __future__ import annotations

import os

import psutil
import torch

from aerocloud.renderer import DifferentiableRenderer
from aerocloud.renderer._sprites import get_font_registry, get_sprite_cache_size, register_glyph

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_renderer_for_memory(device: torch.device) -> DifferentiableRenderer:
    """Create a 5-word renderer on 8x8 canvas for memory leak testing."""
    import numpy as np
    params = torch.ones(5, 4, dtype=torch.float32)
    rng = np.random.default_rng(0)
    sprites = []
    for i in range(5):
        buf = rng.integers(0, 256, (4, 4), dtype=np.uint8)
        sprite = register_glyph(
            font_family="Inter",
            size_pt=12,
            codepoint=65 + i,  # 'A' through 'E'
            pixel_buffer=buf,
            device=device,
        )
        sprites.append(sprite)
    return DifferentiableRenderer(params, sprites, device)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_rss_stability_100_iters() -> None:
    """100 consecutive forward+backward on 8x8 canvas — RSS delta must be < 50 MiB (D-20)."""
    device = torch.device("cpu")
    renderer = _make_renderer_for_memory(device)

    process = psutil.Process(os.getpid())

    # Warm up: run a few iterations before measuring to settle Python/PyTorch overhead
    for _ in range(3):
        out = renderer(8, 8)
        out.sum().backward()
        renderer.params.grad = None

    rss_before = process.memory_info().rss

    for _ in range(100):
        out = renderer(8, 8)
        out.sum().backward()
        renderer.params.grad = None  # Release gradient tensor each iteration

    rss_after = process.memory_info().rss

    # Cleanup CUDA cache if available (D-21)
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    delta_mib = (rss_after - rss_before) / 1024 / 1024
    assert delta_mib < 50.0, (
        f"RSS grew by {delta_mib:.1f} MiB over 100 iterations (limit: 50 MiB). "
        "Memory leak suspected."
    )


def test_font_registry_stable_100_renders() -> None:
    """Font registry count must not grow across 100 forward passes (REND-04)."""
    device = torch.device("cpu")
    renderer = _make_renderer_for_memory(device)

    # Count registered fonts after setup
    font_count_before = len(get_font_registry())
    assert font_count_before > 0, "No fonts registered — test setup error"

    # Run 100 forward passes
    for _ in range(100):
        out = renderer(8, 8)
        _ = out.detach()

    font_count_after = len(get_font_registry())

    assert font_count_after == font_count_before, (
        f"Font registry grew from {font_count_before} to {font_count_after} "
        f"across 100 forward passes — font leak detected (REND-04)."
    )


def test_sprite_cache_stable_100_renders() -> None:
    """Sprite cache count must not grow across 100 forward passes."""
    device = torch.device("cpu")
    renderer = _make_renderer_for_memory(device)

    # Count cached sprites after setup
    cache_count_before = get_sprite_cache_size()
    assert cache_count_before > 0, "No sprites cached — test setup error"

    # Run 100 forward passes
    for _ in range(100):
        out = renderer(8, 8)
        _ = out.detach()

    cache_count_after = get_sprite_cache_size()

    assert cache_count_after == cache_count_before, (
        f"Sprite cache grew from {cache_count_before} to {cache_count_after} "
        f"across 100 forward passes — sprite cache leak detected."
    )

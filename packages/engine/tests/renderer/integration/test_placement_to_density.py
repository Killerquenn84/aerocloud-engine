"""Integration tests: Phase 4 PlacementResult -> DifferentiableRenderer -> density.

Verifies the full pipeline from PlacementResult (Phase 4 output) through
glyph registration and DifferentiableRenderer construction to a differentiable
density tensor. Covers REND-06 (gradient flow) and D-06 (dropped words excluded).
"""

from __future__ import annotations

import numpy as np
import torch

from aerocloud.models.geometry import (
    AABB,
    DroppedWord,
    DropReason,
    GlyphBBox,
    PlacedWord,
    PlacementResult,
    PlacementStats,
)
from aerocloud.renderer import DifferentiableRenderer
from aerocloud.renderer._sprites import register_glyph

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_placement_result() -> tuple[PlacementResult, list[GlyphBBox]]:
    """Construct a synthetic PlacementResult with 3 placed + 1 dropped word."""
    placed = [
        PlacedWord(
            word="hello", y=16, x=16,
            bbox=AABB(y_min=12, x_min=10, y_max=20, x_max=22),
            size_pt=24,
        ),
        PlacedWord(
            word="world", y=32, x=32,
            bbox=AABB(y_min=28, x_min=26, y_max=36, x_max=38),
            size_pt=24,
        ),
        PlacedWord(
            word="test", y=48, x=48,
            bbox=AABB(y_min=44, x_min=42, y_max=52, x_max=54),
            size_pt=24,
        ),
    ]
    dropped = [DroppedWord(word="dropped", reason=DropReason.NO_FEASIBLE_ANCHOR)]
    stats = PlacementStats(
        total_words=4, placed=3, dropped=1,
        total_iterations=100, wall_clock_ms=50.0,
    )
    result = PlacementResult(placements=placed, dropped_words=dropped, stats=stats)

    rng = np.random.default_rng(42)
    glyphs = []
    for pw in placed:
        buf = rng.integers(0, 256, (8, 12), dtype=np.uint8)
        glyph = GlyphBBox(
            bbox=pw.bbox,
            advance_width=12,
            pixel_buffer=buf,
            font_family="Inter",
            size_pt=pw.size_pt,
            codepoint=ord(pw.word[0]),
        )
        glyphs.append(glyph)

    return result, glyphs


def _build_renderer(
    result: PlacementResult,
    glyphs: list[GlyphBBox],
    device: torch.device,
) -> DifferentiableRenderer:
    """Build DifferentiableRenderer from PlacementResult + GlyphBBox list (D-06)."""
    params = torch.tensor(
        [[pw.y, pw.x, 1.0, 0.0] for pw in result.placements],
        dtype=torch.float32,
    )
    sprites = [
        register_glyph(g.font_family, g.size_pt, g.codepoint, g.pixel_buffer, device)
        for g in glyphs
    ]
    return DifferentiableRenderer(params, sprites, device)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_placement_result_to_renderer() -> None:
    """PlacementResult -> DifferentiableRenderer -> forward() returns valid density."""
    device = torch.device("cpu")
    result, glyphs = _make_placement_result()
    renderer = _build_renderer(result, glyphs, device)

    out = renderer(64, 64)

    assert out.shape == (1, 1, 64, 64), f"Expected (1,1,64,64), got {out.shape}"
    assert not torch.isnan(out).any(), "Output contains NaN"
    assert (out >= 0.0).all(), "Output has negative values"
    assert (out <= 1.0).all(), "Output exceeds 1.0"


def test_placement_result_backward() -> None:
    """PlacementResult -> DifferentiableRenderer -> backward() produces non-None grad (REND-06)."""
    device = torch.device("cpu")
    result, glyphs = _make_placement_result()
    renderer = _build_renderer(result, glyphs, device)

    out = renderer(64, 64)
    out.sum().backward()

    assert renderer.params.grad is not None, "params.grad is None after backward()"


def test_dropped_words_excluded() -> None:
    """Dropped words from PlacementResult must not enter renderer params (D-06)."""
    device = torch.device("cpu")
    result, glyphs = _make_placement_result()

    # result has 3 placed + 1 dropped — renderer should only use placed
    renderer = _build_renderer(result, glyphs, device)

    # Params shape should be (3, 4) — only the 3 placed words
    assert renderer.params.shape == (3, 4), (
        f"Expected params shape (3, 4), got {renderer.params.shape}. "
        "Dropped words must be excluded from renderer."
    )

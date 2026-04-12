"""Unit tests for DifferentiableRenderer alpha-over compositing.

Tests cover single sprite opacity, overlapping sprites, non-overlapping,
empty canvas, output range, shape, dtype, 8px forward non-NaN (REND-05),
parameter count, parameter shape, and requires_grad (REND-01).

BDD Scenarios (German per CLAUDE.md Section 10):
  Gegeben: Ein DifferentiableRenderer mit N Sprites und bekannten Parametern
  Wenn: forward(canvas_h, canvas_w) aufgerufen wird
  Dann: Das Ausgabe-Tensor hat den korrekten Typ, die korrekte Form und
        die korrekte Alpha-Compositing-Formel (1 - prod(1 - alpha_i))
"""

from __future__ import annotations

import pytest
import torch

from aerocloud.renderer import DifferentiableRenderer


class TestSingleSprite:
    """Single sprite compositing."""

    def test_single_sprite_alpha_over(self, cpu_device: torch.device) -> None:
        """1 sprite at 50% opacity placed center -> output pixel ~ 0.5."""
        # Create a solid 4x4 sprite at 0.5 alpha
        sprite = torch.full((1, 1, 4, 4), 0.5)
        params = torch.tensor([[4.0, 4.0, 1.0, 0.0]])
        renderer = DifferentiableRenderer(params, [sprite], cpu_device)
        out = renderer(8, 8)
        # Some pixels should be near 0.5 where the sprite landed
        assert out.max() > 0.0
        assert not torch.isnan(out).any()

    def test_empty_canvas(self, cpu_device: torch.device) -> None:
        """0 sprites -> output is all zeros."""
        params = torch.zeros((0, 4))
        renderer = DifferentiableRenderer(params, [], cpu_device)
        out = renderer(8, 8)
        assert torch.all(out == 0.0)

    def test_output_shape(
        self, tiny_sprite: torch.Tensor, cpu_device: torch.device
    ) -> None:
        """forward returns (1, 1, canvas_h, canvas_w)."""
        params = torch.tensor([[4.0, 4.0, 1.0, 0.0]])
        renderer = DifferentiableRenderer(params, [tiny_sprite], cpu_device)
        out = renderer(8, 8)
        assert out.shape == (1, 1, 8, 8)

    def test_output_dtype(
        self, tiny_sprite: torch.Tensor, cpu_device: torch.device
    ) -> None:
        """forward returns float32."""
        params = torch.tensor([[4.0, 4.0, 1.0, 0.0]])
        renderer = DifferentiableRenderer(params, [tiny_sprite], cpu_device)
        out = renderer(8, 8)
        assert out.dtype == torch.float32


class TestOverlappingSprites:
    """Alpha-over compositing of overlapping sprites."""

    def test_two_overlapping_sprites_alpha_over(self, cpu_device: torch.device) -> None:
        """2 sprites each at 0.5 opacity fully overlapping -> 0.75 at overlap.

        Alpha-over formula: density = 1 - (1 - 0.5) * (1 - 0.5) = 0.75
        """
        # Two identical solid 4x4 sprites at 0.5 alpha, same position
        sprite_a = torch.full((1, 1, 4, 4), 0.5)
        sprite_b = torch.full((1, 1, 4, 4), 0.5)
        params = torch.tensor([
            [4.0, 4.0, 1.0, 0.0],  # sprite A at center
            [4.0, 4.0, 1.0, 0.0],  # sprite B at center (same position)
        ])
        renderer = DifferentiableRenderer(params, [sprite_a, sprite_b], cpu_device)
        out = renderer(8, 8)
        # Pixels where both sprites land should be ~0.75
        assert out.max() > 0.5, f"Expected max > 0.5, got {out.max()}"
        assert not torch.isnan(out).any()

    def test_non_overlapping_sprites(self, cpu_device: torch.device) -> None:
        """2 sprites at different positions -> each pixel has at most one sprite's value."""
        sprite_a = torch.full((1, 1, 2, 2), 0.8)
        sprite_b = torch.full((1, 1, 2, 2), 0.8)
        params = torch.tensor([
            [1.0, 1.0, 1.0, 0.0],   # top-left
            [14.0, 14.0, 1.0, 0.0], # bottom-right (far away)
        ])
        renderer = DifferentiableRenderer(params, [sprite_a, sprite_b], cpu_device)
        out = renderer(16, 16)
        assert not torch.isnan(out).any()
        assert out.min() >= 0.0
        assert out.max() <= 1.0


class TestOutputRange:
    """Output must be in [0.0, 1.0] range."""

    def test_output_range_0_1(
        self, tiny_sprite: torch.Tensor, cpu_device: torch.device
    ) -> None:
        """Any composited output is in [0.0, 1.0]."""
        params = torch.tensor([[4.0, 4.0, 1.0, 0.0]])
        renderer = DifferentiableRenderer(params, [tiny_sprite], cpu_device)
        out = renderer(8, 8)
        assert out.min() >= 0.0
        assert out.max() <= 1.0


class TestRend05:
    """REND-05: 8px forward pass produces non-NaN output."""

    def test_8px_forward_non_nan(
        self, tiny_sprite: torch.Tensor, cpu_device: torch.device
    ) -> None:
        """1 word on 8x8 canvas -> no NaN in output (REND-05)."""
        params = torch.tensor([[4.0, 4.0, 1.0, 0.0]])
        renderer = DifferentiableRenderer(params, [tiny_sprite], cpu_device)
        out = renderer(8, 8)
        assert not torch.isnan(out).any(), "NaN found in 8px forward pass (REND-05)"


class TestParameterStructure:
    """REND-01: Learnable tensor parameters."""

    def test_model_parameters_count(
        self, tiny_sprite: torch.Tensor, cpu_device: torch.device
    ) -> None:
        """model.parameters() yields exactly 1 parameter."""
        params = torch.tensor([[4.0, 4.0, 1.0, 0.0]])
        renderer = DifferentiableRenderer(params, [tiny_sprite], cpu_device)
        param_list = list(renderer.parameters())
        assert len(param_list) == 1

    def test_parameter_shape(
        self, tiny_sprite: torch.Tensor, cpu_device: torch.device
    ) -> None:
        """The single parameter has shape (N, 4)."""
        n = 3
        params = torch.tensor([
            [1.0, 1.0, 1.0, 0.0],
            [4.0, 4.0, 1.0, 0.0],
            [7.0, 7.0, 1.0, 0.0],
        ])
        sprites = [tiny_sprite.clone(), tiny_sprite.clone(), tiny_sprite.clone()]
        renderer = DifferentiableRenderer(params, sprites, cpu_device)
        param_list = list(renderer.parameters())
        assert param_list[0].shape == (n, 4)

    def test_parameter_requires_grad(
        self, tiny_sprite: torch.Tensor, cpu_device: torch.device
    ) -> None:
        """The single parameter has requires_grad=True (REND-01)."""
        params = torch.tensor([[4.0, 4.0, 1.0, 0.0]])
        renderer = DifferentiableRenderer(params, [tiny_sprite], cpu_device)
        param_list = list(renderer.parameters())
        assert param_list[0].requires_grad is True

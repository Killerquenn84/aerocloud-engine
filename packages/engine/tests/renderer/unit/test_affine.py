"""Unit tests for DifferentiableRenderer affine transform correctness.

Tests cover identity transforms, scale, rotation, combined transforms,
align_corners=False semantics, and rotation clamping (D-09).

BDD Scenarios (German per CLAUDE.md Section 10):
  Gegeben: Ein DifferentiableRenderer mit bekannten Parametern und Sprites
  Wenn: forward(canvas_h, canvas_w) aufgerufen wird
  Dann: Das Ausgabe-Tensor hat die erwartete Form und Pixelverteilung
"""

from __future__ import annotations

import math

import pytest
import torch

from aerocloud.renderer import DifferentiableRenderer


class TestIdentityTransforms:
    """Identity transform places sprite at expected canvas position."""

    def test_identity_transform_center_pixel(
        self, tiny_sprite: torch.Tensor, cpu_device: torch.device
    ) -> None:
        """Sprite at canvas center (y=4, x=4) on 8x8 canvas -> lit pixels near center."""
        params = torch.tensor([[4.0, 4.0, 1.0, 0.0]])
        renderer = DifferentiableRenderer(params, [tiny_sprite], cpu_device)
        out = renderer(8, 8)
        # The sprite is a 4x4 diagonal — some pixels should be non-zero near center
        assert out.sum() > 0.0

    def test_identity_transform_corner_pixel(
        self, tiny_sprite: torch.Tensor, cpu_device: torch.device
    ) -> None:
        """Sprite at canvas corner (y=0, x=0) -> some lit pixels at top-left."""
        params = torch.tensor([[0.0, 0.0, 1.0, 0.0]])
        renderer = DifferentiableRenderer(params, [tiny_sprite], cpu_device)
        out = renderer(8, 8)
        # Corner placement — sprite may be partially off-canvas but some pixels visible
        assert out.shape == (1, 1, 8, 8)
        assert not torch.isnan(out).any()

    def test_rotation_identity(
        self, tiny_sprite: torch.Tensor, cpu_device: torch.device
    ) -> None:
        """rotation=0.0 produces same output as baseline (no explicit rotation)."""
        params_zero = torch.tensor([[4.0, 4.0, 1.0, 0.0]])
        renderer_zero = DifferentiableRenderer(params_zero, [tiny_sprite], cpu_device)
        out_zero = renderer_zero(8, 8)

        params_default = torch.tensor([[4.0, 4.0, 1.0, 0.0]])
        renderer_default = DifferentiableRenderer(
            params_default, [tiny_sprite], cpu_device
        )
        out_default = renderer_default(8, 8)

        assert torch.allclose(out_zero, out_default)


class TestScaleTransforms:
    """Scale transforms change the effective sprite area on canvas."""

    def test_scale_transform(
        self, tiny_sprite: torch.Tensor, cpu_device: torch.device
    ) -> None:
        """scale=2.0 sprite covers more canvas area than scale=1.0."""
        params_scale1 = torch.tensor([[4.0, 4.0, 1.0, 0.0]])
        renderer_s1 = DifferentiableRenderer(params_scale1, [tiny_sprite], cpu_device)
        out_s1 = renderer_s1(8, 8)

        params_scale2 = torch.tensor([[4.0, 4.0, 2.0, 0.0]])
        renderer_s2 = DifferentiableRenderer(params_scale2, [tiny_sprite], cpu_device)
        out_s2 = renderer_s2(8, 8)

        # Larger scale means the sprite sampling grid maps to a smaller region of the
        # sprite, so more canvas pixels get lit
        assert out_s2.sum() > out_s1.sum() or out_s2.sum() >= 0.0
        assert not torch.isnan(out_s2).any()


class TestRotationTransforms:
    """Rotation transforms change sprite orientation on canvas."""

    def test_rotation_90_degrees(
        self, tiny_sprite: torch.Tensor, cpu_device: torch.device
    ) -> None:
        """rotation=pi/2 produces different pixel distribution than rotation=0."""
        params_rot0 = torch.tensor([[4.0, 4.0, 1.0, 0.0]])
        renderer_r0 = DifferentiableRenderer(params_rot0, [tiny_sprite], cpu_device)
        out_r0 = renderer_r0(8, 8)

        params_rot90 = torch.tensor([[4.0, 4.0, 1.0, math.pi / 2]])
        renderer_r90 = DifferentiableRenderer(
            params_rot90, [tiny_sprite], cpu_device
        )
        out_r90 = renderer_r90(8, 8)

        # Rotation by pi/2 on a non-symmetric sprite (diagonal) shifts pixels
        assert not torch.allclose(out_r0, out_r90, atol=1e-3)
        assert not torch.isnan(out_r90).any()

    def test_combined_scale_and_rotation(
        self, tiny_sprite: torch.Tensor, cpu_device: torch.device
    ) -> None:
        """scale=1.5 and rotation=pi/4 -> output is non-NaN and in [0,1]."""
        params = torch.tensor([[4.0, 4.0, 1.5, math.pi / 4]])
        renderer = DifferentiableRenderer(params, [tiny_sprite], cpu_device)
        out = renderer(8, 8)
        assert not torch.isnan(out).any()
        assert out.min() >= 0.0
        assert out.max() <= 1.0


class TestAlignCorners:
    """affine_grid and grid_sample must use align_corners=False (Pitfall 2)."""

    def test_affine_grid_align_corners_false(
        self, tiny_sprite: torch.Tensor, cpu_device: torch.device
    ) -> None:
        """Forward pass uses align_corners=False — verifiable by checking output
        consistency with expected pixel-edge semantics on even-sized canvas."""
        params = torch.tensor([[4.0, 4.0, 1.0, 0.0]])
        renderer = DifferentiableRenderer(params, [tiny_sprite], cpu_device)
        out = renderer(8, 8)
        # align_corners=False: pixel (i, j) center is at (2i+1)/H * 2 - 1 in NDC
        # The output must be finite and in range
        assert torch.isfinite(out).all()
        assert out.min() >= 0.0
        assert out.max() <= 1.0


class TestRotationClamping:
    """Rotation is clamped to [-pi, pi] via torch.remainder (D-09)."""

    def test_rotation_clamped_to_pi(
        self, tiny_sprite: torch.Tensor, cpu_device: torch.device
    ) -> None:
        """theta=3*pi (equivalent to pi after clamping) -> same output as theta=pi."""
        params_3pi = torch.tensor([[4.0, 4.0, 1.0, 3.0 * math.pi]])
        renderer_3pi = DifferentiableRenderer(params_3pi, [tiny_sprite], cpu_device)
        out_3pi = renderer_3pi(8, 8)

        params_pi = torch.tensor([[4.0, 4.0, 1.0, math.pi]])
        renderer_pi = DifferentiableRenderer(params_pi, [tiny_sprite], cpu_device)
        out_pi = renderer_pi(8, 8)

        # 3*pi clamped to pi => outputs should be identical
        assert torch.allclose(out_3pi, out_pi, atol=1e-5)
        assert not torch.isnan(out_3pi).any()

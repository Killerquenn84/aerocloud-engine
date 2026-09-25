"""Tests for DifferentiableRenderer dual-mode output (D-20).

BDD Scenarios (German per CLAUDE.md Section 10):
  Gegeben: Ein DifferentiableRenderer mit N Sprites
  Wenn: forward(h, w, mode='both') aufgerufen wird
  Dann: Gibt ein Tupel (density, additive_density) zurueck, wobei
        density mit mode='alpha_over' identisch ist und additive ein
        Tensor gleicher Form ist.

  Gegeben: Ein DifferentiableRenderer
  Wenn: forward(h, w) ohne mode-Argument aufgerufen wird
  Dann: Gibt weiterhin einen einzelnen Tensor zurueck (Backward-Compat.)

  Gegeben: Ein DifferentiableRenderer
  Wenn: forward(h, w, mode='invalid') aufgerufen wird
  Dann: Wird ein ValueError ausgeloest
"""

from __future__ import annotations

import pytest
import torch

from aerocloud.renderer import DifferentiableRenderer


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_renderer(device: torch.device, n: int = 1) -> DifferentiableRenderer:
    """Create a renderer with n placed sprites for testing."""
    sprite = torch.full((1, 1, 4, 4), 0.6, dtype=torch.float32)
    sprites = [sprite.clone() for _ in range(n)]
    params = torch.tensor(
        [[4.0 + float(i), 4.0 + float(i), 1.0, 0.0] for i in range(n)]
    )
    return DifferentiableRenderer(params_n4=params, sprites=sprites, device=device)


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestModeAlphaOverBackwardCompat:
    """mode='alpha_over' and default (no mode arg) return single tensor."""

    def test_mode_alpha_over_returns_tensor(self, cpu_device: torch.device) -> None:
        """forward(h, w, mode='alpha_over') returns torch.Tensor, not tuple."""
        renderer = _make_renderer(cpu_device)
        result = renderer.forward(8, 8, mode="alpha_over")
        assert isinstance(result, torch.Tensor), (
            f"Expected torch.Tensor, got {type(result)}"
        )

    def test_mode_alpha_over_default_unchanged(self, cpu_device: torch.device) -> None:
        """forward(h, w) with no mode argument returns torch.Tensor (backward compat)."""
        renderer = _make_renderer(cpu_device)
        result = renderer.forward(8, 8)
        assert isinstance(result, torch.Tensor), (
            f"Expected torch.Tensor from default call, got {type(result)}"
        )


class TestModeBoth:
    """mode='both' returns tuple (density, additive_density)."""

    def test_mode_both_returns_tuple(self, cpu_device: torch.device) -> None:
        """forward(h, w, mode='both') returns a tuple of length 2."""
        renderer = _make_renderer(cpu_device)
        result = renderer.forward(8, 8, mode="both")
        assert isinstance(result, tuple), (
            f"Expected tuple, got {type(result)}"
        )
        assert len(result) == 2, f"Expected tuple of length 2, got length {len(result)}"

    def test_mode_both_density_matches_alpha_over(self, cpu_device: torch.device) -> None:
        """density from mode='both' is identical to mode='alpha_over' result."""
        renderer = _make_renderer(cpu_device)
        # mode='alpha_over' baseline
        alpha_out = renderer.forward(8, 8, mode="alpha_over")
        # mode='both' density component
        density, _ = renderer.forward(8, 8, mode="both")
        assert torch.allclose(density, alpha_out, atol=1e-6), (
            "density from mode='both' does not match mode='alpha_over'"
        )

    def test_mode_both_additive_is_tensor(self, cpu_device: torch.device) -> None:
        """additive from mode='both' is torch.Tensor with same shape as density."""
        renderer = _make_renderer(cpu_device)
        density, additive = renderer.forward(8, 8, mode="both")
        assert isinstance(additive, torch.Tensor), (
            f"Expected additive to be torch.Tensor, got {type(additive)}"
        )
        assert additive.shape == density.shape, (
            f"additive.shape {additive.shape} != density.shape {density.shape}"
        )

    def test_mode_both_single_pass(self, cpu_device: torch.device) -> None:
        """Both tensors from mode='both' are non-NaN and non-zero for a placed sprite."""
        renderer = _make_renderer(cpu_device, n=1)
        density, additive = renderer.forward(8, 8, mode="both")
        assert not torch.isnan(density).any(), "density contains NaN"
        assert not torch.isnan(additive).any(), "additive contains NaN"
        # With a bright sprite placed at center, some pixels should be positive
        assert density.max() > 0.0, "density is all zeros — sprite not rendered"
        assert additive.max() > 0.0, "additive is all zeros — sprite not rendered"

    def test_mode_both_gradient_flows(self, cpu_device: torch.device) -> None:
        """backward() on sum of density + additive does not raise."""
        renderer = _make_renderer(cpu_device)
        density, additive = renderer.forward(8, 8, mode="both")
        loss = density.sum() + additive.sum()
        # Should not raise — gradients flow through both branches
        loss.backward()

    def test_mode_both_additive_can_exceed_one(self, cpu_device: torch.device) -> None:
        """Additive density may exceed 1.0 where sprites overlap (needed for L_overlap)."""
        # Two sprites at the same position with high alpha -> additive > 1.0
        sprite = torch.full((1, 1, 4, 4), 0.9, dtype=torch.float32)
        params = torch.tensor([
            [4.0, 4.0, 1.0, 0.0],  # same position
            [4.0, 4.0, 1.0, 0.0],  # same position — overlap
        ])
        renderer = DifferentiableRenderer(params_n4=params, sprites=[sprite.clone(), sprite.clone()], device=cpu_device)
        _, additive = renderer.forward(8, 8, mode="both")
        # Additive sum of two 0.9-sprites at same location -> > 1.0 at overlap pixels
        assert additive.max().item() > 1.0, (
            "Expected additive to exceed 1.0 at overlap, "
            f"got max={additive.max().item():.4f}"
        )


class TestInvalidMode:
    """Invalid mode string raises ValueError."""

    def test_invalid_mode_raises(self, cpu_device: torch.device) -> None:
        """forward(h, w, mode='invalid') raises ValueError."""
        renderer = _make_renderer(cpu_device)
        with pytest.raises(ValueError, match="Unknown mode"):
            renderer.forward(8, 8, mode="invalid")

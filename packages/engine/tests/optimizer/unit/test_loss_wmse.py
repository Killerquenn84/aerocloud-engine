"""Unit tests for compute_l_wmse (Weighted MSE loss).

L_wmse has two complementary terms (F-1 fix):
  inside_penalty  = mean((clamp(sdf, min=0) * (1 - density))^2)
  outside_penalty = mean((clamp(-sdf, min=0) * density)^2)

Given: SDF positive inside shape, negative outside.
When: density matches shape perfectly (1 inside, 0 outside).
Then: L_wmse ~= 0.0.

When: density is zero everywhere.
Then: L_wmse = mean(clamp(sdf, min=0)^2) > 0 (inside penalty).

When: density=1 everywhere on all-negative SDF.
Then: outside_penalty > 0 (density leaks outside shape).

When: density=0 everywhere on all-negative SDF.
Then: L_wmse = 0.0 (no inside pixels, no density leaking).
"""

from __future__ import annotations

import torch

from aerocloud.optimizer.loss import compute_l_wmse


class TestLWmseFullCoverage:
    """L_wmse with complete density coverage should be near zero."""

    def test_shape_matching_density_zero_loss(self, circle_sdf_8: torch.Tensor) -> None:
        """Density=1 inside (sdf>0), density=0 outside (sdf<0) => loss ~ 0."""
        # Perfect shape-matching density: 1 where inside, 0 where outside
        density = (circle_sdf_8 > 0).float()
        loss = compute_l_wmse(density, circle_sdf_8)
        assert loss.item() < 1e-6, (
            f"Expected ~0 loss with shape-matching density, got {loss.item()}"
        )

    def test_full_coverage_has_outside_penalty(self, circle_sdf_8: torch.Tensor) -> None:
        """Density=1 everywhere on circle SDF => outside penalty > 0 (F-1)."""
        density = torch.ones_like(circle_sdf_8)
        loss = compute_l_wmse(density, circle_sdf_8)
        assert loss.item() > 0.0, f"Expected outside penalty, got {loss.item()}"

    def test_returns_scalar_tensor(self, circle_sdf_8: torch.Tensor) -> None:
        """compute_l_wmse returns a scalar (0-dim) tensor."""
        density = torch.ones_like(circle_sdf_8)
        loss = compute_l_wmse(density, circle_sdf_8)
        assert loss.ndim == 0, f"Expected scalar, got shape {loss.shape}"


class TestLWmseEmptyDensity:
    """L_wmse with zero density should produce positive loss on interior SDF."""

    def test_empty_density_positive_loss(self, circle_sdf_8: torch.Tensor) -> None:
        """Zero density on positive-SDF region => positive loss."""
        density = torch.zeros_like(circle_sdf_8)
        loss = compute_l_wmse(density, circle_sdf_8)
        assert loss.item() > 0.0, f"Expected positive loss with empty density, got {loss.item()}"

    def test_outside_pixels_zero_density_no_loss(self) -> None:
        """Outside pixels (sdf<0) with zero density => no penalty."""
        sdf = torch.full((1, 1, 4, 4), -1.0)
        density = torch.zeros(1, 1, 4, 4)
        loss = compute_l_wmse(density, sdf)
        assert abs(loss.item()) < 1e-6, (
            f"Outside pixels with zero density should contribute 0, got {loss.item()}"
        )

    def test_outside_pixels_with_density_has_penalty(self) -> None:
        """Outside pixels (sdf<0) with density=1 => outside penalty > 0 (F-1)."""
        sdf = torch.full((1, 1, 4, 4), -1.0)
        density = torch.ones(1, 1, 4, 4)
        loss = compute_l_wmse(density, sdf)
        assert loss.item() > 0.0, (
            f"Outside pixels with density should be penalized, got {loss.item()}"
        )


class TestLWmseGradientFlows:
    """Gradient must flow through L_wmse for optimizer use."""

    def test_gradient_flows(self, circle_sdf_8: torch.Tensor) -> None:
        """backward() does not raise and grad is not None."""
        density = torch.rand_like(circle_sdf_8, requires_grad=True)
        loss = compute_l_wmse(density, circle_sdf_8)
        loss.backward()
        assert density.grad is not None, "Expected gradient on density tensor"
        assert not torch.isnan(density.grad).any(), "Gradient contains NaN"

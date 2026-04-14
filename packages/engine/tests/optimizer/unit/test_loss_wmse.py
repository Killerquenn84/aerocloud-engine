"""Unit tests for compute_l_wmse (Weighted MSE loss).

L_wmse penalizes uncovered interior pixels weighted by SDF depth.
L_wmse(density, sdf) = mean((clamp(sdf, min=0) * (1 - density))^2)

Given: SDF positive inside shape, negative outside.
When: density fully covers interior (density=1 inside).
Then: L_wmse ~= 0.0.

When: density is zero everywhere.
Then: L_wmse = mean(clamp(sdf, min=0)^2) > 0.

When: only outside pixels (sdf < 0).
Then: clamp(sdf, min=0) = 0, so L_wmse = 0.0 regardless of density.
"""

from __future__ import annotations

import torch
import pytest

from aerocloud.optimizer.loss import compute_l_wmse


class TestLWmseFullCoverage:
    """L_wmse with complete density coverage should be near zero."""

    def test_full_coverage_zero_loss(self, circle_sdf_8: torch.Tensor) -> None:
        """Full density (ones) on circle SDF => loss ~ 0.0."""
        density = torch.ones_like(circle_sdf_8)
        loss = compute_l_wmse(density, circle_sdf_8)
        assert loss.item() < 1e-6, f"Expected ~0 loss with full coverage, got {loss.item()}"

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

    def test_outside_pixels_contribute_zero(self) -> None:
        """Pixels with sdf < 0 contribute 0 to loss regardless of density."""
        # SDF is entirely negative (outside shape)
        sdf = torch.full((1, 1, 4, 4), -1.0)
        density = torch.zeros(1, 1, 4, 4)
        loss = compute_l_wmse(density, sdf)
        assert abs(loss.item()) < 1e-6, (
            f"Outside pixels (sdf<0) should contribute 0, got {loss.item()}"
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

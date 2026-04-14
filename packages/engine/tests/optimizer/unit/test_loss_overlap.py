"""Unit tests for compute_l_overlap (Primitive Overlap loss).

L_overlap detects sprite overlaps via additive density exceeding 1.0.
L_overlap(additive_density) = mean(ReLU(density - 1.0)^2)

Given: additive density <= 1.0 everywhere.
When: compute_l_overlap is called.
Then: loss = 0.0 (no overlap penalty).

Given: additive density = 2.0 at some pixels (overlap).
When: compute_l_overlap is called.
Then: loss > 0 (overlap detected and penalized).

Given: additive density from 2 overlapping sprites.
When: compute_additive_density is called on tiny_renderer.
Then: max(additive_density) > 1.0.
"""

from __future__ import annotations

import torch
import pytest

from aerocloud.optimizer.loss import compute_l_overlap, compute_additive_density


class TestLOverlapNoOverlap:
    """L_overlap should be zero when density <= 1.0."""

    def test_no_overlap_zero_loss(self) -> None:
        """density=0.5 everywhere => zero overlap loss."""
        density = torch.full((1, 1, 4, 4), 0.5)
        loss = compute_l_overlap(density)
        assert abs(loss.item()) < 1e-6, f"Expected ~0 with no overlap, got {loss.item()}"

    def test_exactly_one_zero_loss(self) -> None:
        """density=1.0 everywhere (boundary) => still zero loss."""
        density = torch.ones(1, 1, 4, 4)
        loss = compute_l_overlap(density)
        assert abs(loss.item()) < 1e-6, f"Expected ~0 at density=1.0, got {loss.item()}"


class TestLOverlapWithOverlap:
    """L_overlap should be positive when density > 1.0."""

    def test_overlap_positive_loss(self) -> None:
        """density=2.0 at all pixels => positive loss = mean((2-1)^2) = 1.0."""
        density = torch.full((1, 1, 4, 4), 2.0)
        loss = compute_l_overlap(density)
        # ReLU(2 - 1)^2 = 1.0 at all pixels, mean = 1.0
        assert abs(loss.item() - 1.0) < 1e-5, f"Expected ~1.0 loss, got {loss.item()}"

    def test_single_overlap_pixel(self) -> None:
        """Single pixel with density=2.0, rest=0.5 => small positive loss."""
        density = torch.full((1, 1, 4, 4), 0.5)
        density[0, 0, 2, 2] = 2.0
        loss = compute_l_overlap(density)
        assert loss.item() > 0.0, "Expected positive loss with one overlapping pixel"


class TestLOverlapAdditiveHelper:
    """compute_additive_density should produce values > 1.0 for overlapping sprites."""

    def test_overlapping_sprites_exceed_one(self, tiny_renderer: object) -> None:
        """Two overlapping sprites => max(additive_density) > 1.0."""
        additive = compute_additive_density(tiny_renderer, canvas_h=8, canvas_w=8)
        assert additive.shape == (1, 1, 8, 8), f"Expected (1,1,8,8), got {additive.shape}"
        assert additive.max().item() > 1.0, (
            f"Expected additive density > 1.0 for overlapping sprites, "
            f"got max={additive.max().item()}"
        )


class TestLOverlapGradientFlows:
    """Gradient must flow through L_overlap."""

    def test_gradient_flows(self) -> None:
        """backward() does not raise and grad is not None."""
        density = torch.rand(1, 1, 4, 4) + 0.5  # ensure some > 1.0
        density.requires_grad_(True)
        loss = compute_l_overlap(density)
        loss.backward()
        assert density.grad is not None, "Expected gradient on density tensor"
        assert not torch.isnan(density.grad).any(), "Gradient contains NaN"

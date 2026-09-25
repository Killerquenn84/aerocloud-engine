"""Unit tests for compute_total_loss.

L_total = alpha * L_wmse + beta * L_overlap + gamma * L_fidelity + lambda_ * L_temporal

Given: default LossWeights (alpha=1.0, beta=10.0, gamma=0.1, lambda_=0.0).
When: individual losses are known scalars.
Then: total = alpha * l_wmse + beta * l_overlap + gamma * l_fidelity + lambda_ * l_temporal.

Given: custom weights.
When: individual losses are 1.0 each.
Then: total = sum of weights * 1.0.
"""

from __future__ import annotations

import torch

from aerocloud.models.optimizer import LossWeights
from aerocloud.optimizer.loss import compute_total_loss


class TestComputeTotalLoss:
    """compute_total_loss combines losses with configurable weights."""

    def test_default_weights_combination(self) -> None:
        """With default weights, total = 1*l_wmse + 10*l_overlap + 0.1*l_fid + 0*l_temp."""
        weights = LossWeights()
        l_wmse = torch.tensor(1.0)
        l_overlap = torch.tensor(1.0)
        l_fidelity = torch.tensor(1.0)
        l_temporal = torch.tensor(1.0)
        total = compute_total_loss(weights, l_wmse, l_overlap, l_fidelity, l_temporal)
        expected = 1.0 * 1.0 + 10.0 * 1.0 + 0.1 * 1.0 + 0.0 * 1.0  # = 11.1
        assert abs(total.item() - expected) < 1e-4, f"Expected {expected}, got {total.item()}"

    def test_lambda_zero_suppresses_temporal(self) -> None:
        """Default lambda_=0.0 means temporal loss has no effect."""
        weights = LossWeights()
        l_wmse = torch.tensor(0.0)
        l_overlap = torch.tensor(0.0)
        l_fidelity = torch.tensor(0.0)
        l_temporal = torch.tensor(999.0)  # large value, should be suppressed
        total = compute_total_loss(weights, l_wmse, l_overlap, l_fidelity, l_temporal)
        assert abs(total.item()) < 1e-5, f"Expected ~0 with lambda=0, got {total.item()}"

    def test_custom_weights(self) -> None:
        """Custom weights are applied correctly."""
        weights = LossWeights(alpha=2.0, beta=3.0, gamma=4.0, lambda_=5.0)
        l_wmse = torch.tensor(1.0)
        l_overlap = torch.tensor(1.0)
        l_fidelity = torch.tensor(1.0)
        l_temporal = torch.tensor(1.0)
        total = compute_total_loss(weights, l_wmse, l_overlap, l_fidelity, l_temporal)
        expected = 2.0 + 3.0 + 4.0 + 5.0  # = 14.0
        assert abs(total.item() - expected) < 1e-4, f"Expected {expected}, got {total.item()}"

    def test_returns_scalar_tensor(self) -> None:
        """compute_total_loss returns a scalar tensor."""
        weights = LossWeights()
        total = compute_total_loss(
            weights,
            torch.tensor(1.0),
            torch.tensor(1.0),
            torch.tensor(1.0),
            torch.tensor(1.0),
        )
        assert total.ndim == 0, f"Expected scalar, got shape {total.shape}"

    def test_gradient_flows_through_total(self) -> None:
        """Gradient flows through compute_total_loss to each component."""
        weights = LossWeights()
        base = torch.tensor(1.0, requires_grad=True)
        l_wmse = base * 1.0
        l_overlap = base * 2.0
        l_fidelity = base * 3.0
        l_temporal = base * 4.0
        total = compute_total_loss(weights, l_wmse, l_overlap, l_fidelity, l_temporal)
        total.backward()
        assert base.grad is not None, "Expected gradient to flow through total loss"
        assert not torch.isnan(base.grad), "Gradient contains NaN"

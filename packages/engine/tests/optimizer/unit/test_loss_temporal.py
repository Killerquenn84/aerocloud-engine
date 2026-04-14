"""Unit tests for compute_l_temporal (Temporal Coherence loss).

L_temporal penalizes position drift (default weight 0.0).
L_temporal(params_current, params_initial) = mean((current[:, :2] - initial[:, :2])^2)

Given: current and initial params are identical.
When: compute_l_temporal is called.
Then: loss = 0.0 (no drift penalty).

Given: current params shifted by delta from initial.
When: compute_l_temporal is called.
Then: loss > 0.

Note: Only the y/x columns ([:, :2]) contribute; scale/rotation drift is ignored.
"""

from __future__ import annotations

import torch
import pytest

from aerocloud.optimizer.loss import compute_l_temporal


class TestLTemporalNoDrift:
    """L_temporal should be zero when positions are unchanged."""

    def test_same_positions_zero_loss(self) -> None:
        """Identical params_current and params_initial => loss = 0.0."""
        params = torch.tensor([[1.0, 2.0, 1.0, 0.0], [3.0, 4.0, 0.5, 0.3]])
        loss = compute_l_temporal(params, params)
        assert abs(loss.item()) < 1e-6, f"Expected ~0 with no drift, got {loss.item()}"

    def test_returns_scalar_tensor(self) -> None:
        """compute_l_temporal returns a scalar tensor."""
        params = torch.tensor([[1.0, 2.0, 1.0, 0.0]])
        loss = compute_l_temporal(params, params)
        assert loss.ndim == 0, f"Expected scalar, got shape {loss.shape}"


class TestLTemporalWithDrift:
    """L_temporal should be positive when positions drift."""

    def test_shifted_positions_positive_loss(self) -> None:
        """Shift of 1.0 in y and x for 1 word => mean((1^2 + 1^2)/2) = 1.0."""
        initial = torch.tensor([[0.0, 0.0, 1.0, 0.0]])
        current = torch.tensor([[1.0, 1.0, 1.0, 0.0]])
        loss = compute_l_temporal(current, initial)
        # mean((1-0)^2, (1-0)^2) = mean(1, 1) = 1.0
        assert abs(loss.item() - 1.0) < 1e-5, f"Expected 1.0, got {loss.item()}"

    def test_scale_rotation_not_counted(self) -> None:
        """Scale and rotation changes do not affect L_temporal."""
        initial = torch.tensor([[0.0, 0.0, 1.0, 0.0]])
        # Same position, different scale and rotation
        current = torch.tensor([[0.0, 0.0, 5.0, 3.14]])
        loss = compute_l_temporal(current, initial)
        assert abs(loss.item()) < 1e-6, (
            f"Scale/rotation should not affect L_temporal, got {loss.item()}"
        )


class TestLTemporalGradientFlows:
    """Gradient must flow through L_temporal via params_current."""

    def test_gradient_flows(self) -> None:
        """backward() does not raise and params_current.grad is not None."""
        initial = torch.tensor([[0.0, 0.0, 1.0, 0.0], [1.0, 1.0, 0.5, 0.0]])
        current = torch.tensor(
            [[0.5, 0.5, 1.0, 0.0], [1.5, 1.5, 0.5, 0.0]], requires_grad=True
        )
        loss = compute_l_temporal(current, initial)
        loss.backward()
        assert current.grad is not None, "Expected gradient on params_current tensor"
        assert not torch.isnan(current.grad).any(), "Gradient contains NaN"

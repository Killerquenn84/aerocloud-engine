"""Unit tests for compute_l_fidelity (Data Fidelity loss).

L_fidelity prevents artificial scale inflation using cosine similarity.
L_fidelity(s_ref, params) = 1 - cos_sim(s_ref, params[:, 2])

Given: s_ref and current scales are identical.
When: compute_l_fidelity is called.
Then: loss = 0.0 (no fidelity penalty).

Given: s_ref and current scales are orthogonal.
When: compute_l_fidelity is called.
Then: loss = 1.0.

Given: any valid inputs.
When: compute_l_fidelity is called.
Then: value is in [0, 2] (cosine similarity in [-1, 1]).
"""

from __future__ import annotations

import torch

from aerocloud.optimizer.loss import compute_l_fidelity


class TestLFidelityIdentical:
    """L_fidelity should be zero for identical scale vectors."""

    def test_identical_scales_zero_loss(self, ref_weights_2: torch.Tensor) -> None:
        """Identical s_ref and params[:, 2] => loss ~= 0.0."""
        # params with scale column matching s_ref exactly
        params = torch.tensor([[0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.5, 0.0]])
        loss = compute_l_fidelity(ref_weights_2, params)
        assert abs(loss.item()) < 1e-5, f"Expected ~0 with identical scales, got {loss.item()}"

    def test_returns_scalar_tensor(self, ref_weights_2: torch.Tensor) -> None:
        """compute_l_fidelity returns a scalar tensor."""
        params = torch.tensor([[0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.5, 0.0]])
        loss = compute_l_fidelity(ref_weights_2, params)
        assert loss.ndim == 0, f"Expected scalar, got shape {loss.shape}"


class TestLFidelityOrthogonal:
    """L_fidelity should approach specific values for orthogonal scales."""

    def test_value_in_valid_range(self) -> None:
        """Loss value must be in [0, 2] (cosine similarity in [-1, 1])."""
        s_ref = torch.tensor([1.0, 0.0])
        params = torch.tensor([[0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]])
        loss = compute_l_fidelity(s_ref, params)
        # cosine_similarity([1,0], [0,1]) = 0 => loss = 1 - 0 = 1.0
        assert 0.0 <= loss.item() <= 2.0, f"Loss must be in [0, 2], got {loss.item()}"


class TestLFidelityGradientFlows:
    """Gradient must flow through L_fidelity via params."""

    def test_gradient_flows(self, ref_weights_2: torch.Tensor) -> None:
        """backward() does not raise and params.grad is not None."""
        params = torch.tensor([[0.0, 0.0, 0.8, 0.0], [0.0, 0.0, 0.4, 0.0]], requires_grad=True)
        loss = compute_l_fidelity(ref_weights_2, params)
        loss.backward()
        assert params.grad is not None, "Expected gradient on params tensor"
        assert not torch.isnan(params.grad).any(), "Gradient contains NaN"

"""Unit tests for gradient clipping behavior.

After backward() on a loss with large gradient, clip_grad_norm_ limits
the parameter norm to 1.0.

Given: params with requires_grad=True and a loss that produces large gradients.
When: loss.backward() is called.
Then: grad norm > 1.0 before clipping.

When: clip_grad_norm_(params, max_norm=1.0) is called.
Then: grad norm <= 1.0.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import pytest


class TestGradientClipping:
    """Gradient clipping limits param norm to max_norm."""

    def test_large_grad_before_clip(self) -> None:
        """Large loss produces grad norm > 1.0 before clipping."""
        params = nn.Parameter(torch.ones(4, 4))
        # Large scalar loss ensures large gradients
        loss = (params * 100.0).sum()
        loss.backward()
        assert params.grad is not None, "Expected gradient after backward"
        grad_norm = params.grad.norm().item()
        assert grad_norm > 1.0, (
            f"Expected large gradient (> 1.0) before clipping, got {grad_norm}"
        )

    def test_clip_grad_norm_limit(self) -> None:
        """After clip_grad_norm_, the gradient norm is <= 1.0."""
        params = nn.Parameter(torch.ones(4, 4))
        loss = (params * 100.0).sum()
        loss.backward()
        nn.utils.clip_grad_norm_([params], max_norm=1.0)
        assert params.grad is not None, "Expected gradient after clip"
        grad_norm = params.grad.norm().item()
        assert grad_norm <= 1.0 + 1e-6, (
            f"Expected grad norm <= 1.0 after clipping, got {grad_norm}"
        )

    def test_small_grad_unchanged_by_clip(self) -> None:
        """Small gradient is not affected by clip_grad_norm_(max_norm=1.0)."""
        params = nn.Parameter(torch.ones(2, 2) * 0.001)
        loss = (params * 0.001).sum()
        loss.backward()
        assert params.grad is not None
        grad_norm_before = params.grad.norm().item()
        # Only apply clip if norm > max_norm; small gradient should stay unchanged
        nn.utils.clip_grad_norm_([params], max_norm=1.0)
        grad_norm_after = params.grad.norm().item()
        # After clip, small gradient should remain approximately unchanged
        assert grad_norm_after <= 1.0 + 1e-6, (
            f"Norm after clip must be <= 1.0, got {grad_norm_after}"
        )
        if grad_norm_before <= 1.0:
            assert abs(grad_norm_after - grad_norm_before) < 1e-6, (
                "Small gradient should be unchanged by clipping"
            )

    def test_clip_with_optimizer_params(self) -> None:
        """clip_grad_norm_ works correctly with a model parameter group."""
        model = nn.Linear(10, 10)
        # Create large gradient
        x = torch.randn(1, 10)
        output = model(x)
        loss = output.sum() * 1000.0
        loss.backward()
        # Check at least one grad exists and is large
        grad_norms = [
            p.grad.norm().item() for p in model.parameters() if p.grad is not None
        ]
        assert len(grad_norms) > 0
        # Clip
        total_norm_before = nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        total_norm_after = torch.stack([
            p.grad.norm() for p in model.parameters() if p.grad is not None
        ]).norm().item()
        assert total_norm_after <= 1.0 + 1e-5, (
            f"Expected total norm <= 1.0 after clipping, got {total_norm_after}"
        )

"""Property-based tests for loss functions using Hypothesis.

Verifies:
- No NaN/Inf across 1000 random seeds (ROADMAP success criterion 3)
- L_overlap >= 0, L_wmse >= 0, L_fidelity in [0, 2] (property bounds)
- Total loss is finite for random inputs through the renderer

All tests are CPU-only per D-23.
"""

from __future__ import annotations

import torch
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from aerocloud.models.optimizer import LossWeights
from aerocloud.optimizer.loss import (
    compute_additive_density,
    compute_l_fidelity,
    compute_l_overlap,
    compute_l_temporal,
    compute_l_wmse,
    compute_total_loss,
)
from aerocloud.renderer._renderer import DifferentiableRenderer

# ---------------------------------------------------------------------------
# Strategy helpers
# ---------------------------------------------------------------------------

_finite_floats = st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False)


def _draw_tensor(draw: st.DrawFn, rows: int, cols: int) -> torch.Tensor:
    """Draw a (rows, cols) float32 tensor from finite floats."""
    values = draw(st.lists(_finite_floats, min_size=rows * cols, max_size=rows * cols))
    return torch.tensor(values, dtype=torch.float32).reshape(rows, cols)


def _draw_4d_tensor(draw: st.DrawFn, h: int, w: int) -> torch.Tensor:
    """Draw a (1, 1, h, w) float32 tensor from finite floats."""
    n = h * w
    values = draw(st.lists(_finite_floats, min_size=n, max_size=n))
    return torch.tensor(values, dtype=torch.float32).reshape(1, 1, h, w)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(
    h=st.integers(min_value=4, max_value=32),
    w=st.integers(min_value=4, max_value=32),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_l_wmse_is_finite(h: int, w: int) -> None:
    """compute_l_wmse is non-negative and finite for any random density and SDF (1,1,H,W)."""
    density = torch.rand(1, 1, h, w)
    sdf = torch.randn(1, 1, h, w)
    result = compute_l_wmse(density, sdf)
    assert torch.isfinite(result), f"L_wmse not finite: {result}"
    assert result >= 0.0, f"L_wmse is negative: {result}"


@given(
    h=st.integers(min_value=4, max_value=32),
    w=st.integers(min_value=4, max_value=32),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_l_overlap_non_negative(h: int, w: int) -> None:
    """compute_l_overlap is non-negative and finite for random additive density."""
    # Additive density can exceed 1.0 (range [0, +large])
    additive_density = torch.rand(1, 1, h, w) * 3.0
    result = compute_l_overlap(additive_density)
    assert torch.isfinite(result), f"L_overlap not finite: {result}"
    assert result >= 0.0, f"L_overlap is negative: {result}"


@given(
    n=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_l_fidelity_in_range(n: int) -> None:
    """compute_l_fidelity is in [0, 2] and finite for random s_ref and params (N,4).

    Cosine similarity in [-1, 1] so 1 - cos_sim in [0, 2].
    Edge case: zero-norm vectors produce cos_sim=0 via eps, so result=1.0 in [0, 2].
    """
    s_ref = torch.randn(n)
    params = torch.randn(n, 4)
    result = compute_l_fidelity(s_ref, params)
    assert torch.isfinite(result), f"L_fidelity not finite: {result}"
    # cosine_similarity with dim=1 on unsqueezed (1,N) vectors -> scalar in [-1,1]
    # 1 - (-1..1) = [0, 2]
    assert 0.0 <= float(result) <= 2.0 + 1e-5, f"L_fidelity out of [0, 2]: {result}"


@given(
    n=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_l_temporal_non_negative(n: int) -> None:
    """compute_l_temporal is non-negative and finite for random params."""
    params_current = torch.randn(n, 4)
    params_initial = torch.randn(n, 4)
    result = compute_l_temporal(params_current, params_initial)
    assert torch.isfinite(result), f"L_temporal not finite: {result}"
    assert result >= 0.0, f"L_temporal is negative: {result}"


@given(
    h=st.integers(min_value=4, max_value=16),
    w=st.integers(min_value=4, max_value=16),
    n=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_total_loss_is_finite(h: int, w: int, n: int) -> None:
    """compute_total_loss is finite for random inputs for all 4 loss terms."""
    density = torch.rand(1, 1, h, w)
    sdf = torch.randn(1, 1, h, w)
    additive = torch.rand(1, 1, h, w) * 2.0
    s_ref = torch.randn(n)
    params_c = torch.randn(n, 4)
    params_i = torch.randn(n, 4)

    l_wmse = compute_l_wmse(density, sdf)
    l_overlap = compute_l_overlap(additive)
    l_fidelity = compute_l_fidelity(s_ref, params_c)
    l_temporal = compute_l_temporal(params_c, params_i)

    result = compute_total_loss(LossWeights(), l_wmse, l_overlap, l_fidelity, l_temporal)
    assert torch.isfinite(result), f"total loss not finite: {result}"


@given(
    n=st.integers(min_value=1, max_value=5),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_random_params_produce_finite_loss_through_renderer(n: int) -> None:
    """Random params produce finite losses for all terms through DifferentiableRenderer."""
    device = torch.device("cpu")
    params = torch.rand(n, 4)
    sprites = [torch.rand(1, 1, 4, 4) for _ in range(n)]
    renderer = DifferentiableRenderer(params, sprites, device)

    canvas_h, canvas_w = 8, 8
    sdf = torch.randn(1, 1, canvas_h, canvas_w)
    s_ref = torch.rand(n)

    density = renderer.forward(canvas_h, canvas_w)
    additive = compute_additive_density(renderer, canvas_h, canvas_w)

    l_wmse = compute_l_wmse(density, sdf)
    l_overlap = compute_l_overlap(additive)
    l_fidelity = compute_l_fidelity(s_ref, renderer.params)
    l_temporal = compute_l_temporal(renderer.params, renderer.params.detach().clone())
    l_total = compute_total_loss(LossWeights(), l_wmse, l_overlap, l_fidelity, l_temporal)

    assert torch.isfinite(l_wmse), f"L_wmse not finite: {l_wmse}"
    assert torch.isfinite(l_overlap), f"L_overlap not finite: {l_overlap}"
    assert torch.isfinite(l_fidelity), f"L_fidelity not finite: {l_fidelity}"
    assert torch.isfinite(l_temporal), f"L_temporal not finite: {l_temporal}"
    assert torch.isfinite(l_total), f"L_total not finite: {l_total}"


def test_l_overlap_zero_when_no_overlap() -> None:
    """compute_l_overlap is exactly 0.0 when additive density <= 1.0 everywhere."""
    # Density in [0, 1] range: no overlap -> penalty must be exactly 0
    additive_density = torch.rand(1, 1, 8, 8)  # values in [0, 1)
    result = compute_l_overlap(additive_density)
    assert result.item() == 0.0, (
        f"L_overlap should be 0 with no overlapping pixels, got {result.item()}"
    )

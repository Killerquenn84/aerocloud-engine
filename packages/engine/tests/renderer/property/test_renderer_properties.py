"""Property-based tests for DifferentiableRenderer using Hypothesis.

Tests verify:
- Random (N, 4) params always produce non-NaN output in [0, 1]
- backward() does not raise for any valid params (REND-06)
- Gradient is non-None and non-zero after backward()
- Output shape matches requested canvas dimensions
- Extreme rotation (D-09 clamping) does not produce NaN
- Zero scale does not crash
"""

from __future__ import annotations

import torch
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from aerocloud.renderer import DifferentiableRenderer

# ---------------------------------------------------------------------------
# Strategy helpers
# ---------------------------------------------------------------------------

def _make_renderer(n: int, sprite_h: int = 4, sprite_w: int = 4) -> DifferentiableRenderer:
    """Create a DifferentiableRenderer with random params and fixed sprites."""
    params = torch.rand(n, 4)
    sprites = [torch.rand(1, 1, sprite_h, sprite_w) for _ in range(n)]
    return DifferentiableRenderer(params, sprites, torch.device("cpu"))


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

@given(
    n=st.integers(min_value=1, max_value=10),
    canvas_h=st.integers(min_value=4, max_value=32),
    canvas_w=st.integers(min_value=4, max_value=32),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_random_params_produce_valid_output(n: int, canvas_h: int, canvas_w: int) -> None:
    """Random (N, 4) params always produce non-NaN output in [0, 1]."""
    renderer = _make_renderer(n)
    out = renderer(canvas_h, canvas_w)
    assert not torch.isnan(out).any(), "Output contains NaN"
    assert (out >= 0.0).all(), "Output has negative values"
    assert (out <= 1.0).all(), "Output exceeds 1.0"


@given(
    n=st.integers(min_value=1, max_value=10),
    canvas_h=st.integers(min_value=4, max_value=16),
    canvas_w=st.integers(min_value=4, max_value=16),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_backward_does_not_raise(n: int, canvas_h: int, canvas_w: int) -> None:
    """forward().sum().backward() must not raise for any random params (REND-06)."""
    renderer = _make_renderer(n)
    out = renderer(canvas_h, canvas_w)
    # Should not raise
    out.sum().backward()


@given(
    n=st.integers(min_value=1, max_value=10),
    canvas_h=st.integers(min_value=4, max_value=16),
    canvas_w=st.integers(min_value=4, max_value=16),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_gradient_is_non_none(n: int, canvas_h: int, canvas_w: int) -> None:
    """After backward(), renderer.params.grad must not be None."""
    renderer = _make_renderer(n)
    out = renderer(canvas_h, canvas_w)
    out.sum().backward()
    assert renderer.params.grad is not None, "params.grad is None after backward()"


def test_gradient_is_non_zero() -> None:
    """Single word at canvas center with a non-trivial sprite: grad must be non-zero."""
    # Use canvas 16x16, place word at center (8, 8)
    params = torch.tensor([[8.0, 8.0, 1.0, 0.0]])
    # Non-trivial sprite: uniform non-zero pattern
    sprite = torch.ones(1, 1, 4, 4) * 0.5
    renderer = DifferentiableRenderer(params, [sprite], torch.device("cpu"))
    out = renderer(16, 16)
    out.sum().backward()
    assert renderer.params.grad is not None
    assert renderer.params.grad.abs().sum() > 0, "All gradient elements are zero"


@given(
    n=st.integers(min_value=1, max_value=10),
    canvas_h=st.integers(min_value=4, max_value=32),
    canvas_w=st.integers(min_value=4, max_value=32),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_output_shape_matches_canvas(n: int, canvas_h: int, canvas_w: int) -> None:
    """Output shape must be (1, 1, canvas_h, canvas_w) for any canvas size."""
    renderer = _make_renderer(n)
    out = renderer(canvas_h, canvas_w)
    assert out.shape == (1, 1, canvas_h, canvas_w), (
        f"Expected shape (1, 1, {canvas_h}, {canvas_w}), got {out.shape}"
    )


@given(n=st.integers(min_value=1, max_value=5))
@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
def test_extreme_rotation_no_nan(n: int) -> None:
    """theta values near +/- 1e4 must not produce NaN (D-09 clamping)."""
    params = torch.rand(n, 4)
    params[:, 3] = 1e4  # Extreme rotation
    sprites = [torch.rand(1, 1, 4, 4) for _ in range(n)]
    renderer = DifferentiableRenderer(params, sprites, torch.device("cpu"))
    out = renderer(8, 8)
    assert not torch.isnan(out).any(), "NaN output with extreme rotation values"


@given(n=st.integers(min_value=1, max_value=5))
@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
def test_zero_scale_no_nan(n: int) -> None:
    """scale=0.0 must not produce NaN (degenerate but must not crash)."""
    params = torch.rand(n, 4)
    params[:, 2] = 0.0  # Zero scale
    sprites = [torch.rand(1, 1, 4, 4) for _ in range(n)]
    renderer = DifferentiableRenderer(params, sprites, torch.device("cpu"))
    out = renderer(8, 8)
    assert not torch.isnan(out).any(), "NaN output with zero scale"

"""Determinism tests for DifferentiableRenderer.

Verifies that:
- Same seed + same input produces byte-identical output over 10 runs (D-18)
- Same seed + backward produces byte-identical gradients over 10 runs
- Different seeds produce different outputs
"""

from __future__ import annotations

import torch

from aerocloud.renderer import DifferentiableRenderer
from aerocloud.utils.determinism import set_seed

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_renderer_fixed(device: torch.device) -> DifferentiableRenderer:
    """Create a renderer with fixed (non-random) params and sprites for determinism testing."""
    params = torch.tensor([
        [8.0, 8.0, 1.0, 0.0],
        [4.0, 4.0, 0.5, 0.785],  # pi/4
    ], dtype=torch.float32)
    # Fixed deterministic sprites (no randomness)
    sprite_a = torch.linspace(0.0, 1.0, 16).reshape(1, 1, 4, 4)
    sprite_b = torch.linspace(1.0, 0.0, 16).reshape(1, 1, 4, 4)
    return DifferentiableRenderer(params, [sprite_a, sprite_b], device)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_determinism_10_runs() -> None:
    """Same seed + same input produces byte-identical output tensor over 10 runs (D-18)."""
    device = torch.device("cpu")
    outputs = []

    for _ in range(10):
        set_seed(42)
        renderer = _make_renderer_fixed(device)
        out = renderer(16, 16)
        outputs.append(out.detach().clone())

    for i in range(1, 10):
        assert torch.equal(outputs[i], outputs[0]), (
            f"Run {i} output differs from run 0 — not deterministic"
        )


def test_determinism_backward_10_runs() -> None:
    """Same seed + forward+backward over 10 runs produces byte-identical gradients."""
    device = torch.device("cpu")
    grads = []

    for _ in range(10):
        set_seed(42)
        renderer = _make_renderer_fixed(device)
        out = renderer(16, 16)
        out.sum().backward()
        assert renderer.params.grad is not None
        grads.append(renderer.params.grad.detach().clone())

    for i in range(1, 10):
        assert torch.equal(grads[i], grads[0]), (
            f"Run {i} gradient differs from run 0 — backward not deterministic"
        )


def test_different_seeds_different_output() -> None:
    """Different seeds with random init must produce different outputs."""
    device = torch.device("cpu")

    # Seed 42 — random params
    set_seed(42)
    params_42 = torch.randn(3, 4)
    sprites_42 = [torch.rand(1, 1, 4, 4) for _ in range(3)]
    renderer_42 = DifferentiableRenderer(params_42, sprites_42, device)
    out_42 = renderer_42(16, 16).detach().clone()

    # Seed 99 — different random params
    set_seed(99)
    params_99 = torch.randn(3, 4)
    sprites_99 = [torch.rand(1, 1, 4, 4) for _ in range(3)]
    renderer_99 = DifferentiableRenderer(params_99, sprites_99, device)
    out_99 = renderer_99(16, 16).detach().clone()

    assert not torch.equal(out_42, out_99), (
        "Outputs with different seeds are identical — seed has no effect"
    )

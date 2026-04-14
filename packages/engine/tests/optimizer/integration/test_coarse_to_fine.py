"""Integration tests for the Coarse-to-Fine InnerLoop pipeline (Plan 02).

Tests verify the full optimize() pipeline per D-07..D-19:
- Convergence from random init within 100 epochs at 8px (ROADMAP SC 1)
- Stage schedule filters resolutions >= target
- Warm-start carries params between stages
- Determinism: identical seeds produce identical loss curves
- OptimizationResult structure is valid
"""

from __future__ import annotations

import math

import numpy as np
import pytest
import torch

from aerocloud.optimizer.inner_loop import InnerLoop
from aerocloud.models.optimizer import InnerLoopConfig, OptimizationResult
from aerocloud.renderer._renderer import DifferentiableRenderer
from aerocloud.utils.determinism import set_seed


# ---------------------------------------------------------------------------
# Helpers / inline fixtures
# ---------------------------------------------------------------------------


def _make_tiny_renderer(
    n_sprites: int = 2,
    device: torch.device | None = None,
) -> DifferentiableRenderer:
    """2-sprite renderer for integration tests."""
    if device is None:
        device = torch.device("cpu")
    sprite = torch.eye(4, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
    sprites = [sprite.clone() for _ in range(n_sprites)]
    params_n4 = torch.tensor(
        [[2.0, 2.0, 1.0, 0.0], [3.0, 3.0, 1.0, 0.0]][:n_sprites],
        dtype=torch.float32,
    )
    return DifferentiableRenderer(params_n4=params_n4, sprites=sprites, device=device)


def _make_circle_sdf(size: int, device: torch.device | None = None) -> torch.Tensor:
    """Circle SDF of given size for integration tests."""
    if device is None:
        device = torch.device("cpu")
    cy, cx = size / 2.0, size / 2.0
    radius = size * 0.35
    coords = np.zeros((size, size), dtype=np.float32)
    for row in range(size):
        for col in range(size):
            dist = math.sqrt((row - cy) ** 2 + (col - cx) ** 2)
            coords[row, col] = radius - dist
    sdf = torch.from_numpy(coords).unsqueeze(0).unsqueeze(0)
    return sdf.to(device)


def _make_ref_weights(n: int = 2) -> torch.Tensor:
    """Reference scale weights."""
    return torch.tensor([1.0, 0.5][:n])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_coarse_to_fine_converges_8px() -> None:
    """Full pipeline on 8px canvas should converge and return valid result.

    Given: a tiny renderer with 2 sprites, an 8px circle SDF, ref weights
    When: InnerLoop.optimize() is called with default config
    Then: Loss should decrease (first loss > last loss in stage 0)
          and OptimizationResult should have correct structure.
    """
    set_seed(42)
    renderer = _make_tiny_renderer()
    sdf = _make_circle_sdf(8)
    ref_weights = _make_ref_weights()

    # Use minimal config for speed: small max_epochs, only 8px stage
    config = InnerLoopConfig(
        max_epochs=50,
        min_epochs_before_convergence=5,
        stage_resolutions=[8],
    )
    loop = InnerLoop(renderer=renderer, sdf=sdf, ref_weights=ref_weights, config=config)
    result = loop.optimize()

    assert isinstance(result, OptimizationResult)
    # Loss should decrease during optimization
    hist = result.stage_loss_histories[0]
    assert len(hist) > 1, "Should have at least 2 epoch losses recorded"
    assert hist[0] > hist[-1], (
        f"Loss should decrease: first={hist[0]:.4f}, last={hist[-1]:.4f}"
    )


def test_stage_schedule_filters_large_resolutions() -> None:
    """Stage schedule filters resolutions >= target, leaving [8, target].

    Given: InnerLoop with 16px target SDF and stage_resolutions=[8, 32, 128]
    When: optimize() is called
    Then: Only 2 stages run (8 and 16), because 32 and 128 >= 16 are filtered.
    """
    set_seed(42)
    renderer = _make_tiny_renderer()
    sdf = _make_circle_sdf(16)
    ref_weights = _make_ref_weights()

    config = InnerLoopConfig(
        max_epochs=5,
        min_epochs_before_convergence=100,  # disable early convergence
        stage_resolutions=[8, 32, 128],
    )
    loop = InnerLoop(renderer=renderer, sdf=sdf, ref_weights=ref_weights, config=config)
    result = loop.optimize()

    assert len(result.stage_loss_histories) == 2, (
        f"Expected 2 stages (8 and 16), got {len(result.stage_loss_histories)}"
    )


def test_warm_start_carries_params() -> None:
    """After stage 1, params should have changed from their initial values.

    Given: InnerLoop with 2 resolution stages (8px then 16px)
    When: optimize() runs through both stages
    Then: final params differ from the initial params (optimizer moved them).
    """
    set_seed(42)
    renderer = _make_tiny_renderer()
    initial_params = renderer.params.detach().clone()
    sdf = _make_circle_sdf(16)
    ref_weights = _make_ref_weights()

    config = InnerLoopConfig(
        max_epochs=30,
        min_epochs_before_convergence=100,  # force full epochs
        stage_resolutions=[8, 16],
    )
    loop = InnerLoop(renderer=renderer, sdf=sdf, ref_weights=ref_weights, config=config)
    result = loop.optimize()

    final_params = result.params
    assert not torch.allclose(initial_params, final_params, atol=1e-6), (
        "Params should have changed after optimization (warm-start + gradient steps)"
    )


def test_determinism_two_runs() -> None:
    """Same seed + same renderer should produce identical loss histories.

    Given: Two InnerLoop instances with same seed and same config
    When: Both run optimize()
    Then: Their stage loss histories are identical (element-wise).
    """
    config = InnerLoopConfig(
        max_epochs=10,
        min_epochs_before_convergence=100,
        stage_resolutions=[8],
    )

    # Run 1
    set_seed(42)
    renderer1 = _make_tiny_renderer()
    sdf = _make_circle_sdf(8)
    ref_weights = _make_ref_weights()
    loop1 = InnerLoop(renderer=renderer1, sdf=sdf, ref_weights=ref_weights, config=config)
    result1 = loop1.optimize()

    # Run 2 — identical setup
    set_seed(42)
    renderer2 = _make_tiny_renderer()
    sdf2 = _make_circle_sdf(8)
    ref_weights2 = _make_ref_weights()
    loop2 = InnerLoop(renderer=renderer2, sdf=sdf2, ref_weights=ref_weights2, config=config)
    result2 = loop2.optimize()

    assert len(result1.stage_loss_histories) == len(result2.stage_loss_histories)
    for hist1, hist2 in zip(result1.stage_loss_histories, result2.stage_loss_histories):
        assert hist1 == hist2, (
            f"Loss histories differ between identical runs:\n{hist1}\nvs\n{hist2}"
        )


def test_optimize_returns_valid_result() -> None:
    """OptimizationResult must have correct structure and valid values.

    Given: A small 8px InnerLoop
    When: optimize() completes
    Then:
    - params.shape == (N, 4)
    - stage_loss_histories is list of lists of floats
    - convergence_flags is list of bools
    - wall_clock_s > 0
    - total_epochs > 0
    """
    set_seed(42)
    n_sprites = 2
    renderer = _make_tiny_renderer(n_sprites=n_sprites)
    sdf = _make_circle_sdf(8)
    ref_weights = _make_ref_weights(n=n_sprites)

    config = InnerLoopConfig(
        max_epochs=5,
        min_epochs_before_convergence=100,
        stage_resolutions=[8],
    )
    loop = InnerLoop(renderer=renderer, sdf=sdf, ref_weights=ref_weights, config=config)
    result = loop.optimize()

    # params shape
    assert result.params.shape == (n_sprites, 4), (
        f"Expected params shape ({n_sprites}, 4), got {result.params.shape}"
    )

    # stage_loss_histories: list of lists of floats
    assert isinstance(result.stage_loss_histories, list)
    for stage_hist in result.stage_loss_histories:
        assert isinstance(stage_hist, list)
        for v in stage_hist:
            assert isinstance(v, float)
            assert math.isfinite(v), f"Loss value {v} is not finite"

    # convergence_flags: list of bools
    assert isinstance(result.convergence_flags, list)
    for flag in result.convergence_flags:
        assert isinstance(flag, bool)

    # timing
    assert result.wall_clock_s > 0, "wall_clock_s should be positive"
    assert result.total_epochs > 0, "total_epochs should be positive"

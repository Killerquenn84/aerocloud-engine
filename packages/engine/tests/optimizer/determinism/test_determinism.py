"""Determinism tests for the InnerLoop optimizer.

Verifies:
- Same seed produces byte-identical loss curves over 10 runs (ROADMAP criterion 5)
- Different seeds produce different loss histories
- Determinism holds across multi-stage Coarse-to-Fine runs
"""

from __future__ import annotations

import torch

from aerocloud.models.optimizer import InnerLoopConfig
from aerocloud.optimizer.inner_loop import InnerLoop
from aerocloud.renderer._renderer import DifferentiableRenderer
from aerocloud.utils.determinism import set_seed

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tiny_inner_loop(
    seed: int,
    stage_resolutions: list[int] | None = None,
    sdf_size: int = 8,
    max_epochs: int = 20,
) -> InnerLoop:
    """Create a small InnerLoop with seeded random state.

    Args:
        seed: Random seed to set before creating renderer + params.
        stage_resolutions: Resolution schedule. Defaults to [stage of sdf_size].
        sdf_size: SDF height and width in pixels.
        max_epochs: Maximum epochs per stage.

    Returns:
        Configured InnerLoop instance (renderer params are seeded random).
    """
    set_seed(seed)

    n_sprites = 2
    params = torch.rand(n_sprites, 4) * float(sdf_size)
    params[:, 2] = torch.rand(n_sprites) * 2.0 + 0.5  # scale in [0.5, 2.5]
    params[:, 3] = torch.rand(n_sprites) * 0.5  # rotation in [0, 0.5]

    sprites = [torch.rand(1, 1, 4, 4) for _ in range(n_sprites)]

    device = torch.device("cpu")
    renderer = DifferentiableRenderer(params, sprites, device)

    sdf = torch.zeros(1, 1, sdf_size, sdf_size)
    # Simple circular SDF: positive inside, negative outside
    for row in range(sdf_size):
        for col in range(sdf_size):
            cy, cx = sdf_size / 2.0, sdf_size / 2.0
            radius = sdf_size / 2.5
            dist = ((row - cy) ** 2 + (col - cx) ** 2) ** 0.5
            sdf[0, 0, row, col] = radius - dist

    ref_weights = torch.tensor([1.0, 0.5])

    resolutions = stage_resolutions if stage_resolutions is not None else []
    config = InnerLoopConfig(
        stage_resolutions=resolutions,
        max_epochs=max_epochs,
        min_epochs_before_convergence=5,
    )
    return InnerLoop(renderer, sdf, ref_weights, config)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_same_seed_identical_loss_curves() -> None:
    """Same seed produces byte-identical loss histories over 10 runs.

    ROADMAP success criterion 5: same seed -> identical loss curves.
    """
    histories: list[list[list[float]]] = []

    for _ in range(10):
        loop = _make_tiny_inner_loop(seed=42, sdf_size=8, max_epochs=20)
        result = loop.optimize()
        histories.append(result.stage_loss_histories)

    # All 10 runs must produce identical loss histories
    for i in range(1, 10):
        assert histories[i] == histories[0], (
            f"Run {i} loss history differs from run 0 — InnerLoop not deterministic.\n"
            f"Run 0: {histories[0]}\n"
            f"Run {i}: {histories[i]}"
        )


def test_different_seeds_differ() -> None:
    """Different seeds produce different loss histories (seed has effect)."""
    loop_42 = _make_tiny_inner_loop(seed=42, sdf_size=8, max_epochs=20)
    result_42 = loop_42.optimize()

    loop_99 = _make_tiny_inner_loop(seed=99, sdf_size=8, max_epochs=20)
    result_99 = loop_99.optimize()

    assert result_42.stage_loss_histories != result_99.stage_loss_histories, (
        "Seeds 42 and 99 produced identical loss histories — seed has no effect."
    )


def test_determinism_across_stages() -> None:
    """Same seed with multi-stage schedule produces identical histories over 3 runs.

    Uses stage_resolutions=[8] with sdf_size=16, resulting in schedule [8, 16].
    """
    histories: list[list[list[float]]] = []

    for _ in range(3):
        # 16px SDF with [8] base resolutions -> schedule [8, 16]
        loop = _make_tiny_inner_loop(
            seed=42,
            stage_resolutions=[8],
            sdf_size=16,
            max_epochs=15,
        )
        result = loop.optimize()
        histories.append(result.stage_loss_histories)

    assert len(histories[0]) == 2, (
        f"Expected 2 stages (schedule [8,16]), got {len(histories[0])}"
    )

    for i in range(1, 3):
        assert histories[i] == histories[0], (
            f"Run {i} multi-stage history differs from run 0.\n"
            f"Run 0: {histories[0]}\n"
            f"Run {i}: {histories[i]}"
        )

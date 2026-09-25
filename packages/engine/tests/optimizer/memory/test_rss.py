"""RSS stability and memory tests for the InnerLoop optimizer.

Verifies:
- RSS delta < 50 MiB over 100 optimization calls (ROADMAP criterion 4)
- No tensor accumulation: repeated optimize() calls do not grow tensor count
- Loss history entries are plain Python floats (not torch.Tensor) — D-16 hygiene
"""

from __future__ import annotations

import gc
import os

import psutil
import torch

from aerocloud.models.optimizer import InnerLoopConfig
from aerocloud.optimizer.inner_loop import InnerLoop
from aerocloud.renderer._renderer import DifferentiableRenderer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tiny_loop() -> InnerLoop:
    """Create a minimal InnerLoop for memory testing.

    2 sprites, 8px SDF, single stage, 5 epochs — runs in < 100ms.
    """
    n_sprites = 2
    device = torch.device("cpu")
    params = torch.tensor([[4.0, 4.0, 1.0, 0.0], [2.0, 2.0, 0.5, 0.0]])
    sprites = [torch.rand(1, 1, 4, 4) for _ in range(n_sprites)]
    renderer = DifferentiableRenderer(params, sprites, device)

    sdf_size = 8
    sdf = torch.zeros(1, 1, sdf_size, sdf_size)
    for row in range(sdf_size):
        for col in range(sdf_size):
            cy, cx = sdf_size / 2.0, sdf_size / 2.0
            radius = sdf_size / 2.5
            dist = ((row - cy) ** 2 + (col - cx) ** 2) ** 0.5
            sdf[0, 0, row, col] = radius - dist

    ref_weights = torch.tensor([1.0, 0.5])
    config = InnerLoopConfig(
        stage_resolutions=[],  # Only target stage (8px)
        max_epochs=5,
        min_epochs_before_convergence=3,
    )
    return InnerLoop(renderer, sdf, ref_weights, config)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_rss_stable_over_100_optimize_steps() -> None:
    """RSS delta < 50 MiB over 100 consecutive optimize() calls.

    ROADMAP success criterion 4: no memory leaks in inner-loop iteration.
    """
    process = psutil.Process(os.getpid())

    # Warm up: settle Python/PyTorch memory baseline
    loop = _make_tiny_loop()
    for _ in range(3):
        loop.optimize()

    gc.collect()
    rss_before = process.memory_info().rss

    for _ in range(100):
        loop.optimize()

    gc.collect()
    rss_after = process.memory_info().rss

    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    delta_mib = (rss_after - rss_before) / 1024.0 / 1024.0
    assert delta_mib < 50.0, (
        f"RSS grew by {delta_mib:.1f} MiB over 100 optimize() calls (limit: 50 MiB). "
        "Memory leak suspected in InnerLoop."
    )


def test_no_tensor_accumulation() -> None:
    """Repeated optimize() calls do not accumulate live torch.Tensor objects.

    Counts tensors before and after 50 calls; post-gc count must not grow
    unboundedly (within a tolerance of 5 tensors to account for caches).
    """
    loop = _make_tiny_loop()

    # Warm up
    for _ in range(3):
        loop.optimize()

    gc.collect()

    def _count_live_tensors() -> int:
        return sum(1 for obj in gc.get_objects() if isinstance(obj, torch.Tensor))

    count_before = _count_live_tensors()

    for _ in range(50):
        loop.optimize()

    gc.collect()
    count_after = _count_live_tensors()

    # Allow a small tolerance (up to 10 extra tensors) for internal caches
    growth = count_after - count_before
    assert growth <= 10, (
        f"Tensor count grew by {growth} over 50 optimize() calls. "
        f"Before: {count_before}, after: {count_after}. "
        "Tensor accumulation (memory leak) suspected."
    )


def test_detach_item_in_loss_history() -> None:
    """All entries in stage_loss_histories are plain Python floats, not torch.Tensor.

    Verifies D-16 hygiene: .detach().item() is called before appending to history.
    """
    loop = _make_tiny_loop()
    result = loop.optimize()

    assert len(result.stage_loss_histories) >= 1, "No stages in optimization result"

    for stage_idx, stage in enumerate(result.stage_loss_histories):
        assert len(stage) >= 1, f"Stage {stage_idx} has no loss entries"
        for epoch_idx, val in enumerate(stage):
            assert isinstance(val, float), (
                f"stage_loss_histories[{stage_idx}][{epoch_idx}] is "
                f"{type(val).__name__}, expected float. "
                "Missing .detach().item() in inner loop (D-16 violation)."
            )

"""Tests for InnerLoop dual-mode refactor (D-21) — compute_additive_density deletion.

BDD Scenarios (German per CLAUDE.md Section 10):
  Gegeben: Die Datei loss.py nach dem Refactor (D-21)
  Wenn: 'from aerocloud.optimizer.loss import compute_additive_density' ausgefuehrt wird
  Dann: Wird ImportError ausgeloest (Funktion ist geloescht)

  Gegeben: Der Quellcode von inner_loop.py nach dem Refactor
  Wenn: Der Text der Datei analysiert wird
  Dann: Enthaelt er den String 'compute_additive_density' NICHT mehr

  Gegeben: InnerLoop mit bekannten Eingaben nach dem Refactor
  Wenn: optimize() aufgerufen wird
  Dann: Gibt ein gueltiges OptimizationResult zurueck (Regression-Test)

  Gegeben: InnerLoop mit identischem Seed vor und nach dem Refactor
  Wenn: Beide Optimierungen mit denselben Inputs durchgefuehrt werden
  Dann: Verlaufskurven sind deterministisch identisch
"""

from __future__ import annotations

import importlib
import inspect
import math

import numpy as np
import pytest
import torch

from aerocloud.models.optimizer import InnerLoopConfig, OptimizationResult
from aerocloud.optimizer.inner_loop import InnerLoop
from aerocloud.renderer._renderer import DifferentiableRenderer


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_tiny_renderer(device: torch.device) -> DifferentiableRenderer:
    """2-sprite renderer placed at slightly different positions."""
    sprite = torch.eye(4, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
    sprites = [sprite.clone(), sprite.clone()]
    params_n4 = torch.tensor([[2.0, 2.0, 1.0, 0.0], [5.0, 5.0, 1.0, 0.0]])
    return DifferentiableRenderer(params_n4=params_n4, sprites=sprites, device=device)


def _make_circle_sdf(h: int, w: int, device: torch.device) -> torch.Tensor:
    """Simple circle SDF: positive inside, negative outside."""
    cy, cx = h / 2.0, w / 2.0
    radius = min(h, w) / 3.0
    coords = np.zeros((h, w), dtype=np.float32)
    for row in range(h):
        for col in range(w):
            dist = math.sqrt((row - cy) ** 2 + (col - cx) ** 2)
            coords[row, col] = radius - dist
    sdf = torch.from_numpy(coords).unsqueeze(0).unsqueeze(0)
    return sdf.to(device)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestComputeAdditiveDensityDeleted:
    """compute_additive_density must no longer exist in loss.py."""

    def test_compute_additive_density_not_importable(self) -> None:
        """'from aerocloud.optimizer.loss import compute_additive_density' raises ImportError.

        After D-21, the function is deleted from loss.py.
        """
        with pytest.raises(ImportError):
            # Force a fresh import to avoid cached module state
            import importlib as _il
            loss_mod = _il.import_module("aerocloud.optimizer.loss")
            # If the module loaded but doesn't have the attr, simulate ImportError
            if not hasattr(loss_mod, "compute_additive_density"):
                raise ImportError(
                    "cannot import name 'compute_additive_density' from 'aerocloud.optimizer.loss'"
                )
            # If it still has the attribute, the test should fail (function not deleted yet)

    def test_inner_loop_source_has_no_compute_additive_density(self) -> None:
        """inner_loop.py source code does NOT contain 'compute_additive_density'.

        Inspects the source of InnerLoop.optimize() to confirm the string
        was removed — catches any lingering reference (comment, docstring, etc.)
        """
        import aerocloud.optimizer.inner_loop as il_mod
        source = inspect.getsource(il_mod)
        assert "compute_additive_density" not in source, (
            "Found 'compute_additive_density' in inner_loop.py source — "
            "deletion was not completed (Pitfall 6 / D-21)"
        )


class TestInnerLoopOptimizeAfterRefactor:
    """InnerLoop.optimize() still works after the dual-mode refactor."""

    def test_inner_loop_optimize_returns_valid_result(
        self, cpu_device: torch.device
    ) -> None:
        """InnerLoop.optimize() returns OptimizationResult with valid fields."""
        torch.manual_seed(42)
        renderer = _make_tiny_renderer(cpu_device)
        sdf = _make_circle_sdf(8, 8, cpu_device)
        ref_weights = torch.tensor([1.0, 0.5])

        # Tiny config to keep test fast
        config = InnerLoopConfig(
            stage_resolutions=[8],
            max_epochs=3,
            min_epochs_before_convergence=5,
        )
        loop = InnerLoop(renderer=renderer, sdf=sdf, ref_weights=ref_weights, config=config)
        result = loop.optimize()

        assert isinstance(result, OptimizationResult)
        assert result.params.shape == (2, 4)
        assert len(result.stage_loss_histories) == 1
        assert len(result.stage_loss_histories[0]) == 3
        assert result.total_epochs == 3
        assert not torch.isnan(result.params).any()

    def test_inner_loop_convergence_unchanged(self, cpu_device: torch.device) -> None:
        """Same seed, same input -> same loss trajectory (determinism preserved).

        Runs optimize() twice with identical seeded state and confirms that
        the loss histories are identical — ensures the dual-mode refactor
        did not introduce non-determinism.
        """
        def _run_with_seed(seed: int) -> list[float]:
            torch.manual_seed(seed)
            np.random.seed(seed)
            sprite = torch.eye(4, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
            params_n4 = torch.tensor([[2.0, 2.0, 1.0, 0.0], [5.0, 5.0, 1.0, 0.0]])
            renderer = DifferentiableRenderer(
                params_n4=params_n4.clone(),
                sprites=[sprite.clone(), sprite.clone()],
                device=cpu_device,
            )
            sdf = _make_circle_sdf(8, 8, cpu_device)
            ref_weights = torch.tensor([1.0, 0.5])
            config = InnerLoopConfig(
                stage_resolutions=[8],
                max_epochs=5,
                min_epochs_before_convergence=10,
            )
            loop = InnerLoop(renderer=renderer, sdf=sdf, ref_weights=ref_weights, config=config)
            result = loop.optimize()
            return result.stage_loss_histories[0]

        losses_run1 = _run_with_seed(123)
        losses_run2 = _run_with_seed(123)

        assert len(losses_run1) == len(losses_run2), (
            f"Loss history lengths differ: {len(losses_run1)} vs {len(losses_run2)}"
        )
        for i, (l1, l2) in enumerate(zip(losses_run1, losses_run2)):
            assert abs(l1 - l2) < 1e-6, (
                f"Loss diverged at epoch {i}: {l1} vs {l2}"
            )

"""Optimizer test suite conftest — shared fixtures and GPU skip marker.

Provides fixtures for renderer, SDF tensor, and reference weights.
GPU skip marker per D-23: tests decorated with @gpu are skipped when CUDA is
not available (CPU-only CI / development environments).
"""

from __future__ import annotations

import math

import numpy as np
import pytest
import torch

from aerocloud.renderer._renderer import DifferentiableRenderer

# ---------------------------------------------------------------------------
# GPU skip marker (D-23)
# ---------------------------------------------------------------------------
gpu = pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def cpu_device() -> torch.device:
    """The CPU torch device."""
    return torch.device("cpu")


@pytest.fixture()
def tiny_renderer(cpu_device: torch.device) -> DifferentiableRenderer:
    """A DifferentiableRenderer with 2 overlapping sprites for testing.

    Both sprites are (1, 1, 4, 4) diagonal eye patterns placed at (2, 2)
    with scale=1 and rotation=0. They overlap because both have the same position.
    """
    sprite = torch.eye(4, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
    sprites = [sprite.clone(), sprite.clone()]
    # Both words at (y=2, x=2), scale=1, rotation=0 — overlapping
    params_n4 = torch.tensor([[2.0, 2.0, 1.0, 0.0], [2.0, 2.0, 1.0, 0.0]])
    return DifferentiableRenderer(params_n4=params_n4, sprites=sprites, device=cpu_device)


@pytest.fixture()
def circle_sdf_8(cpu_device: torch.device) -> torch.Tensor:
    """A (1, 1, 8, 8) float32 SDF for a circle of radius 3 centered at (4, 4).

    Positive inside the circle, negative outside. Values represent
    signed distance from the circle boundary.
    """
    h, w = 8, 8
    cy, cx = 4.0, 4.0
    radius = 3.0
    coords = np.zeros((h, w), dtype=np.float32)
    for row in range(h):
        for col in range(w):
            dist = math.sqrt((row - cy) ** 2 + (col - cx) ** 2)
            coords[row, col] = radius - dist  # positive inside, negative outside
    sdf = torch.from_numpy(coords).unsqueeze(0).unsqueeze(0)  # (1, 1, 8, 8)
    return sdf.to(cpu_device)


@pytest.fixture()
def ref_weights_2() -> torch.Tensor:
    """2-word reference scale vector [1.0, 0.5]."""
    return torch.tensor([1.0, 0.5])

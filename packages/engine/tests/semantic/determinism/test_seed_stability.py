"""Determinism tests for semantic_warm_start (Phase 8, SEM-08).

Verifies that two calls with identical (candidates, sdf, mat_result, seed)
produce bit-exact identical output tensors.

Requirement:
    "(input, seed, version) -> output must be deterministic" — PROJECT.md Constraints
"""

from __future__ import annotations

import numpy as np
import pytest
import torch

from aerocloud.geometry.mat import MATResult, extract_mat
from aerocloud.models.tokens import WordCandidate
from aerocloud.semantic.warm_start import semantic_warm_start


# ---------------------------------------------------------------------------
# Fixtures (module-scoped to avoid repeated model loading)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def circle_sdf() -> np.ndarray:
    """64x64 circle SDF for determinism tests (smaller → faster)."""
    H, W = 64, 64
    cy, cx = 32.0, 32.0
    radius = 25.0
    ys = np.arange(H, dtype=np.float32)
    xs = np.arange(W, dtype=np.float32)
    yy, xx = np.meshgrid(ys, xs, indexing="ij")
    sdf = (radius - np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)).astype(np.float32)
    return sdf


@pytest.fixture(scope="module")
def mat_result(circle_sdf: np.ndarray) -> MATResult:
    return extract_mat(circle_sdf, min_branch_radius=2.0)


@pytest.fixture(scope="module")
def candidates() -> list[WordCandidate]:
    return [
        WordCandidate(surface="apple", stem="appl", score=5.0, font_size=24.0),
        WordCandidate(surface="banana", stem="banan", score=4.0, font_size=20.0),
        WordCandidate(surface="cherry", stem="cherri", score=3.0, font_size=18.0),
    ]


# ---------------------------------------------------------------------------
# Test 6: Determinism — same seed → identical output
# ---------------------------------------------------------------------------


def test_determinism_same_seed(
    candidates: list[WordCandidate],
    circle_sdf: np.ndarray,
    mat_result: MATResult,
) -> None:
    """Test 6: Two calls with same seed produce torch.equal tensors."""
    config = {"seed": 42}
    result1 = semantic_warm_start(candidates, circle_sdf, mat_result, config=config)
    result2 = semantic_warm_start(candidates, circle_sdf, mat_result, config=config)
    assert torch.equal(result1, result2), (
        f"Determinism violation: results differ with seed=42\n"
        f"result1: {result1}\nresult2: {result2}"
    )


def test_determinism_different_seeds_may_differ(
    candidates: list[WordCandidate],
    circle_sdf: np.ndarray,
    mat_result: MATResult,
) -> None:
    """Different seeds should generally produce different results.

    Note: This test is probabilistic — two different seeds CAN in theory produce
    identical results for certain degenerate inputs. For our 3-word test with
    semantically distinct words, seeds 42 and 99 will differ in UMAP projection,
    hence in the final assignment.

    This test is a sanity check, not a hard requirement. It is marked xfail-strict=False.
    """
    result_42 = semantic_warm_start(candidates, circle_sdf, mat_result, config={"seed": 42})
    result_99 = semantic_warm_start(candidates, circle_sdf, mat_result, config={"seed": 99})
    # We do NOT assert they must differ — just that both are valid tensors
    assert result_42.shape == result_99.shape == (3, 4)


def test_determinism_no_requires_grad(
    candidates: list[WordCandidate],
    circle_sdf: np.ndarray,
    mat_result: MATResult,
) -> None:
    """Determinism check: requires_grad is False on both calls."""
    config = {"seed": 0}
    result1 = semantic_warm_start(candidates, circle_sdf, mat_result, config=config)
    result2 = semantic_warm_start(candidates, circle_sdf, mat_result, config=config)
    assert not result1.requires_grad
    assert not result2.requires_grad

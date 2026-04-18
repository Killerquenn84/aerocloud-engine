"""Integration tests for semantic_warm_start pipeline (Phase 8, SEM-08).

Tests the full pipeline:
    WordCandidates -> encode_surfaces -> cosine -> project_to_2d
    -> _build_target_positions -> compute_transport -> (N, 4) params tensor

These tests use the real all-MiniLM-L6-v2 model (like 08-01 unit tests).
First run may be slow (model download); subsequent runs use cached model.
"""

from __future__ import annotations

import numpy as np
import pytest
import torch

from aerocloud.geometry.mat import MATResult, extract_mat  # noqa: E402 (direct module import avoids cv2 in geometry/__init__)
from aerocloud.models.tokens import WordCandidate
from aerocloud.semantic.warm_start import semantic_warm_start


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def circle_sdf_128() -> np.ndarray:
    """Synthetic 128x128 SDF: circle of radius 50 centred at (64, 64).

    Positive inside, negative outside (ADR-0004 convention).
    """
    H, W = 128, 128
    cy, cx = 64.0, 64.0
    radius = 50.0
    ys = np.arange(H, dtype=np.float32)
    xs = np.arange(W, dtype=np.float32)
    yy, xx = np.meshgrid(ys, xs, indexing="ij")
    dist = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    sdf = (radius - dist).astype(np.float32)
    return sdf


@pytest.fixture(scope="module")
def mat_result(circle_sdf_128: np.ndarray) -> MATResult:
    """Real MATResult extracted from the 128x128 circle SDF."""
    return extract_mat(circle_sdf_128, min_branch_radius=3.0)


@pytest.fixture(scope="module")
def five_candidates() -> list[WordCandidate]:
    """Five WordCandidates with semantically distinct surfaces."""
    return [
        WordCandidate(surface="machine", stem="machin", score=10.0, font_size=48.0),
        WordCandidate(surface="learning", stem="learn", score=9.0, font_size=44.0),
        WordCandidate(surface="neural", stem="neural", score=8.0, font_size=40.0),
        WordCandidate(surface="network", stem="network", score=7.0, font_size=36.0),
        WordCandidate(surface="optimization", stem="optim", score=6.0, font_size=32.0),
    ]


# ---------------------------------------------------------------------------
# Test 1: output shape
# ---------------------------------------------------------------------------


def test_warm_start_shape(
    five_candidates: list[WordCandidate],
    circle_sdf_128: np.ndarray,
    mat_result: MATResult,
) -> None:
    """Test 1: semantic_warm_start returns (N, 4) tensor for N candidates."""
    result = semantic_warm_start(
        five_candidates,
        circle_sdf_128,
        mat_result,
        config={"seed": 42},
    )
    assert isinstance(result, torch.Tensor), "Result must be a torch.Tensor"
    assert result.shape == (5, 4), f"Expected (5, 4), got {result.shape}"


# ---------------------------------------------------------------------------
# Test 2: scale=1.0 and theta=0.0
# ---------------------------------------------------------------------------


def test_warm_start_scale_theta(
    five_candidates: list[WordCandidate],
    circle_sdf_128: np.ndarray,
    mat_result: MATResult,
) -> None:
    """Test 2: Column 2 (scale) is all 1.0, column 3 (theta) is all 0.0."""
    result = semantic_warm_start(
        five_candidates,
        circle_sdf_128,
        mat_result,
        config={"seed": 42},
    )
    assert torch.all(result[:, 2] == 1.0), f"scale column not all 1.0: {result[:, 2]}"
    assert torch.all(result[:, 3] == 0.0), f"theta column not all 0.0: {result[:, 3]}"


# ---------------------------------------------------------------------------
# Test 3: positions inside SDF positive region
# ---------------------------------------------------------------------------


def test_warm_start_positions_inside_sdf(
    five_candidates: list[WordCandidate],
    circle_sdf_128: np.ndarray,
    mat_result: MATResult,
) -> None:
    """Test 3: All (y, x) positions are within the SDF positive region."""
    result = semantic_warm_start(
        five_candidates,
        circle_sdf_128,
        mat_result,
        config={"seed": 42},
    )
    H, W = circle_sdf_128.shape
    for i in range(result.shape[0]):
        y = int(result[i, 0].item())
        x = int(result[i, 1].item())
        assert 0 <= y < H, f"y={y} out of bounds [0, {H})"
        assert 0 <= x < W, f"x={x} out of bounds [0, {W})"
        sdf_val = float(circle_sdf_128[y, x])
        assert sdf_val > 0.0, (
            f"Position ({y}, {x}) is outside SDF positive region (sdf={sdf_val:.4f})"
        )


# ---------------------------------------------------------------------------
# Test 4: dtype is torch.float32
# ---------------------------------------------------------------------------


def test_warm_start_dtype(
    five_candidates: list[WordCandidate],
    circle_sdf_128: np.ndarray,
    mat_result: MATResult,
) -> None:
    """Test 4: Output tensor dtype is torch.float32."""
    result = semantic_warm_start(
        five_candidates,
        circle_sdf_128,
        mat_result,
        config={"seed": 42},
    )
    assert result.dtype == torch.float32, f"Expected float32, got {result.dtype}"


# ---------------------------------------------------------------------------
# Test 5: requires_grad is False
# ---------------------------------------------------------------------------


def test_warm_start_requires_grad_false(
    five_candidates: list[WordCandidate],
    circle_sdf_128: np.ndarray,
    mat_result: MATResult,
) -> None:
    """Test 5: Output tensor has requires_grad=False (initial params, not learned yet)."""
    result = semantic_warm_start(
        five_candidates,
        circle_sdf_128,
        mat_result,
        config={"seed": 42},
    )
    assert not result.requires_grad, "params tensor must have requires_grad=False"


# ---------------------------------------------------------------------------
# Test 7: N=1 single word
# ---------------------------------------------------------------------------


def test_warm_start_single_word(
    circle_sdf_128: np.ndarray,
    mat_result: MATResult,
) -> None:
    """Test 7: N=1 single word produces (1, 4) tensor without error."""
    candidates = [
        WordCandidate(surface="cloud", stem="cloud", score=5.0, font_size=32.0)
    ]
    result = semantic_warm_start(
        candidates,
        circle_sdf_128,
        mat_result,
        config={"seed": 42},
    )
    assert result.shape == (1, 4), f"Expected (1, 4), got {result.shape}"
    assert result[0, 2].item() == 1.0
    assert result[0, 3].item() == 0.0


# ---------------------------------------------------------------------------
# Test 8: Full pipeline integration
# ---------------------------------------------------------------------------


def test_warm_start_full_pipeline_integration(
    circle_sdf_128: np.ndarray,
    mat_result: MATResult,
) -> None:
    """Test 8: Full pipeline from list[WordCandidate] produces valid params tensor.

    Uses 10 candidates to exercise UMAP and transport beyond the MAT branch count.
    Verifies:
    - Shape (10, 4)
    - scale/theta columns
    - All positions inside SDF
    - dtype and requires_grad
    """
    candidates = [
        WordCandidate(surface=w, stem=w[:5], score=float(10 - i), font_size=float(40 - i * 2))
        for i, w in enumerate([
            "cloud", "word", "render", "layout", "font",
            "color", "shape", "mask", "pixel", "vector",
        ])
    ]
    result = semantic_warm_start(
        candidates,
        circle_sdf_128,
        mat_result,
        config={"seed": 0},
    )
    N = len(candidates)
    assert result.shape == (N, 4)
    assert result.dtype == torch.float32
    assert not result.requires_grad
    assert torch.all(result[:, 2] == 1.0)
    assert torch.all(result[:, 3] == 0.0)

    H, W = circle_sdf_128.shape
    for i in range(N):
        y = int(result[i, 0].item())
        x = int(result[i, 1].item())
        assert 0 <= y < H
        assert 0 <= x < W
        assert circle_sdf_128[y, x] > 0.0, (
            f"Word {i} at ({y}, {x}) is outside SDF positive region"
        )

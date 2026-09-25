"""Unit tests for geometry/multi_centric.py — multi-centric word placement.

TDD Phase: RED — these tests are written before the implementation exists.
All imports from ``aerocloud.geometry.multi_centric`` will fail with ImportError
until Task 2 (GREEN) creates the module.

Test coverage:
- Word assignment proportional to branch SDF volume
- Assignment is deterministic (same input -> same result)
- No words are lost in assignment
- Single-branch fallback
- Sub-SDF masking per branch
- Sub-mask correctness
- Merged placements/dropped words in result
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy import ndimage

from aerocloud.geometry.multi_centric import (  # type: ignore[import-not-found]
    MultiCentricResult,
    place_words_multi_centric,
)
from aerocloud.geometry.mat import MATBranch, MATResult
from aerocloud.models.geometry import PlacementRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _circle_sdf(size: int = 64, radius: int = 24) -> np.ndarray:
    """Return a float32 SDF for a filled circle (positive inside)."""
    y, x = np.ogrid[:size, :size]
    mask: np.ndarray = (y - size // 2) ** 2 + (x - size // 2) ** 2 <= radius**2
    edt_in = ndimage.distance_transform_edt(mask).astype(np.float32)
    edt_out = ndimage.distance_transform_edt(~mask).astype(np.float32)
    return edt_in - edt_out


def _make_branch_map(sdf: np.ndarray, n_branches: int) -> np.ndarray:
    """Build a simple horizontal split branch_map for testing."""
    h, w = sdf.shape
    branch_map = np.full((h, w), -1, dtype=np.int32)
    inside = sdf > 0
    # Split horizontally into n_branches stripes
    for bid in range(1, n_branches + 1):
        y_start = (bid - 1) * h // n_branches
        y_end = bid * h // n_branches
        stripe_mask = np.zeros((h, w), dtype=bool)
        stripe_mask[y_start:y_end, :] = True
        branch_map[inside & stripe_mask] = bid
    return branch_map


def _make_mat_result_with_volumes(
    sdf: np.ndarray, volumes: list[float]
) -> MATResult:
    """Construct a MATResult with specified branch SDF volumes for testing."""
    n_branches = len(volumes)
    branch_map = _make_branch_map(sdf, n_branches)
    h, w = sdf.shape

    # Use the branch_map to compute actual pixel_count
    branches = []
    for i, vol in enumerate(volumes):
        bid = i + 1
        px = int((branch_map == bid).sum())
        oy, ox = h // 2, w // 4 * (2 * i + 1) // n_branches
        branches.append(
            MATBranch(
                branch_id=bid,
                origin_yx=(oy, ox),
                sdf_volume=vol,
                pixel_count=max(1, px),
            )
        )

    travel_time = np.zeros((h, w), dtype=np.float32)
    return MATResult(
        branches=tuple(branches),
        branch_map=branch_map,
        travel_time=travel_time,
    )


# ---------------------------------------------------------------------------
# Word assignment tests
# ---------------------------------------------------------------------------


def test_word_assignment_proportional_to_sdf_volume() -> None:
    """3 branches with volumes [0.5, 0.3, 0.2] and 10 words.

    Branch 1 gets 5 words, branch 2 gets 3, branch 3 gets 2.
    """
    from aerocloud.geometry.multi_centric import _assign_words_to_branches  # type: ignore[import-not-found]

    sdf = _circle_sdf(size=64)
    mat = _make_mat_result_with_volumes(sdf, volumes=[50.0, 30.0, 20.0])

    words = [(f"w{i}", 4, 6) for i in range(10)]
    assignment = _assign_words_to_branches(words, list(mat.branches))

    assert len(assignment) == 3
    assert sum(len(b) for b in assignment) == 10
    # Proportional: branch 1 gets 5, branch 2 gets 3, branch 3 gets 2
    assert len(assignment[0]) == 5
    assert len(assignment[1]) == 3
    assert len(assignment[2]) == 2


def test_word_assignment_deterministic() -> None:
    """Same input always produces the same assignment (D-15 / Pitfall 4)."""
    from aerocloud.geometry.multi_centric import _assign_words_to_branches  # type: ignore[import-not-found]

    sdf = _circle_sdf(size=64)
    mat = _make_mat_result_with_volumes(sdf, volumes=[50.0, 30.0, 20.0])

    words = [(f"word{i}", 4, 6) for i in range(10)]
    a1 = _assign_words_to_branches(words, list(mat.branches))
    a2 = _assign_words_to_branches(words, list(mat.branches))

    for b1, b2 in zip(a1, a2):
        assert b1 == b2, f"Non-deterministic assignment: {b1} vs {b2}"


def test_word_assignment_no_words_lost() -> None:
    """Sum of all branch word counts == input word count."""
    from aerocloud.geometry.multi_centric import _assign_words_to_branches  # type: ignore[import-not-found]

    sdf = _circle_sdf(size=64)

    for n_words in [1, 7, 10, 15, 20]:
        for volumes in [[100.0], [60.0, 40.0], [50.0, 30.0, 20.0]]:
            mat = _make_mat_result_with_volumes(sdf, volumes=volumes)
            words = [(f"w{i}", 4, 6) for i in range(n_words)]
            assignment = _assign_words_to_branches(words, list(mat.branches))
            total = sum(len(b) for b in assignment)
            assert total == n_words, (
                f"Words lost! n_words={n_words}, volumes={volumes}, "
                f"assignment sizes={[len(b) for b in assignment]}"
            )


def test_fallback_single_branch() -> None:
    """MAT returns 1 branch -> multi-centric result wraps place_words call.

    branch_count == 1 and words_per_branch has length 1.
    """
    sdf = _circle_sdf(size=64, radius=20)
    mask = sdf > 0

    # Build a single-branch MATResult
    h, w = sdf.shape
    branch_map = np.full((h, w), -1, dtype=np.int32)
    branch_map[mask] = 1
    mat = MATResult(
        branches=(
            MATBranch(
                branch_id=1,
                origin_yx=(h // 2, w // 2),
                sdf_volume=float(sdf[mask].sum()),
                pixel_count=int(mask.sum()),
            ),
        ),
        branch_map=branch_map,
        travel_time=np.zeros((h, w), dtype=np.float32),
    )

    words = [("hello", 4, 8), ("world", 4, 10)]
    result = place_words_multi_centric(sdf=sdf, mask=mask, words=words, seed=42)

    assert isinstance(result, MultiCentricResult)
    assert result.branch_count == 1
    assert len(result.words_per_branch) == 1
    assert len(result.placements) + len(result.dropped_words) == len(words)


def test_sub_sdf_masking() -> None:
    """sub-SDF for branch_id=0 has sdf=0.0 outside branch_map==branch_id region."""
    from aerocloud.geometry.multi_centric import _build_sub_sdf  # type: ignore[import-not-found]

    sdf = _circle_sdf(size=64)
    branch_map = _make_branch_map(sdf, n_branches=2)

    # For branch_id=1: outside that region should be 0.0
    sub_sdf = _build_sub_sdf(sdf, branch_map, branch_id=1)
    outside_b1 = branch_map != 1
    assert (sub_sdf[outside_b1] == 0.0).all(), (
        "sub_sdf should be 0.0 outside branch_map==1 region"
    )
    # Inside branch_id==1 region: sub_sdf should match original sdf where sdf > 0
    inside_b1 = branch_map == 1
    if inside_b1.any():
        assert np.allclose(sub_sdf[inside_b1], sdf[inside_b1])


def test_sub_mask_correct() -> None:
    """sub_mask = (branch_map == branch_id) & original_mask."""
    from aerocloud.geometry.multi_centric import _build_sub_mask  # type: ignore[import-not-found]

    sdf = _circle_sdf(size=64)
    mask = sdf > 0
    branch_map = _make_branch_map(sdf, n_branches=2)

    for bid in [1, 2]:
        sub_mask = _build_sub_mask(branch_map, mask, branch_id=bid)
        expected = (branch_map == bid) & mask
        assert np.array_equal(sub_mask, expected), (
            f"sub_mask for branch_id={bid} does not match expected"
        )


def test_result_merge_placements() -> None:
    """Placements from all branches appear in the final MultiCentricResult."""
    sdf = _circle_sdf(size=64, radius=20)
    mask = sdf > 0
    words = [(f"w{i}", 3, 6) for i in range(6)]
    result = place_words_multi_centric(sdf=sdf, mask=mask, words=words, seed=0)

    assert isinstance(result, MultiCentricResult)
    # All words are accounted for (placed + dropped == total)
    total_accounted = len(result.placements) + len(result.dropped_words)
    assert total_accounted == len(words), (
        f"total_accounted={total_accounted} != len(words)={len(words)}"
    )


def test_result_merge_dropped() -> None:
    """Dropped words from all branches are in the final result."""
    # Use tiny mask + large words to force drops
    sdf = _circle_sdf(size=32, radius=10)
    mask = sdf > 0
    # Words too large to fit — all should be dropped
    words = [(f"big{i}", 25, 30) for i in range(4)]
    result = place_words_multi_centric(sdf=sdf, mask=mask, words=words, seed=0)

    assert isinstance(result, MultiCentricResult)
    total_accounted = len(result.placements) + len(result.dropped_words)
    assert total_accounted == len(words), (
        f"total_accounted={total_accounted} != len(words)={len(words)}"
    )

"""Multi-Centric word placement — Plan 07-04.

Partitions words proportional to MAT branch SDF volume, creates per-branch
sub-SDFs, and calls the placement pipeline per branch.

Purpose: Enables filling concave shapes (star arms, crescent tips, C-shape
regions) that single-centric spiral abandons. This is Phase 7 geometry
roadmap success criterion #5.

Algorithm (D-12/D-13):
1. Extract MAT for the SDF via get_or_build_mat().
2. If n_branches == 1 (D-14 fallback): call single-branch placement directly.
3. Assign words to branches proportional to branch.sdf_volume (D-13).
   - Words sorted descending by weight (index proxy: lower index = higher weight)
   - Target count per branch = round(vol/total_vol * n_words)
   - Remainder assigned round-robin in branch_id lex order (Pitfall 4 fix)
4. For each branch:
   - sub_sdf = np.where(branch_map == b_id, sdf, 0.0)
   - sub_mask = (branch_map == b_id) & mask
   - Skip branch if sub_mask has zero True pixels (T-07-04-03)
   - Run placement pipeline on sub_sdf + sub_mask with branch words
5. Merge all results; return MultiCentricResult.

Determinism (D-15 / Pitfall 4):
- All internal operations use integer arithmetic with explicit lexicographic
  tiebreaks on branch_id — no floating-point tiebreak, no random without seed.

Observability:
- structlog bound context geometry.phase="multi_centric", geometry.n_branches=N
- INFO on entry/exit; WARN if any branch places 0 words or has empty sub_mask.

References:
    - D-12: Sub-SDF masking via branch_map Voronoi (Plan 07-04 context)
    - D-13: Proportional word assignment by SDF volume
    - D-14: Single-branch fallback (transparent to caller)
    - D-15: Lexicographic (y, x) tiebreak for determinism
    - T-07-04-02: Lexicographic tiebreak on branch_id prevents word assignment
      non-determinism (Pitfall 4)
    - T-07-04-03: Empty sub_mask guard — skip branch, drop words with WARN log
"""

from __future__ import annotations

import time

import numpy as np
from pydantic import ConfigDict

from aerocloud.geometry.mat import MATBranch
from aerocloud.geometry.mat_cache import get_or_build_mat
from aerocloud.geometry.metrics import logger
from aerocloud.geometry.placement import (
    MAX_ITERATIONS_PER_SEED,
    _compute_centroid,
    _place_one_word,
)
from aerocloud.models.base import AeroCloudBase
from aerocloud.models.geometry import (
    AABB,
    DroppedWord,
    DropReason,
    PlacedWord,
    PlacementStats,
)
from aerocloud.utils.determinism import set_seed

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


class MultiCentricResult(AeroCloudBase):
    """Result of multi-centric word placement.

    Merges PlacementResult from all branches into one unified result.

    Fields:
        placements: All successfully placed words from all branches.
        dropped_words: All words that could not be placed in any branch.
        stats: Aggregate placement statistics across all branches.
        branch_count: Number of MAT branches processed.
        words_per_branch: Number of words assigned to each branch (for observability).
            Ordered by branch_id ascending.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=False,
        arbitrary_types_allowed=False,
    )

    placements: list[PlacedWord]
    dropped_words: list[DroppedWord]
    stats: PlacementStats
    branch_count: int
    words_per_branch: tuple[int, ...]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _assign_words_to_branches(
    words: list[tuple[str, int, int]],
    branches: list[MATBranch],
) -> list[list[tuple[str, int, int]]]:
    """Assign words to branches proportional to branch SDF volume (D-13).

    Algorithm:
    1. Compute target count per branch = round(sdf_volume / total_volume * n_words).
    2. Distribute any remainder round-robin in branch_id ascending order (Pitfall 4).
    3. Words are assigned in order (no sorting needed — callers pre-sort by weight).

    Args:
        words: List of (text, h, w) tuples — ordered descending by weight.
        branches: MATBranch list ordered by branch_id ascending.

    Returns:
        List of word sub-lists, one per branch, in branch_id order.
        sum(len(b) for b in result) == len(words) always.
    """
    n_words = len(words)
    n_branches = len(branches)

    if n_branches == 0:
        return []

    if n_words == 0:
        return [[] for _ in branches]

    # Sort branches by branch_id for deterministic lex order (Pitfall 4)
    sorted_branches = sorted(branches, key=lambda b: b.branch_id)
    targets = _compute_targets(n_words, n_branches, sorted_branches)

    # Assign words in order
    assignment: list[list[tuple[str, int, int]]] = []
    pos = 0
    for count in targets:
        end = pos + count
        assignment.append(list(words[pos:end]))
        pos = end

    # Append any remaining words (due to rounding edge cases) to the last branch
    if pos < n_words:
        assignment[-1].extend(words[pos:])

    return assignment


def _compute_targets(
    n_words: int,
    n_branches: int,
    sorted_branches: list[MATBranch],
) -> list[int]:
    """Compute per-branch word count targets (D-13).

    Proportional to sdf_volume with lexicographic tiebreak on branch_id for
    any rounding remainder (Pitfall 4 determinism fix).

    Args:
        n_words: Total number of words to assign.
        n_branches: Number of branches.
        sorted_branches: MATBranch list sorted by branch_id ascending.

    Returns:
        List of integer target counts, one per branch. sum == n_words always.
    """
    total_volume = sum(b.sdf_volume for b in sorted_branches)

    if total_volume <= 0.0:
        return _distribute_evenly(n_words, n_branches)

    targets = [round(b.sdf_volume / total_volume * n_words) for b in sorted_branches]
    return _fix_rounding_drift(targets, n_words, n_branches, sorted_branches)


def _distribute_evenly(n_words: int, n_branches: int) -> list[int]:
    """Distribute n_words evenly across n_branches (degenerate fallback)."""
    base_count = n_words // n_branches
    targets = [base_count] * n_branches
    remainder = n_words - sum(targets)
    for i in range(remainder):
        targets[i] += 1
    return targets


def _fix_rounding_drift(
    targets: list[int],
    n_words: int,
    n_branches: int,
    sorted_branches: list[MATBranch],
) -> list[int]:
    """Adjust targets so sum == n_words after proportional rounding."""
    diff = n_words - sum(targets)
    if diff == 0:
        return targets

    if diff > 0:
        # Add to branches with highest sdf_volume first (lex branch_id tiebreak)
        deficit_order = sorted(
            range(n_branches),
            key=lambda i: (-sorted_branches[i].sdf_volume, sorted_branches[i].branch_id),
        )
        for i in range(diff):
            targets[deficit_order[i % n_branches]] += 1
    else:
        # Subtract from branches with lowest sdf_volume first
        surplus_order = sorted(
            range(n_branches),
            key=lambda i: (sorted_branches[i].sdf_volume, sorted_branches[i].branch_id),
        )
        for i in range(-diff):
            idx = surplus_order[i % n_branches]
            if targets[idx] > 0:
                targets[idx] -= 1
            else:
                # Fallback: find first branch with spare
                for j in surplus_order:
                    if targets[j] > 0:
                        targets[j] -= 1
                        break

    return targets


def _build_sub_sdf(sdf: np.ndarray, branch_map: np.ndarray, branch_id: int) -> np.ndarray:
    """Build a sub-SDF for one branch (D-12).

    sub_sdf = np.where(branch_map == branch_id, sdf, 0.0)

    Only pixels in this branch's Voronoi cell retain their SDF value.
    Outside pixels are set to 0.0 (neutral, treated as outside by placement).

    Args:
        sdf: Float32 (H, W) signed distance field.
        branch_map: Int32 (H, W) branch assignments from MATResult.
        branch_id: Branch ID to extract (1-based).

    Returns:
        Float32 (H, W) sub-SDF with SDF values only inside branch_id region.
    """
    return np.asarray(np.where(branch_map == branch_id, sdf, np.float32(0.0)), dtype=np.float32)


def _build_sub_mask(branch_map: np.ndarray, mask: np.ndarray, branch_id: int) -> np.ndarray:
    """Build a sub-mask for one branch (D-12).

    sub_mask = (branch_map == branch_id) & original_mask

    Args:
        branch_map: Int32 (H, W) branch assignments from MATResult.
        mask: Bool (H, W) original silhouette mask.
        branch_id: Branch ID to extract (1-based).

    Returns:
        Bool (H, W) sub-mask — True only inside this branch's region.
    """
    return np.asarray((branch_map == branch_id) & mask, dtype=bool)


def _place_words_on_arrays(
    sdf: np.ndarray,
    mask: np.ndarray,
    words: list[tuple[str, int, int]],
    seed: int,
) -> tuple[list[PlacedWord], list[DroppedWord], int]:
    """Run the placement pipeline directly on numpy arrays.

    Mirrors the inner loop of placement.place_words() but accepts pre-computed
    sdf + mask directly (for multi-centric sub-SDF branches).

    Args:
        sdf: Float32 (H, W) SDF — positive inside.
        mask: Bool (H, W) mask.
        words: List of (text, h, w) tuples.
        seed: Determinism seed.

    Returns:
        Tuple of (placements, dropped, total_iters).
    """
    set_seed(seed)

    canvas_height, canvas_width = mask.shape
    centroid = _compute_centroid(mask)

    occupied: np.ndarray = np.zeros((canvas_height, canvas_width), dtype=bool)
    existing: np.ndarray = np.zeros((0, 4), dtype=np.int32)

    placements: list[PlacedWord] = []
    dropped: list[DroppedWord] = []
    total_iters = 0

    for word, h, w in words:
        if h <= 0 or w <= 0 or h > canvas_height or w > canvas_width:
            dropped.append(DroppedWord(word=word, reason=DropReason.TOO_LARGE_FOR_MASK))
            continue

        total_iters += MAX_ITERATIONS_PER_SEED

        found, reason = _place_one_word(
            h, w, canvas_height, canvas_width, sdf, occupied, existing, centroid
        )

        if found is not None:
            y_min, x_min, y_max, x_max = found
            bbox = AABB(
                y_min=int(y_min),
                x_min=int(x_min),
                y_max=int(y_max),
                x_max=int(x_max),
            )
            placements.append(
                PlacedWord(
                    word=word,
                    y=int((y_min + y_max) // 2),
                    x=int((x_min + x_max) // 2),
                    bbox=bbox,
                    size_pt=h,
                )
            )
            occupied[y_min:y_max, x_min:x_max] = True
            new_row = np.array([[y_min, x_min, y_max, x_max]], dtype=np.int32)
            existing = np.vstack([existing, new_row])
        else:
            dropped.append(DroppedWord(word=word, reason=reason))

    return placements, dropped, total_iters


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def place_words_multi_centric(
    sdf: np.ndarray,
    mask: np.ndarray,
    words: list[tuple[str, int, int]],
    seed: int = 0,
    mat_min_branch_radius: float = 3.0,
) -> MultiCentricResult:
    """Place words using multi-centric branch-partitioned placement (D-12/D-13/D-14).

    Partitions words proportional to MAT branch SDF volume, creates per-branch
    sub-SDFs, and runs the existing placement pipeline per branch.

    Args:
        sdf: Float32 (H, W) signed distance field, positive inside.
        mask: Bool (H, W) silhouette mask (True = inside).
        words: List of (text, h, w) tuples — already sorted descending by weight.
        seed: Determinism seed. Passed through to set_seed() at entry.
        mat_min_branch_radius: Minimum inscribed-circle radius for MAT branch
            inclusion. Branches below this threshold are pruned as noise.

    Returns:
        MultiCentricResult with merged placements, dropped words, aggregate
        stats, branch_count, and words_per_branch tuple.
    """
    set_seed(seed)
    t_start = time.perf_counter()

    log = logger.bind(
        geometry_phase="multi_centric",
        seed=seed,
        total_words=len(words),
    )
    log.info("multi_centric_start")

    # Step 1: Extract MAT
    mat = get_or_build_mat(sdf, min_branch_radius=mat_min_branch_radius)
    n_branches = len(mat.branches)

    log = log.bind(geometry_n_branches=n_branches)

    # Step 2: D-14 fallback — single branch
    if n_branches <= 1:
        log.info("multi_centric_fallback_single_branch")

        # Run single-branch placement
        if n_branches == 0 or not mask.any():
            # Degenerate: drop all words
            dropped_all = [
                DroppedWord(word=w, reason=DropReason.NO_FEASIBLE_ANCHOR) for w, h, ww in words
            ]
            wall_ms = (time.perf_counter() - t_start) * 1000.0
            stats = PlacementStats(
                total_words=len(words),
                placed=0,
                dropped=len(words),
                total_iterations=0,
                wall_clock_ms=wall_ms,
            )
            return MultiCentricResult(
                placements=[],
                dropped_words=dropped_all,
                stats=stats,
                branch_count=n_branches,
                words_per_branch=tuple([len(words)] if n_branches == 1 else []),
            )

        placements, dropped, total_iters = _place_words_on_arrays(sdf, mask, words, seed)

        wall_ms = (time.perf_counter() - t_start) * 1000.0
        stats = PlacementStats(
            total_words=len(words),
            placed=len(placements),
            dropped=len(dropped),
            total_iterations=total_iters,
            wall_clock_ms=wall_ms,
        )

        log.info(
            "multi_centric_done",
            placed=len(placements),
            dropped=len(dropped),
            wall_ms=round(wall_ms, 1),
        )

        return MultiCentricResult(
            placements=placements,
            dropped_words=dropped,
            stats=stats,
            branch_count=1,
            words_per_branch=(len(words),),
        )

    # Step 3: Assign words to branches (D-13)
    sorted_branches = sorted(mat.branches, key=lambda b: b.branch_id)
    assignment = _assign_words_to_branches(words, sorted_branches)

    words_per_branch_list: list[int] = [len(a) for a in assignment]

    log = log.bind(geometry_words_per_branch=words_per_branch_list)
    log.info("multi_centric_branch_assignment")

    # Step 4: Place per branch
    all_placements: list[PlacedWord] = []
    all_dropped: list[DroppedWord] = []
    total_iters = 0

    for branch, branch_words in zip(sorted_branches, assignment, strict=True):
        bid = branch.branch_id
        branch_log = log.bind(geometry_branch_id=bid, geometry_branch_words=len(branch_words))

        # Build sub-SDF and sub-mask (D-12)
        sub_sdf = _build_sub_sdf(sdf, mat.branch_map, bid)
        sub_mask = _build_sub_mask(mat.branch_map, mask, bid)

        # T-07-04-03: Empty sub_mask guard
        if not sub_mask.any():
            branch_log.warning(
                "multi_centric_empty_sub_mask",
                geometry_branch_id=bid,
            )
            # Drop all words assigned to this branch
            for w, _h, _ww in branch_words:
                all_dropped.append(DroppedWord(word=w, reason=DropReason.NO_FEASIBLE_ANCHOR))
            continue

        if len(branch_words) == 0:
            branch_log.warning(
                "multi_centric_branch_no_words",
                geometry_branch_id=bid,
            )
            continue

        # Run placement on sub-SDF
        b_placed, b_dropped, b_iters = _place_words_on_arrays(sub_sdf, sub_mask, branch_words, seed)

        if len(b_placed) == 0 and len(branch_words) > 0:
            branch_log.warning(
                "multi_centric_branch_placed_zero",
                geometry_branch_id=bid,
            )

        all_placements.extend(b_placed)
        all_dropped.extend(b_dropped)
        total_iters += b_iters

    wall_ms = (time.perf_counter() - t_start) * 1000.0
    stats = PlacementStats(
        total_words=len(words),
        placed=len(all_placements),
        dropped=len(all_dropped),
        total_iterations=total_iters,
        wall_clock_ms=wall_ms,
    )

    log.info(
        "multi_centric_done",
        placed=len(all_placements),
        dropped=len(all_dropped),
        wall_ms=round(wall_ms, 1),
    )

    return MultiCentricResult(
        placements=all_placements,
        dropped_words=all_dropped,
        stats=stats,
        branch_count=n_branches,
        words_per_branch=tuple(words_per_branch_list),
    )

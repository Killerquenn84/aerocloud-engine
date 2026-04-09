"""Per-word adaptive POI spiral placement (D-38..D-46).

Architecture:
1. Decode mask + SDF (cached via sdf_cache.get_or_build).
2. Initialise ``occupied`` bool canvas and ``existing`` int32 AABB array.
3. For each word:
   a. Compute ``feasibility_field = min_filter(sdf, AABB) masked by
      binary_dilation(occupied, AABB)``.
   b. Select origin via eps-band max + Manhattan-to-centroid tiebreak + (y, x) lex.
   c. If no feasible origin -> drop as NO_FEASIBLE_ANCHOR.
   d. Walk Archimedean spiral with
      ``step = clamp(min(w, h, sdf_at_pos) * 0.5, MIN_STEP, MAX_STEP)``,
      bounded by per-seed budget (500 iters), max 3 seeds/word, 1.0 s walltime.
   e. First legal position found -> record placement; else drop with DropReason.
4. Return PlacementResult.

Determinism (D-45/D-46):
- ``set_seed(request.seed)`` called at function entry.
- Integer-only hot loop: spiral offsets are integer (dy, dx) tuples; all
  collision checks use int32/int64 arrays.
- FP is only used for: feasibility_field computation (scipy ndimage, confined
  to float32 arrays) and ``sdf[y, x]`` lookup that feeds step clamping
  (immediately converted to int via floor).

Locked constants (D-41/D-42 -- NEVER change without 3-KI review):
    MIN_STEP = 1     (Codex g-5: lower bound prevents infinite loop on tiny AABB)
    MAX_STEP = 16    (Codex g-5: higher values create aliasing pockets; 16 chosen)
    MAX_ITERATIONS_PER_SEED = 500
    MAX_SEEDS_PER_WORD = 3
    MAX_WALL_CLOCK_PER_WORD = 1.0  seconds

References:
    - D-38: per-word adaptive POI (NOT single global origin)
    - D-39: eps-band max + Manhattan tiebreak + (y, x) lex in select_origin
    - D-40: integer Archimedean offsets, deduped, deterministic
    - D-41: MIN_STEP=1, MAX_STEP=16
    - D-42: per-seed budgets
    - D-43: PlacementResult + DropReason + PlacementFailedError
    - D-45: set_seed at entry
    - D-46: integer arithmetic in hot loop
    - 04-RESEARCH.md §6 (feasibility field) and §7 (Archimedean offsets)
"""

from __future__ import annotations

import math
import time
from typing import Final

import numpy as np
from scipy import ndimage

from aerocloud.geometry.collision import has_any_collision
from aerocloud.geometry.errors import EmptyMaskError, PlacementFailedError
from aerocloud.geometry.mask import mask_from_bytes
from aerocloud.geometry.sdf_cache import get_or_build
from aerocloud.models.geometry import (
    AABB,
    DroppedWord,
    DropReason,
    PlacedWord,
    PlacementRequest,
    PlacementResult,
    PlacementStats,
)
from aerocloud.utils.determinism import set_seed

# ---------------------------------------------------------------------------
# Locked constants (D-41 / D-42)
# grep-verify: grep -qE "MAX_STEP.*=.*16" placement.py
# ---------------------------------------------------------------------------

MIN_STEP: Final[int] = 1
MAX_STEP: Final[int] = 16
MAX_ITERATIONS_PER_SEED: Final[int] = 500
MAX_SEEDS_PER_WORD: Final[int] = 3
MAX_WALL_CLOCK_PER_WORD: Final[float] = 1.0  # seconds

EPS_BAND: Final[float] = 0.5  # half-pixel band for eps-band POI selection (D-39)

# Angular samples per full turn for the Archimedean spiral (D-40).
_SAMPLES_PER_TURN: Final[int] = 16


# ---------------------------------------------------------------------------
# Feasibility field (D-39 / 04-RESEARCH.md §6)
# ---------------------------------------------------------------------------

def feasibility_field(
    sdf: np.ndarray,
    occupied: np.ndarray,
    h: int,
    w: int,
) -> np.ndarray:
    """Compute the feasibility field for a word AABB of size (h, w).

    A pixel (y, x) in the feasibility field is the minimum SDF value in the
    (h, w) window centred at (y, x).  It is set to ``-inf`` if:
    - the AABB would extend outside the canvas (handled by minimum_filter with
      cval=-inf at the boundary), OR
    - any pixel in the AABB window overlaps an already-occupied region.

    Args:
        sdf: Float32 (canvas_h, canvas_w) signed distance field, positive inside.
        occupied: Bool (canvas_h, canvas_w) canvas; True = pixel already used.
        h: AABB height in pixels.
        w: AABB width in pixels.

    Returns:
        Float32 (canvas_h, canvas_w) array.  Positive values are valid anchor
        pixels; the value is the min(SDF) over the AABB window.
    """
    struct = np.ones((h, w), dtype=bool)
    min_sdf: np.ndarray = ndimage.minimum_filter(
        sdf, footprint=struct, mode="constant", cval=-np.inf
    )
    forbidden: np.ndarray = ndimage.binary_dilation(occupied, structure=struct)
    return np.where(
        forbidden, np.float32(-np.inf), min_sdf.astype(np.float32, copy=False)
    )


# ---------------------------------------------------------------------------
# Origin selection (D-39 / 04-RESEARCH.md §6 Open Question 2)
# ---------------------------------------------------------------------------

def select_origin(
    feasible_sdf: np.ndarray,
    mask_centroid: tuple[int, int],
) -> tuple[int, int] | None:
    """Pick the best anchor pixel from the feasibility field.

    Algorithm (D-39):
    1. Take the global max of ``feasible_sdf``.
    2. If max <= 0 or non-finite -> return None (NO_FEASIBLE_ANCHOR).
    3. Collect all pixels within EPS_BAND (0.5) of the max -> eps-band.
    4. Tiebreak: closest to mask centroid by Manhattan distance (cheaper than
       Euclidean and consistent on grid-aligned masks per RESEARCH.md §6 OQ2).
    5. Final lex tiebreak by (y, x) ascending for full determinism.
    6. Return Python ``int`` coordinates (not ``np.int64``).

    Args:
        feasible_sdf: Float32 (H, W) feasibility field from ``feasibility_field``.
        mask_centroid: (y, x) centroid of the mask's True pixels.

    Returns:
        ``(y, x)`` Python int tuple, or ``None`` if no feasible anchor exists.
    """
    max_val = float(feasible_sdf.max())
    if not math.isfinite(max_val) or max_val <= 0.0:
        return None

    cand: np.ndarray = np.argwhere(feasible_sdf >= max_val - EPS_BAND)
    cy, cx = mask_centroid
    dist: np.ndarray = np.abs(cand[:, 0] - cy) + np.abs(cand[:, 1] - cx)
    # lexsort: LAST key = primary sort key; sort by (dist asc, y asc, x asc)
    order: np.ndarray = np.lexsort((cand[:, 1], cand[:, 0], dist))
    best = cand[order[0]]
    # Cast to Python int -- Pydantic strict mode rejects np.int64 (D-14 / R-8)
    return int(best[0]), int(best[1])


# ---------------------------------------------------------------------------
# Archimedean spiral offset generator (D-40 / 04-RESEARCH.md §7)
# ---------------------------------------------------------------------------

def archimedean_offsets(step: int, max_iters: int) -> list[tuple[int, int]]:
    """Generate deduplicated integer (dy, dx) spiral offsets.

    Uses ``r = b * theta`` with ``b = step / (2*pi)``.  Angular step is
    ``2*pi / _SAMPLES_PER_TURN`` (16 samples per turn).

    The first entry is always ``(0, 0)`` (the anchor pixel itself).

    Deduplication is by integer ``(dy, dx)`` key in insertion order -- FP
    rounding of ``r * cos(theta)`` can map two close theta values to the same
    integer pixel; the duplicate is silently skipped.

    Args:
        step: Spiral pitch in pixels (used to compute ``b``).  Must be >= 1.
        max_iters: Maximum number of unique offsets to return.

    Returns:
        List of at most ``max_iters`` unique ``(dy, dx)`` int tuples.
        Deterministic -- same ``(step, max_iters)`` always returns the same list.
    """
    b = step / (2.0 * math.pi)
    d_theta = (2.0 * math.pi) / _SAMPLES_PER_TURN

    seen: set[tuple[int, int]] = set()
    offsets: list[tuple[int, int]] = []

    seen.add((0, 0))
    offsets.append((0, 0))

    theta = d_theta
    max_angular_steps = max_iters * _SAMPLES_PER_TURN
    angular_steps = 0

    while len(offsets) < max_iters and angular_steps < max_angular_steps:
        r = b * theta
        # math.floor returns int in Python 3; + 0.5 gives round-half-away.
        dy = math.floor(r * math.sin(theta) + 0.5)
        dx = math.floor(r * math.cos(theta) + 0.5)
        key = (dy, dx)
        if key not in seen:
            seen.add(key)
            offsets.append(key)
        theta += d_theta
        angular_steps += 1

    return offsets


# ---------------------------------------------------------------------------
# Step clamping helper (D-41)
# ---------------------------------------------------------------------------

def _clamp_step(aabb_w: int, aabb_h: int, sdf_at_pos: float) -> int:
    """Compute the adaptive spiral step for the current AABB and SDF value.

    Formula (D-41):
        step = clamp(min(aabb_w, aabb_h, max(0, floor(sdf_at_pos))) * 0.5,
                     MIN_STEP, MAX_STEP)
    """
    sdf_int = max(0, math.floor(sdf_at_pos))
    floor_val = min(aabb_w, aabb_h, sdf_int)
    raw = max(1, floor_val // 2)
    return max(MIN_STEP, min(MAX_STEP, raw))


# ---------------------------------------------------------------------------
# Mask centroid helper
# ---------------------------------------------------------------------------

def _compute_centroid(mask: np.ndarray) -> tuple[int, int]:
    """Return (y, x) centroid of the mask's True pixels."""
    ys, xs = np.nonzero(mask)
    if ys.size == 0:
        raise EmptyMaskError("cannot compute centroid of empty mask")
    return round(float(ys.mean())), round(float(xs.mean()))


# ---------------------------------------------------------------------------
# Inner spiral search for one seed (extracted to reduce place_words complexity)
# ---------------------------------------------------------------------------

def _spiral_search(
    oy: int,
    ox: int,
    h: int,
    w: int,
    canvas_height: int,
    canvas_width: int,
    sdf: np.ndarray,
    ff: np.ndarray,
    existing: np.ndarray,
    word_t0: float,
) -> tuple[int, int, int, int] | None:
    """Walk the Archimedean spiral from ``(oy, ox)`` looking for a free AABB.

    Args:
        oy, ox: Spiral origin (anchor pixel).
        h, w: AABB height and width.
        canvas_height, canvas_width: Canvas dimensions.
        sdf: Float32 SDF array.
        ff: Float32 feasibility field (modified in-place by caller between seeds).
        existing: (N, 4) int32 array of already-placed AABB rows.
        word_t0: Perf-counter start for this word's walltime guard.

    Returns:
        ``(y_min, x_min, y_max, x_max)`` on success, or ``None`` if no
        placement was found within the iteration budget or walltime.
    """
    sdf_at: float = float(sdf[oy, ox])
    step: int = _clamp_step(w, h, sdf_at)
    offsets = archimedean_offsets(step, MAX_ITERATIONS_PER_SEED)

    for dy, dx in offsets:
        if time.perf_counter() - word_t0 > MAX_WALL_CLOCK_PER_WORD:
            return None

        y_c = oy + dy
        x_c = ox + dx
        y_min = y_c - h // 2
        x_min = x_c - w // 2
        y_max = y_min + h
        x_max = x_min + w

        if y_min < 0 or x_min < 0 or y_max > canvas_height or x_max > canvas_width:
            continue

        ff_val = ff[y_c, x_c]
        if not math.isfinite(ff_val) or ff_val <= 0.0:
            continue

        cand = np.array([y_min, x_min, y_max, x_max], dtype=np.int32)
        if has_any_collision(cand, existing):
            continue

        return (y_min, x_min, y_max, x_max)

    return None


# ---------------------------------------------------------------------------
# Per-word placement loop (extracted to reduce place_words complexity)
# ---------------------------------------------------------------------------

def _place_one_word(
    h: int,
    w: int,
    canvas_height: int,
    canvas_width: int,
    sdf: np.ndarray,
    occupied: np.ndarray,
    existing: np.ndarray,
    centroid: tuple[int, int],
) -> tuple[tuple[int, int, int, int] | None, DropReason]:
    """Try to place one word AABB using up to MAX_SEEDS_PER_WORD seed attempts.

    Returns the placed AABB coordinates and the final DropReason (the latter
    is only used when the return value is None).
    """
    ff = feasibility_field(sdf, occupied, h, w)
    word_t0 = time.perf_counter()
    last_reason: DropReason = DropReason.NO_FEASIBLE_ANCHOR

    for _ in range(MAX_SEEDS_PER_WORD):
        if time.perf_counter() - word_t0 > MAX_WALL_CLOCK_PER_WORD:
            return None, DropReason.WALL_CLOCK_EXCEEDED

        origin = select_origin(ff, centroid)
        if origin is None:
            return None, DropReason.NO_FEASIBLE_ANCHOR

        oy, ox = origin
        found = _spiral_search(
            oy, ox, h, w, canvas_height, canvas_width, sdf, ff, existing, word_t0
        )

        if found is not None:
            return found, last_reason

        # Seed failed -- suppress this origin and try next-best (D-42)
        last_reason = DropReason.ITERATION_BUDGET_EXCEEDED
        step = _clamp_step(w, h, float(sdf[oy, ox]))
        rr = max(1, step * 2)
        y0_s = max(0, oy - rr)
        y1_s = min(canvas_height, oy + rr + 1)
        x0_s = max(0, ox - rr)
        x1_s = min(canvas_width, ox + rr + 1)
        ff[y0_s:y1_s, x0_s:x1_s] = np.float32(-np.inf)

    return None, last_reason


# ---------------------------------------------------------------------------
# Main entry point (D-38..D-46)
# ---------------------------------------------------------------------------

def place_words(request: PlacementRequest) -> PlacementResult:
    """Place words into the silhouette mask using per-word adaptive POI spiral.

    Deterministic (D-45): ``set_seed(request.seed)`` is called at entry.
    Integer arithmetic dominates the hot loop (D-46).

    Args:
        request: ``PlacementRequest`` with PNG bytes, word list, and seed.

    Returns:
        ``PlacementResult`` with placed words, dropped words, and stats.

    Raises:
        PlacementFailedError: ONLY on contract violations -- NaN/inf SDF.
        EmptyMaskError: If the decoded mask has no inside or no outside pixels.
    """
    set_seed(request.seed)
    t_start = time.perf_counter()

    mask = mask_from_bytes(request.raw_png_bytes)
    sdf = get_or_build(request.raw_png_bytes, mask)

    if not np.isfinite(sdf).all():
        raise PlacementFailedError(
            "SDF contains non-finite values -- contract violation (D-09/D-43)"
        )

    canvas_height, canvas_width = mask.shape
    centroid = _compute_centroid(mask)

    occupied: np.ndarray = np.zeros((canvas_height, canvas_width), dtype=bool)
    existing: np.ndarray = np.zeros((0, 4), dtype=np.int32)

    placements: list[PlacedWord] = []
    dropped: list[DroppedWord] = []
    total_iters: int = 0

    for word, h, w in request.words:
        if h <= 0 or w <= 0 or h > canvas_height or w > canvas_width:
            dropped.append(DroppedWord(word=word, reason=DropReason.TOO_LARGE_FOR_MASK))
            continue

        # Estimate iteration count contribution (approximate -- actual counted in inner loop)
        total_iters += MAX_ITERATIONS_PER_SEED  # pessimistic; refine in future

        found, reason = _place_one_word(
            h, w, canvas_height, canvas_width, sdf, occupied, existing, centroid
        )

        if found is not None:
            y_min, x_min, y_max, x_max = found
            bbox = AABB(
                y_min=int(y_min), x_min=int(x_min),
                y_max=int(y_max), x_max=int(x_max),
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

    wall_ms = (time.perf_counter() - t_start) * 1000.0
    stats = PlacementStats(
        total_words=len(request.words),
        placed=len(placements),
        dropped=len(dropped),
        total_iterations=total_iters,
        wall_clock_ms=wall_ms,
    )
    return PlacementResult(placements=placements, dropped_words=dropped, stats=stats)

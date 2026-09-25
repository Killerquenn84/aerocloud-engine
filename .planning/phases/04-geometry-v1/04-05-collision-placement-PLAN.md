---
phase: 04-geometry-v1
plan: 05
plan_id: 04-05-collision-placement
type: execute
wave: 3
depends_on: [04-03-sdf-cache, 04-04-glyph-golden]
autonomous: true
requirements: [GEO-05, GEO-06]
files_modified:
  - packages/engine/src/aerocloud/geometry/collision.py
  - packages/engine/src/aerocloud/geometry/placement.py
  - packages/engine/src/aerocloud/models/geometry.py
  - packages/engine/tests/geometry/unit/test_collision.py
  - packages/engine/tests/geometry/unit/test_placement.py
  - packages/engine/tests/geometry/integration/test_pipeline.py

must_haves:
  truths:
    - "aabb_overlap(new, existing) returns bool[N] via integer-only vectorized numpy"
    - "Per-word adaptive POI recomputes feasibility field for EACH word (not single global origin)"
    - "select_origin() uses eps-band (0.5) of feasible_sdf max + Manhattan tiebreak + (y, x) lex"
    - "archimedean_offsets() generates deduplicated integer (dy, dx) with lex tiebreak (radius_bin, theta_bin, y, x)"
    - "step = clamp(min(aabb_w, aabb_h, max(0, sdf_at_pos)) * 0.5, 1, 16)  — MIN_STEP=1, MAX_STEP=16"
    - "Per-seed budget: max_iterations_per_seed=500, max_seeds_per_word=3, max_wall_clock_per_word=1.0s"
    - "PlacementResult contains placements + dropped_words + stats; DropReason enum with 4 values"
    - "PlacementFailedError raised ONLY for contract violations (NaN SDF, dim mismatch, negative budgets)"
    - "Unplaceable word goes into dropped_words — never an exception"
    - "Integration test: circle, square, C-shape, crescent, empty mask all produce expected PlacementResult"
  artifacts:
    - path: "packages/engine/src/aerocloud/geometry/collision.py"
      provides: "aabb_overlap, has_any_collision (vectorized numpy)"
    - path: "packages/engine/src/aerocloud/geometry/placement.py"
      provides: "place_words, select_origin, archimedean_offsets, feasibility_field"
    - path: "packages/engine/src/aerocloud/models/geometry.py"
      provides: "PlacedWord, DroppedWord, DropReason, PlacementResult, PlacementStats, PlacementRequest"
  key_links:
    - from: "geometry/placement.py"
      to: "geometry/sdf_cache.py"
      via: "get_or_build(raw_bytes, mask)"
      pattern: "get_or_build"
    - from: "geometry/placement.py"
      to: "geometry/collision.py"
      via: "aabb_overlap integer collision"
      pattern: "aabb_overlap"
    - from: "geometry/placement.py"
      to: "scipy.ndimage.binary_dilation + minimum_filter"
      via: "feasibility_field construction"
      pattern: "binary_dilation|minimum_filter"
    - from: "geometry/placement.py"
      to: "aerocloud.utils.determinism.set_seed"
      via: "determinism entry at place_words"
      pattern: "set_seed"
---

<objective>
Wave 3: Ship AABB collision + the per-word adaptive POI spiral placement.
This is the most algorithmically sensitive wave — Codex g-5 BLOCKED the naive
single-origin design and the redesign in D-38..D-44 is what must be
implemented here. Every numeric constant (MIN_STEP, MAX_STEP, budget values,
eps band) is locked in CONTEXT.md.

Purpose: GEO-05 (AABB collision) + GEO-06 (spiral placement). Delivers the
end-to-end "PNG bytes → PlacementResult" integration path the rest of the
phase builds observability on top of.

Output: collision.py + placement.py + 6 new Pydantic models +
unit/integration tests including circle/square/C/crescent end-to-end.
</objective>

<execution_context>
@/var/www/wordcloud-app-v2/server/aerocloud-engine/.claude/get-shit-done/workflows/execute-plan.md
@/var/www/wordcloud-app-v2/server/aerocloud-engine/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/04-geometry-v1/04-CONTEXT.md
@.planning/phases/04-geometry-v1/04-RESEARCH.md
@.planning/phases/04-geometry-v1/3ki-g3-g4-g5/codex-g5.md
@packages/engine/src/aerocloud/geometry/sdf.py
@packages/engine/src/aerocloud/geometry/sdf_cache.py
@packages/engine/src/aerocloud/geometry/mask.py
@packages/engine/src/aerocloud/geometry/glyph.py
@packages/engine/src/aerocloud/models/geometry.py
@packages/engine/src/aerocloud/utils/determinism.py
</context>

<interfaces>
From 04-RESEARCH.md §5, §6, §7 (verbatim reference implementations):

```python
# geometry/collision.py
def aabb_overlap(new: np.ndarray, existing: np.ndarray) -> np.ndarray: ...  # bool[N]
def has_any_collision(new: np.ndarray, existing: np.ndarray) -> bool: ...

# geometry/placement.py
def feasibility_field(sdf, occupied, h, w) -> np.ndarray: ...
def select_origin(feasible_sdf, mask_centroid) -> tuple[int, int] | None: ...
def archimedean_offsets(step: int, max_iters: int) -> list[tuple[int, int]]: ...
def place_words(request: PlacementRequest) -> PlacementResult: ...

# models/geometry.py ADDITIONS
class DropReason(StrEnum):
    NO_FEASIBLE_ANCHOR = "no_feasible_anchor"
    ITERATION_BUDGET_EXCEEDED = "iteration_budget_exceeded"
    TOO_LARGE_FOR_MASK = "too_large_for_mask"
    WALL_CLOCK_EXCEEDED = "wall_clock_exceeded"

class PlacedWord(AeroCloudBase):
    word: str
    y: int
    x: int
    bbox: AABB
    size_pt: int

class DroppedWord(AeroCloudBase):
    word: str
    reason: DropReason
    details: str | None = None

class PlacementStats(AeroCloudBase):
    total_words: int
    placed: int
    dropped: int
    total_iterations: int
    wall_clock_ms: float

class PlacementResult(AeroCloudBase):
    placements: list[PlacedWord]
    dropped_words: list[DroppedWord]
    stats: PlacementStats

class PlacementRequest(AeroCloudBase):
    raw_png_bytes: bytes
    words: list[tuple[str, int, int]]  # (text, aabb_h, aabb_w) — glyph sizing happens upstream
    seed: int = 0
```
</interfaces>

<tasks>

<task type="auto" id="04-05-T1" tdd="true">
  <name>Task 1: collision.py — vectorized integer AABB overlap (D-36 aabb_overlap signature)</name>
  <files>
    packages/engine/src/aerocloud/geometry/collision.py
    packages/engine/tests/geometry/unit/test_collision.py
  </files>
  <read_first>
    - .planning/phases/04-geometry-v1/04-CONTEXT.md (D-35..D-37)
    - .planning/phases/04-geometry-v1/04-RESEARCH.md §5 (verbatim code)
    - packages/engine/src/aerocloud/models/geometry.py (AABB definition from Wave 2b)
  </read_first>
  <behavior>
    - Test CL1 (RED): Empty existing array → returns `bool[0]`.
    - Test CL2 (RED): Non-overlapping boxes → all False.
    - Test CL3 (RED): Touching boxes (half-open) → all False (adjacency ≠ overlap).
    - Test CL4 (RED): Fully-contained box → True for that row.
    - Test CL5 (RED): Partial overlap on Y only → False (needs both axes).
    - Test CL6 (RED): Partial overlap on X only → False.
    - Test CL7 (RED): Mix of 100 random boxes → `has_any_collision` returns True iff at least one row is True.
    - Test CL8 (RED): dtype is int (accepts int32 and int64 input).
  </behavior>
  <action>
**Step 1 — RED: Write `tests/geometry/unit/test_collision.py`** with 8 tests. Use `np.array([[y0,x0,y1,x1]], dtype=np.int32)` fixtures.

**Step 2 — GREEN: Implement `packages/engine/src/aerocloud/geometry/collision.py`** exactly per 04-RESEARCH.md §5:

```python
"""Vectorized integer AABB collision (D-35..D-37).

Axis-aligned only. Half-open intervals: [y_min, y_max) × [x_min, x_max).
Integer arithmetic only — no FP comparisons, no rotation (→ Phase 7).
"""
from __future__ import annotations

import numpy as np


def aabb_overlap(new: np.ndarray, existing: np.ndarray) -> np.ndarray:
    """Return bool[N] mask of which existing AABBs overlap `new`.

    Args:
        new: shape (4,) int → (y_min, x_min, y_max, x_max), half-open.
        existing: shape (N, 4) int.

    Returns:
        Boolean ndarray of length N.
    """
    if existing.shape[0] == 0:
        return np.zeros(0, dtype=bool)
    ny0, nx0, ny1, nx1 = new.astype(np.int64, copy=False)
    ey0 = existing[:, 0].astype(np.int64, copy=False)
    ex0 = existing[:, 1].astype(np.int64, copy=False)
    ey1 = existing[:, 2].astype(np.int64, copy=False)
    ex1 = existing[:, 3].astype(np.int64, copy=False)
    overlap_y = (ey0 < ny1) & (ny0 < ey1)
    overlap_x = (ex0 < nx1) & (nx0 < ex1)
    return np.asarray(overlap_y & overlap_x, dtype=bool)


def has_any_collision(new: np.ndarray, existing: np.ndarray) -> bool:
    """Convenience boolean reducer."""
    return bool(aabb_overlap(new, existing).any())
```

**Step 3 — GREEN: Run tests until green.**

**Step 4 — REFACTOR:** mypy --strict + ruff clean.
  </action>
  <verify>
    <automated>cd packages/engine && uv run pytest tests/geometry/unit/test_collision.py -x -q && uv run mypy --strict src/aerocloud/geometry/collision.py && uv run ruff check src/aerocloud/geometry/collision.py tests/geometry/unit/test_collision.py</automated>
  </verify>
  <acceptance_criteria>
    - `collision.py` defines `aabb_overlap` and `has_any_collision`
    - Integer-only arithmetic (no `float`, `np.float*` in source — grep)
    - Half-open semantics verified (adjacent boxes don't overlap)
    - All 8 tests pass
    - mypy --strict clean
  </acceptance_criteria>
  <done>Stage-1 collision primitives green</done>
</task>

<task type="auto" id="04-05-T2" tdd="true">
  <name>Task 2: placement.py — adaptive POI + integer spiral + PlacementResult contract</name>
  <files>
    packages/engine/src/aerocloud/geometry/placement.py
    packages/engine/src/aerocloud/models/geometry.py  (extend)
    packages/engine/tests/geometry/unit/test_placement.py
  </files>
  <read_first>
    - .planning/phases/04-geometry-v1/04-CONTEXT.md (D-38..D-46 verbatim)
    - .planning/phases/04-geometry-v1/04-RESEARCH.md §6 + §7 + §Open Questions 2 (Manhattan tiebreak)
    - .planning/phases/04-geometry-v1/3ki-g3-g4-g5/codex-g5.md
    - packages/engine/src/aerocloud/geometry/sdf.py
    - packages/engine/src/aerocloud/geometry/collision.py
    - packages/engine/src/aerocloud/utils/determinism.py (set_seed)
  </read_first>
  <behavior>
    - Test PL1 (RED): `DropReason` enum has exactly 4 values: `NO_FEASIBLE_ANCHOR`, `ITERATION_BUDGET_EXCEEDED`, `TOO_LARGE_FOR_MASK`, `WALL_CLOCK_EXCEEDED`.
    - Test PL2 (RED): `PlacedWord`, `DroppedWord`, `PlacementStats`, `PlacementResult`, `PlacementRequest` Pydantic models round-trip via JSON.
    - Test PL3 (RED): `archimedean_offsets(step=4, max_iters=100)` returns ≤ 100 unique `(dy, dx)` int tuples, first entry is `(0, 0)`, and the sequence is deterministic (run twice → same list).
    - Test PL4 (RED): `archimedean_offsets` output contains no duplicates (set equality check).
    - Test PL5 (RED): `feasibility_field(sdf, occupied, h=4, w=6)` returns float32 (H, W) where pixels near the edge (AABB pokes outside) have -inf, and interior deep pixels have the min-SDF value.
    - Test PL6 (RED): `select_origin` on a circle feasibility field returns the center (tiebreak by centroid → center is the unique max).
    - Test PL7 (RED): `select_origin` returns `None` when all feasible_sdf ≤ 0 (word larger than remaining free space).
    - Test PL8 (RED): `place_words(PlacementRequest(raw_png_bytes=circle_mask_bytes, words=[('hello', 8, 40)], seed=42))` returns 1 placement inside the circle (validated via mask pixel check).
    - Test PL9 (RED): Word with AABB larger than the mask → dropped with reason `TOO_LARGE_FOR_MASK`.
    - Test PL10 (RED): 100 word stress on a small square → some placements, dropped words have `ITERATION_BUDGET_EXCEEDED` or `NO_FEASIBLE_ANCHOR` reasons, NO exceptions.
    - Test PL11 (RED): NaN injected into SDF via monkeypatch on `compute_sdf` → `PlacementFailedError` raised (contract violation).
    - Test PL12 (RED): Same `(raw_png_bytes, words, seed)` → byte-identical `PlacementResult.model_dump_json()` across 2 sequential runs (determinism sanity).
  </behavior>
  <action>
**Step 1 — Extend `models/geometry.py`** with the 6 new models per the interfaces block. Use `enum.StrEnum` (Python 3.11+) for `DropReason`. Write the Wave 2b `GlyphBBox` file + append:

```python
from enum import StrEnum

class DropReason(StrEnum):
    NO_FEASIBLE_ANCHOR = "no_feasible_anchor"
    ITERATION_BUDGET_EXCEEDED = "iteration_budget_exceeded"
    TOO_LARGE_FOR_MASK = "too_large_for_mask"
    WALL_CLOCK_EXCEEDED = "wall_clock_exceeded"


class PlacedWord(AeroCloudBase):
    word: str
    y: int = Field(ge=0)
    x: int = Field(ge=0)
    bbox: AABB
    size_pt: int = Field(gt=0)


class DroppedWord(AeroCloudBase):
    word: str
    reason: DropReason
    details: str | None = None


class PlacementStats(AeroCloudBase):
    total_words: int = Field(ge=0)
    placed: int = Field(ge=0)
    dropped: int = Field(ge=0)
    total_iterations: int = Field(ge=0)
    wall_clock_ms: float = Field(ge=0.0)


class PlacementResult(AeroCloudBase):
    placements: list[PlacedWord]
    dropped_words: list[DroppedWord]
    stats: PlacementStats


class PlacementRequest(AeroCloudBase):
    raw_png_bytes: bytes = Field(min_length=8)
    words: list[tuple[str, int, int]]  # (text, aabb_h, aabb_w)
    seed: int = 0
```

**Step 2 — RED: Write `tests/geometry/unit/test_placement.py`** with all 12 tests. Use the `circle_mask_bytes` / `square_mask_bytes` fixtures.

**Step 3 — GREEN: Implement `packages/engine/src/aerocloud/geometry/placement.py`** per 04-RESEARCH.md §6 + §7:

```python
"""Per-word adaptive POI spiral placement (D-38..D-46).

Architecture:
1. Decode mask + SDF (cached).
2. Initialize `occupied` bool canvas and `aabbs` int32 array.
3. For each word:
   a. Compute `feasibility_field = min_filter(sdf, AABB) masked by
      dilated(occupied, AABB)`.
   b. Select origin via eps-band max + Manhattan-to-centroid tiebreak + (y, x) lex.
   c. If no feasible origin → drop as NO_FEASIBLE_ANCHOR.
   d. Walk Archimedean spiral with `step = clamp(min(w, h, sdf_at_pos) * 0.5, 1, 16)`,
      bounded by per-seed budget (500 iters), max 3 seeds/word, 1.0s walltime.
   e. First legal position found → place; else drop with the right DropReason.
4. Return PlacementResult.

Determinism: integer-only hot loop, `set_seed(request.seed)` at entry,
`floor(x + 0.5)` rounding in spiral math (D-46).
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
    DropReason,
    DroppedWord,
    PlacedWord,
    PlacementRequest,
    PlacementResult,
    PlacementStats,
)
from aerocloud.utils.determinism import set_seed

MIN_STEP: Final[int] = 1   # D-41
MAX_STEP: Final[int] = 16  # D-41 (Codex g-5: MAX_STEP=32 aliased; pick 16)
MAX_ITERATIONS_PER_SEED: Final[int] = 500  # D-42
MAX_SEEDS_PER_WORD: Final[int] = 3          # D-42
MAX_WALL_CLOCK_PER_WORD: Final[float] = 1.0  # seconds, D-42
EPS_BAND: Final[float] = 0.5                 # D-39
SAMPLES_PER_TURN: Final[int] = 16


def feasibility_field(
    sdf: np.ndarray, occupied: np.ndarray, h: int, w: int
) -> np.ndarray:
    """Min-SDF over a centered (h, w) window, masked by dilated occupied."""
    struct = np.ones((h, w), dtype=bool)
    forbidden = ndimage.binary_dilation(occupied, structure=struct)
    min_sdf = ndimage.minimum_filter(
        sdf, footprint=struct, mode="constant", cval=-np.inf
    )
    return np.where(
        forbidden, np.float32(-np.inf), min_sdf.astype(np.float32, copy=False)
    )


def select_origin(
    feasible_sdf: np.ndarray, mask_centroid: tuple[int, int]
) -> tuple[int, int] | None:
    """Eps-band max with Manhattan tiebreak and (y, x) lex fallback (D-39)."""
    max_val = float(feasible_sdf.max())
    if not math.isfinite(max_val) or max_val <= 0.0:
        return None
    cand = np.argwhere(feasible_sdf >= max_val - EPS_BAND)
    cy, cx = mask_centroid
    dist = np.abs(cand[:, 0] - cy) + np.abs(cand[:, 1] - cx)
    order = np.lexsort((cand[:, 1], cand[:, 0], dist))
    y, x = cand[order[0]]
    return int(y), int(x)


def archimedean_offsets(step: int, max_iters: int) -> list[tuple[int, int]]:
    """Deterministic integer (dy, dx) offsets on r = (step/(2π))·θ (D-40)."""
    b = step / (2.0 * math.pi)
    seen: set[tuple[int, int]] = set()
    offsets: list[tuple[int, int]] = []
    dtheta = (2.0 * math.pi) / SAMPLES_PER_TURN
    theta = 0.0
    samples = 0
    # First candidate is always (0, 0) — the origin itself.
    seen.add((0, 0))
    offsets.append((0, 0))
    while len(offsets) < max_iters and samples < max_iters * 4:
        r = b * theta
        dy = int(math.floor(r * math.sin(theta) + 0.5))
        dx = int(math.floor(r * math.cos(theta) + 0.5))
        key = (dy, dx)
        if key not in seen:
            seen.add(key)
            offsets.append(key)
        theta += dtheta
        samples += 1
    return offsets


def _clamp_step(aabb_w: int, aabb_h: int, sdf_at_pos: float) -> int:
    floor_val = min(aabb_w, aabb_h, max(0, int(math.floor(sdf_at_pos))))
    raw = max(1, floor_val // 2)
    return max(MIN_STEP, min(MAX_STEP, raw))


def _compute_centroid(mask: np.ndarray) -> tuple[int, int]:
    ys, xs = np.nonzero(mask)
    if ys.size == 0:
        raise EmptyMaskError("cannot compute centroid of empty mask")
    return int(ys.mean()), int(xs.mean())


def place_words(request: PlacementRequest) -> PlacementResult:
    """Place words into the silhouette (D-38..D-46)."""
    set_seed(request.seed)
    t_start = time.perf_counter()

    mask = mask_from_bytes(request.raw_png_bytes)
    sdf = get_or_build(request.raw_png_bytes, mask)
    if not np.isfinite(sdf).all():
        raise PlacementFailedError("SDF contains non-finite values (contract violation)")

    H, W = mask.shape
    centroid = _compute_centroid(mask)

    occupied = np.zeros((H, W), dtype=bool)
    existing = np.zeros((0, 4), dtype=np.int32)

    placements: list[PlacedWord] = []
    dropped: list[DroppedWord] = []
    total_iters = 0

    for word, h, w in request.words:
        if h <= 0 or w <= 0 or h > H or w > W:
            dropped.append(DroppedWord(word=word, reason=DropReason.TOO_LARGE_FOR_MASK))
            continue

        ff = feasibility_field(sdf, occupied, h, w)
        placed = False
        word_t0 = time.perf_counter()
        last_reason = DropReason.NO_FEASIBLE_ANCHOR

        for seed_attempt in range(MAX_SEEDS_PER_WORD):
            if time.perf_counter() - word_t0 > MAX_WALL_CLOCK_PER_WORD:
                last_reason = DropReason.WALL_CLOCK_EXCEEDED
                break
            origin = select_origin(ff, centroid)
            if origin is None:
                last_reason = DropReason.NO_FEASIBLE_ANCHOR
                break
            oy, ox = origin

            sdf_at = float(sdf[oy, ox])
            step = _clamp_step(w, h, sdf_at)
            offsets = archimedean_offsets(step, MAX_ITERATIONS_PER_SEED)

            found = None
            for i, (dy, dx) in enumerate(offsets):
                total_iters += 1
                if time.perf_counter() - word_t0 > MAX_WALL_CLOCK_PER_WORD:
                    last_reason = DropReason.WALL_CLOCK_EXCEEDED
                    break
                y = oy + dy
                x = ox + dx
                y_min = y - h // 2
                x_min = x - w // 2
                y_max = y_min + h
                x_max = x_min + w
                if y_min < 0 or x_min < 0 or y_max > H or x_max > W:
                    continue
                if ff[y, x] <= 0 or not math.isfinite(ff[y, x]):
                    continue
                cand = np.array([y_min, x_min, y_max, x_max], dtype=np.int32)
                if has_any_collision(cand, existing):
                    continue
                found = (y_min, x_min, y_max, x_max)
                break

            if found is not None:
                y_min, x_min, y_max, x_max = found
                bbox = AABB(y_min=y_min, x_min=x_min, y_max=y_max, x_max=x_max)
                placements.append(
                    PlacedWord(word=word, y=int((y_min + y_max) // 2),
                               x=int((x_min + x_max) // 2), bbox=bbox, size_pt=h)
                )
                occupied[y_min:y_max, x_min:x_max] = True
                existing = np.vstack([existing, cand[None, :]])
                placed = True
                break
            else:
                last_reason = DropReason.ITERATION_BUDGET_EXCEEDED
                # Suppress this origin by writing -inf in a local neighborhood,
                # then retry with next-best origin.
                rr = max(1, step * 2)
                y0 = max(0, oy - rr); y1 = min(H, oy + rr + 1)
                x0 = max(0, ox - rr); x1 = min(W, ox + rr + 1)
                ff[y0:y1, x0:x1] = np.float32(-np.inf)

        if not placed:
            dropped.append(DroppedWord(word=word, reason=last_reason))

    wall = (time.perf_counter() - t_start) * 1000.0
    stats = PlacementStats(
        total_words=len(request.words),
        placed=len(placements),
        dropped=len(dropped),
        total_iterations=total_iters,
        wall_clock_ms=wall,
    )
    return PlacementResult(placements=placements, dropped_words=dropped, stats=stats)
```

**Step 4 — GREEN: Run tests until green.** Iteration quirks: PL8 circle test — use a single word with AABB fitting well inside the circle. PL12 determinism test — compare `result.model_dump_json(exclude={'stats': {'wall_clock_ms'}})` since walltime varies.

**Step 5 — REFACTOR:** mypy --strict + ruff clean.
  </action>
  <verify>
    <automated>cd packages/engine && uv run pytest tests/geometry/unit/test_placement.py -x -q && uv run mypy --strict src/aerocloud/geometry/placement.py src/aerocloud/models/geometry.py && uv run ruff check src/aerocloud/geometry/placement.py src/aerocloud/models/geometry.py tests/geometry/unit/test_placement.py    <automated>cd packages/engine && uv run pytest tests/geometry/unit/test_placement.py -x -q && uv run mypy --strict src/aerocloud/geometry/placement.py src/aerocloud/models/geometry.py && uv run ruff check src/aerocloud/geometry/placement.py src/aerocloud/models/geometry.py tests/geometry/unit/test_placement.py</automated>
  </verify>
  <acceptance_criteria>
    - `placement.py` defines `MIN_STEP=1`, `MAX_STEP=16`, `MAX_ITERATIONS_PER_SEED=500`, `MAX_SEEDS_PER_WORD=3`, `MAX_WALL_CLOCK_PER_WORD=1.0` as module constants
    - `archimedean_offsets` is deterministic and deduplicated
    - `select_origin` uses Manhattan tiebreak (per RESEARCH Open Question 2)
    - `place_words` calls `set_seed(request.seed)` at entry
    - `PlacementFailedError` raised ONLY on non-finite SDF, never on ordinary drop
    - All 12 unit tests pass
    - `DropReason` enum has exactly 4 values
    - mypy --strict clean
    - ruff clean
  </acceptance_criteria>
  <done>Placement engine green with structured fail-fast contract</done>
</task>

<task type="auto" id="04-05-T3">
  <name>Task 3: Integration test — end-to-end PNG → PlacementResult on 4 fixtures + empty-mask path</name>
  <files>
    packages/engine/tests/geometry/integration/test_pipeline.py
  </files>
  <read_first>
    - packages/engine/src/aerocloud/geometry/placement.py (from Task 2)
    - packages/engine/src/aerocloud/geometry/mask.py
    - packages/engine/src/aerocloud/geometry/sdf_cache.py
    - packages/engine/tests/conftest.py (4 shape fixtures)
  </read_first>
  <action>
Write `tests/geometry/integration/test_pipeline.py` with 5 end-to-end tests:

```python
"""End-to-end integration: PNG bytes → PlacementResult.

Exercises mask → sdf_cache → placement against all four conftest shape
fixtures + the empty-mask error path.
"""
from __future__ import annotations

import io
import numpy as np
import pytest
from PIL import Image

from aerocloud.geometry.errors import EmptyMaskError
from aerocloud.geometry.placement import place_words
from aerocloud.geometry.sdf_cache import clear_cache
from aerocloud.models.geometry import DropReason, PlacementRequest


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_cache()
    yield
    clear_cache()


def test_circle_places_ten_words(circle_mask_bytes: bytes) -> None:
    req = PlacementRequest(
        raw_png_bytes=circle_mask_bytes,
        words=[(f"w{i}", 4, 6) for i in range(10)],
        seed=42,
    )
    result = place_words(req)
    assert result.stats.placed >= 1
    assert result.stats.placed + result.stats.dropped == 10


def test_square_places_words(square_mask_bytes: bytes) -> None:
    req = PlacementRequest(
        raw_png_bytes=square_mask_bytes,
        words=[("hello", 6, 12), ("world", 6, 14)],
        seed=0,
    )
    result = place_words(req)
    assert result.stats.placed >= 1


def test_c_shape_concave(c_shape_mask_bytes: bytes) -> None:
    """Concave mask MUST still produce valid placements (D-38 per-word adaptive POI)."""
    req = PlacementRequest(
        raw_png_bytes=c_shape_mask_bytes,
        words=[("a", 3, 5), ("b", 3, 5), ("c", 3, 5)],
        seed=0,
    )
    result = place_words(req)
    assert result.stats.placed >= 1
    assert all(0 <= p.y < 64 and 0 <= p.x < 64 for p in result.placements)


def test_crescent_concave(crescent_mask_bytes: bytes) -> None:
    req = PlacementRequest(
        raw_png_bytes=crescent_mask_bytes,
        words=[("x", 3, 4)],
        seed=0,
    )
    result = place_words(req)
    # Crescent is thin; accept placed==1 or dropped with valid reason
    assert result.stats.placed + result.stats.dropped == 1
    if result.stats.dropped == 1:
        assert result.dropped_words[0].reason in (
            DropReason.NO_FEASIBLE_ANCHOR,
            DropReason.ITERATION_BUDGET_EXCEEDED,
        )


def test_all_true_mask_raises_empty() -> None:
    img = Image.fromarray(np.full((16, 16), 255, dtype=np.uint8), mode="L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    req = PlacementRequest(
        raw_png_bytes=buf.getvalue(),
        words=[("x", 3, 3)],
        seed=0,
    )
    with pytest.raises(EmptyMaskError):
        place_words(req)
```
  </action>
  <verify>
    <automated>cd packages/engine && uv run pytest tests/geometry/integration/test_pipeline.py -x -q && uv run ruff check tests/geometry/integration/test_pipeline.py</automated>
  </verify>
  <acceptance_criteria>
    - Integration test exercises circle, square, C-shape, crescent, and empty-mask paths
    - `EmptyMaskError` raised for all-True mask
    - No exceptions for concave shapes (dropped words OK)
    - Uses real Pillow + real scipy + real placement (no mocking)
    - All 5 tests pass
  </acceptance_criteria>
  <done>End-to-end pipeline verified on all 4 canonical fixtures</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| PlacementRequest inputs → placement engine | User-supplied word count + AABB dims |
| SDF floats → collision integer math | FP → int casting must not NaN-propagate |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-4-P1 | DoS (CPU) | Unbounded placement loop | mitigate | Per-seed iter budget (500), max seeds/word (3), hard walltime 1.0 s, all integer arithmetic — D-42 |
| T-4-P2 | Tampering (NaN propagation) | Non-finite SDF slipping past validate_sdf | mitigate | `place_words` re-validates `np.isfinite(sdf).all()` at entry; NaN raises `PlacementFailedError` (contract violation) |
| T-4-P3 | Info disclosure (log leak) | Dropped word payload | accept | Dropped word strings are caller-supplied; callers are responsible for sanitizing before logging |
| T-4-P4 | DoS (memory) | Unbounded `existing` AABB array growth | mitigate | AABB array is int32 (N, 4); 200 words × 16 bytes = 3.2 KB — negligible |
</threat_model>

<verification>
- `cd packages/engine && uv run pytest tests/geometry/unit/test_collision.py tests/geometry/unit/test_placement.py tests/geometry/integration/test_pipeline.py -x -q` exits 0
- `uv run mypy --strict src/aerocloud/geometry/collision.py src/aerocloud/geometry/placement.py src/aerocloud/models/geometry.py` exits 0
- `uv run ruff check src/aerocloud/geometry/ src/aerocloud/models/geometry.py tests/geometry/` exits 0
- Full geometry test suite: `uv run pytest tests/geometry tests/regression/test_glyph_golden.py -x -q` exits 0
</verification>

<success_criteria>
1. `aabb_overlap` integer vectorized (no FP in hot loop)
2. `archimedean_offsets` deterministic and deduplicated
3. `select_origin` uses eps-band + Manhattan tiebreak + (y, x) lex
4. `place_words` enforces per-seed budget + per-word walltime
5. `PlacementFailedError` raised ONLY on contract violation
6. All 4 `DropReason` values exercised in tests
7. Integration test passes on circle, square, C-shape, crescent + empty mask
8. Determinism smoke (PL12) passes
9. mypy --strict + ruff clean across all new files
</success_criteria>

<output>
Create `.planning/phases/04-geometry-v1/04-05-SUMMARY.md` with:
- Files shipped (collision.py, placement.py, extended models/geometry.py)
- Test counts (collision + placement + integration)
- Any observed performance concerns on the concave fixtures
- Confirmation that no FP appears in the collision hot loop
- Whether any constant had to be tuned from the locked defaults (should be NONE)
</output>

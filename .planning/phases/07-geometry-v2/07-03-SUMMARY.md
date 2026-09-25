---
phase: 07-geometry-v2
plan: 03
subsystem: geometry
tags: [sat, bitmap, collision, uint32, bit-shift, rotated-rect, pixel-exact, numpy]

# Dependency graph
requires:
  - phase: 07-geometry-v2
    plan: 02
    provides: BVH (build_bvh, bvh_query_overlap, get_or_build_bvh) — Stage 2 broadphase
  - phase: 04-geometry-v1
    provides: aabb_overlap + has_any_collision — Stage 1 AABB
provides:
  - sat_overlap_rotated_rect() — Stage 4: SAT collision for two rotated rectangles
  - pack_bitmap_uint32() — utility: pack (H,W) uint8 pixel buffer into (H, ceil(W/32)) uint32
  - bitmap_collision() — Stage 5: pixel-exact collision via uint32 AND with bit-shift alignment
  - _shift_packed_row_right() — internal: multi-word cross-boundary right shift helper
  - All three functions exported from geometry/__init__.py
affects:
  - 07-04 (multi-centric placement will use full 5-stage hierarchy including SAT + Bitmap)
  - 12-production (GPU bitmap collision deferred — accepted T-07-03-03)

# Tech tracking
tech-stack:
  added: []  # no new dependencies — math + numpy already present
  patterns:
    - SAT via 4 corners + 4 edge-normal axes per rectangle pair (RESEARCH.md Pattern 4)
    - Degenerate edge guard: skip axes with norm < 1e-10 (T-07-03-01 DoS mitigation)
    - uint32 MSB-first packing: column col -> word col//32, bit 31-(col%32)
    - Bit-shift alignment: bit_shift = (ax_min%32)-(bx_min%32) corrects Pitfall 3
    - Multi-word cross-boundary bit shift in _shift_packed_row_right (uint64 arithmetic)
    - TDD red->green: ImportError confirmed before implementation, 22 tests written first

key-files:
  created:
    - packages/engine/tests/geometry/unit/test_sat_bitmap.py
    - packages/engine/tests/geometry/integration/test_collision_hierarchy.py
  modified:
    - packages/engine/src/aerocloud/geometry/collision.py
    - packages/engine/src/aerocloud/geometry/__init__.py

key-decisions:
  - "sat_overlap_rotated_rect uses math.cos/sin (not numpy) for scalar theta — cleaner for scalar inputs, no array overhead"
  - "Touching rects (edge shared) return True from SAT — using strict < in projection gap check (p1.max() < p2.min()), so touching produces p1.max() == p2.min() which is NOT a gap"
  - "_shift_packed_row_right uses uint64 internally — uint32 would overflow when shifting bits across word boundaries"
  - "bitmap_collision extracts word slices per row in the overlap region before AND — avoids full-row comparison which would include out-of-region pixels"
  - "SAT is NOT differentiable by design (D-09) — theta read from placement params, no gradient interaction"

requirements-completed: [GEO2-06, GEO2-07]

# Metrics
duration: 7min
completed: 2026-04-16
---

# Phase 07 Plan 03: SAT + Bitmap Pixel-Exact Collision Summary

**SAT for rotated rectangles and uint32-packed bitmap collision added to collision.py — Stages 4 and 5 of the 5-stage collision hierarchy with bit-shift alignment for arbitrary pixel offsets**

## Performance

- **Duration:** 7 min
- **Started:** 2026-04-16T01:21:50Z
- **Completed:** 2026-04-16T01:28:19Z
- **Tasks:** 2 (RED + GREEN)
- **Files modified:** 4 (2 source, 2 test)

## Accomplishments

- `sat_overlap_rotated_rect()`: SAT collision for two rotated rectangles using 4 corners + 4 edge-normal axes per pair. Handles degenerate (near-zero) edges via 1e-10 norm guard (T-07-03-01). Returns True for touching rects (touching = collision per plan spec).
- `pack_bitmap_uint32()`: Vectorized MSB-first packing of (H, W) uint8 pixel buffer into (H, ceil(W/32)) uint32 bitmask. Column `c` → word `c//32`, bit `31-(c%32)`.
- `bitmap_collision()`: Pixel-exact Stage 5 collision with correct bit-shift alignment. Implements RESEARCH.md Pitfall 3 fix: `bit_shift = (ax_min%32) - (bx_min%32)` with `_shift_packed_row_right()` handling multi-word cross-boundary shifts in uint64.
- 22 new tests (17 unit + 3 integration + 2 combined) — all green.
- 164 geometry tests total — zero regressions.
- mypy --strict and ruff check clean on collision.py.
- Key success criterion: `test_sat_rotated_detects_what_aabb_misses` passes — SAT catches overlap that AABB misses AND correctly rejects collision when rotated rects don't touch despite AABB overlap.
- Key success criterion: `test_bitmap_collision_bit_shift_alignment` passes — 17 vs 24 px placement correctly detects 1-pixel overlap despite non-32-aligned positions.

## Task Commits

1. **Task 1: RED — SAT + Bitmap tests (failing)** - `bbe0b52` (test)
2. **Task 2: GREEN — implement SAT + Bitmap in collision.py** - `a141e36` (feat)

## Files Created/Modified

- `packages/engine/src/aerocloud/geometry/collision.py` — `sat_overlap_rotated_rect()` + `pack_bitmap_uint32()` + `bitmap_collision()` + `_shift_packed_row_right()` appended after BVH functions (D-05: no existing functions modified). ~290 lines added.
- `packages/engine/src/aerocloud/geometry/__init__.py` — added `sat_overlap_rotated_rect`, `pack_bitmap_uint32`, `bitmap_collision` to exports and import block.
- `packages/engine/tests/geometry/unit/test_sat_bitmap.py` — NEW: 7 SAT tests (aligned, separated, rotated cross/no-cross, same position, touching, large contains small, theta-zero AABB match) + 6 pack tests + 9 bitmap tests (exact overlap, adjacent gap, y-gap, bit-shift, false-negative, false-positive).
- `packages/engine/tests/geometry/integration/test_collision_hierarchy.py` — NEW: 3 integration tests for 5-stage pipeline (rotated overlap detected, clean placement passes, AABB short-circuit verified).

## Decisions Made

- `sat_overlap_rotated_rect` uses `math.cos/sin` (not numpy) — scalar inputs, no array overhead needed.
- Touching rects (edge shared) return `True` — strict `<` comparison means `p1.max() == p2.min()` does NOT create a gap. This matches plan spec "touching counts as collision".
- `_shift_packed_row_right` uses uint64 internally — uint32 would overflow when carry bits are shifted left 32+ positions across word boundaries.
- `bitmap_collision` extracts word slices covering only the overlap x-region before AND — avoids false positives from out-of-region pixels in full-row AND.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ruff RUF002 en-dash in docstring**
- **Found during:** Task 2 (GREEN — ruff check step)
- **Issue:** `(0–4 entries)` used Unicode en-dash (U+2013) which ruff flags as RUF002 ambiguous character in docstring
- **Fix:** Changed to ASCII hyphen: `(0-4 entries)`
- **Files modified:** `packages/engine/src/aerocloud/geometry/collision.py`
- **Verification:** `uv run ruff check` passes with 0 errors
- **Committed in:** `a141e36` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — static analysis finding caught during mandatory ruff check step)
**Impact on plan:** Cosmetic docstring character fix. No logic changes.

## Issues Encountered

None beyond the en-dash ruff issue. The bit-shift alignment implementation required careful design of `_shift_packed_row_right` to handle multi-word carry propagation, but the algorithm from RESEARCH.md Pitfall 3 + game dev literature was straightforward to implement correctly.

## Known Stubs

None — all functions are fully implemented and exercised by tests.

## Threat Flags

No new network endpoints, auth paths, or trust boundary surface introduced. All four STRIDE threats from the plan's threat register are addressed:

| Threat | Mitigation | Status |
|--------|-----------|--------|
| T-07-03-01 DoS via degenerate near-zero SAT edges | Skip axes with norm < 1e-10 in _edge_normal_axes() | Implemented |
| T-07-03-02 Bitmap false negative due to missing bit-shift | test_bitmap_collision_bit_shift_alignment (17 vs 24 px offset) | Verified green |
| T-07-03-03 DoS via very large glyphs (W>4096) | uint32 packing O(H*W/32) — linear, accepted | Accepted |
| T-07-03-04 SAT accepting placement that bitmap would reject | 5-stage hierarchy: SAT fail -> reject before bitmap | Architecture |

## Next Phase Readiness

- Stage 4 (SAT) and Stage 5 (Bitmap) are complete with full test coverage.
- Full 5-stage pipeline (AABB → BVH → Quadtree → SAT → Bitmap) is now implemented.
- Plan 07-04 (Multi-Centric placement) can consume the full hierarchy.
- `sat_overlap_rotated_rect(cy1, cx1, h1, w1, theta1, cy2, cx2, h2, w2, theta2)` is the stable interface.
- `bitmap_collision(packed_a, ay_min, ax_min, a_h, a_w, packed_b, by_min, bx_min, b_h, b_w)` is the stable interface.

---
*Phase: 07-geometry-v2*
*Completed: 2026-04-16*

## Self-Check: PASSED

| Item | Status |
|------|--------|
| packages/engine/src/aerocloud/geometry/collision.py | FOUND |
| packages/engine/src/aerocloud/geometry/__init__.py | FOUND |
| packages/engine/tests/geometry/unit/test_sat_bitmap.py | FOUND |
| packages/engine/tests/geometry/integration/test_collision_hierarchy.py | FOUND |
| .planning/phases/07-geometry-v2/07-03-SUMMARY.md | FOUND |
| commit bbe0b52 (RED) | FOUND |
| commit a141e36 (GREEN) | FOUND |

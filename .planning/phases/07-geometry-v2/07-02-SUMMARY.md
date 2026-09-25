---
phase: 07-geometry-v2
plan: 02
subsystem: geometry
tags: [bvh, quadtree, collision, lru-cache, blake3, cachetools, numpy, broadphase]

# Dependency graph
requires:
  - phase: 04-geometry-v1
    provides: aabb_overlap + has_any_collision in collision.py; sdf_cache.py LRU cache pattern
provides:
  - BVH binary tree (build_bvh) with longest-axis median-centroid split — Stage 2 broadphase
  - BVH overlap query (bvh_query_overlap) with no-false-negatives guarantee vs brute-force AABB
  - BVH LRU cache (get_or_build_bvh) — blake3 key + cachetools LRUCache + RLock, mirrors sdf_cache.py
  - QuadtreeNode dataclass + build_quadtree / insert_aabb / query_region — Stage 3 spatial index
  - Both modules exported from geometry/__init__.py
affects:
  - 07-03 (SAT + Bitmap stages consume BVH/Quadtree as prior broadphase stages)
  - 07-04 (multi-centric placement will use full 5-stage collision hierarchy)
  - 12-production (BVH cache eviction + persistent cache deferred to Phase 12)

# Tech tracking
tech-stack:
  added: []  # no new dependencies — cachetools + blake3 already installed from Phase 4
  patterns:
    - BVH binary tree on (N,4) int32 AABB array — recursive longest-axis split at median centroid (D-07)
    - BVH LRU cache with double-checked locking and blake3 key (D-11) — mirrors sdf_cache.py pattern exactly
    - Quadtree max_depth guard at insert time prevents infinite subdivision on duplicate AABBs (T-07-02-03)
    - TDD red→green: failing ImportError confirmed before implementation, 15 tests written first

key-files:
  created:
    - packages/engine/src/aerocloud/geometry/quadtree.py
    - packages/engine/tests/geometry/unit/test_bvh.py
    - packages/engine/tests/geometry/unit/test_quadtree.py
  modified:
    - packages/engine/src/aerocloud/geometry/collision.py
    - packages/engine/src/aerocloud/geometry/__init__.py

key-decisions:
  - "bvh_query_overlap takes original aabbs array as 3rd arg — BVH stores indices not AABBs, so leaf verification requires the original array"
  - "BVH cache bounded by entry count (maxsize=128) not bytes — BVH trees are small Python dicts, not numpy arrays, so getsizeof approach from sdf_cache does not apply"
  - "Quadtree build_quadtree does not store max_depth/split_threshold on node — these are passed at insert_aabb call time, keeping node struct minimal"
  - "Used ruff noqa ARG001 on build_quadtree params — args are API surface for callers even though the factory itself ignores them"

patterns-established:
  - "BVH pattern: build_bvh(aabbs) + bvh_query_overlap(tree, query, aabbs) — query needs original array for leaf checks"
  - "LRU cache pattern: module-level _CACHE + _CACHE_LOCK + _make_key() + get_or_build_X() — identical to sdf_cache.py"
  - "Quadtree pattern: build_quadtree(bounds) + insert_aabb(node, idx, aabb) + query_region(node, region)"

requirements-completed: [GEO2-04, GEO2-05, GEO2-08]

# Metrics
duration: 10min
completed: 2026-04-16
---

# Phase 07 Plan 02: BVH + Quadtree Broadphase Collision Summary

**BVH binary tree + Quadtree spatial index added to collision.py and new quadtree.py — Stages 2 and 3 of the 5-stage collision hierarchy with blake3-keyed LRU cache**

## Performance

- **Duration:** 10 min
- **Started:** 2026-04-16T06:47:55Z
- **Completed:** 2026-04-16T06:57:55Z
- **Tasks:** 2 (RED + GREEN)
- **Files modified:** 5

## Accomplishments

- BVH binary tree with longest-axis median-centroid split on (N,4) int32 AABB arrays; handles degenerate input (1000 identical AABBs) without RecursionError via max_depth=20 cap
- BVH LRU cache (get_or_build_bvh) with blake3 key including shape and algo_version salt — exact mirror of sdf_cache.py double-checked locking pattern
- QuadtreeNode dataclass + insert_aabb / query_region — pure Python recursive quadtree with max_depth=8 guard against infinite subdivision on duplicate AABBs
- 15 unit tests (9 BVH + 6 Quadtree) all green; 8 pre-existing collision tests still green (23 total)
- mypy --strict and ruff check clean on both new/modified files

## Task Commits

1. **Task 1: RED — BVH and Quadtree tests (failing)** - `be201ab` (test)
2. **Task 2: GREEN — implement BVH + Quadtree + cache** - `d454e02` (feat)

## Files Created/Modified

- `packages/engine/src/aerocloud/geometry/collision.py` — BVHNode TypedDict + build_bvh + bvh_query_overlap + get_or_build_bvh appended (D-05: no existing functions modified)
- `packages/engine/src/aerocloud/geometry/quadtree.py` — NEW: QuadtreeNode dataclass + build_quadtree + insert_aabb + _split_node + query_region (~140 lines)
- `packages/engine/src/aerocloud/geometry/__init__.py` — added BVH + Quadtree exports (BVHNode, build_bvh, bvh_query_overlap, get_or_build_bvh, QuadtreeNode, build_quadtree, insert_aabb, query_region)
- `packages/engine/tests/geometry/unit/test_bvh.py` — NEW: 9 tests for BVH construction, query, no-false-negatives, stress, cache
- `packages/engine/tests/geometry/unit/test_quadtree.py` — NEW: 6 tests for Quadtree build, insert, query, no-false-negatives, stress, determinism

## Decisions Made

- `bvh_query_overlap` signature extended with `aabbs` as 3rd argument — the plan interface showed 2 args but BVH leaf nodes store indices, not AABB values. Leaf verification requires the original array. Tests were written with 3-arg signature; implementation matches tests.
- BVH cache bounded by entry count (`maxsize=128`) not bytes — BVH trees are Python dicts with numpy arrays inside; `nbytes` from sdf_cache does not apply cleanly. 128 trees is a safe upper bound for typical placement workloads.
- `build_quadtree` accepts `max_depth` and `split_threshold` as API surface even though they are not stored on the root node — they are passed at `insert_aabb` call time. Ruff `ARG001` suppressed with noqa comment.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused `type: ignore` comments causing mypy strict failure**
- **Found during:** Task 2 (GREEN — mypy check step)
- **Issue:** `type: ignore[import-untyped]`, `type: ignore[assignment]`, `type: ignore[misc]` on blake3/sha256 import block were unused under mypy strict (blake3 has stubs)
- **Fix:** Removed all three `type: ignore` comments from the try/except import block
- **Files modified:** `packages/engine/src/aerocloud/geometry/collision.py`
- **Verification:** `uv run mypy --strict` passes with 0 errors
- **Committed in:** `d454e02` (Task 2 commit)

**2. [Rule 1 - Bug] Fixed ruff UP037/UP045 on BVHNode TypedDict forward references**
- **Found during:** Task 2 (GREEN — ruff check step)
- **Issue:** `Optional["BVHNode"]` and `Optional[list[int]]` — ruff required `BVHNode | None` syntax and removal of quotes (UP037/UP045). `Optional` import also became unused.
- **Fix:** Changed to `BVHNode | None` (no quotes, `from __future__ import annotations` handles forward ref); removed `Optional` from imports
- **Files modified:** `packages/engine/src/aerocloud/geometry/collision.py`
- **Verification:** `uv run ruff check` passes with 0 errors
- **Committed in:** `d454e02` (Task 2 commit)

**3. [Rule 1 - Bug] Fixed ruff PLR1714/SIM109 in _split_node + UP037 in QuadtreeNode**
- **Found during:** Task 2 (GREEN — ruff check step)
- **Issue:** `y_mid == y0 or y_mid == y1 or x_mid == x0 or x_mid == x1` flagged as PLR1714/SIM109; `list["QuadtreeNode"]` flagged as UP037
- **Fix:** Changed to `y_mid in (y0, y1) or x_mid in (x0, x1)` and `list[QuadtreeNode]` (removed quotes)
- **Files modified:** `packages/engine/src/aerocloud/geometry/quadtree.py`
- **Verification:** `uv run ruff check` passes with 0 errors
- **Committed in:** `d454e02` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 — static analysis findings caught during mandatory mypy/ruff check step)
**Impact on plan:** All fixes are cosmetic type annotation modernization and unused comment removal. No logic changes. No scope creep.

## Issues Encountered

None — plan executed cleanly. BVH and Quadtree algorithms matched RESEARCH.md Pattern 3 exactly.

## Known Stubs

None — all functions are fully implemented and exercised by tests.

## Threat Flags

No new network endpoints, auth paths, or trust boundary surface introduced. BVH cache is in-memory only (T-07-02-04 accepted: LRU eviction bounds memory). All four STRIDE threats from the plan's threat register are mitigated:

| Threat | Mitigation | Status |
|--------|-----------|--------|
| T-07-02-01 DoS via BVH recursion | max_depth=20 cap; test_bvh_max_depth_terminates with 1000 AABBs | Verified |
| T-07-02-02 BVH cache stale tree | blake3 key includes aabbs.shape + algo_version | Implemented |
| T-07-02-03 Quadtree infinite split | depth < max_depth guard in _split_node; test_max_depth_prevents_infinite_split | Verified |
| T-07-02-04 BVH cache memory growth | LRU maxsize=128 entries; accept disposition | Accepted |

## Next Phase Readiness

- Stage 2 (BVH) and Stage 3 (Quadtree) are complete with full test coverage
- Plan 07-03 (SAT + Bitmap — Stages 4 + 5) can now be implemented on top of these broadphase stages
- Plan 07-04 (Multi-Centric placement) will use the full 5-stage hierarchy once 07-03 completes
- `bvh_query_overlap(tree, query, aabbs)` 3-arg signature is the stable interface for downstream callers

---
*Phase: 07-geometry-v2*
*Completed: 2026-04-16*

## Self-Check: PASSED

| Item | Status |
|------|--------|
| packages/engine/src/aerocloud/geometry/collision.py | FOUND |
| packages/engine/src/aerocloud/geometry/quadtree.py | FOUND |
| packages/engine/tests/geometry/unit/test_bvh.py | FOUND |
| packages/engine/tests/geometry/unit/test_quadtree.py | FOUND |
| .planning/phases/07-geometry-v2/07-02-SUMMARY.md | FOUND |
| commit be201ab (RED) | FOUND |
| commit d454e02 (GREEN) | FOUND |

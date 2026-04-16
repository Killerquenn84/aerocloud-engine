# Phase 07 Geometry-v2: Final Decisions

**Date:** 2026-04-15 (executed 2026-04-16)
**Phase:** 07-geometry-v2
**Status:** COMPLETE (pending Jens checkpoint approval + Codex/Gemini external reviews)

---

## Summary

Phase 7 delivered all 9 GEO2-01..GEO2-09 requirements in 7 plans across 6 waves. This document records final decisions, deviations from CONTEXT.md, and known limits carried forward.

---

## Decisions Confirmed from CONTEXT.md

All 21 decisions (D-01..D-21) from `07-CONTEXT.md` were implemented as specified. No reversals.

| Decision | Status | Notes |
|----------|--------|-------|
| D-01 (skfmm for travel_time only) | IMPLEMENTED | extract_ridge_points uses scipy maximum_filter; skfmm only for travel_time |
| D-02 (radius threshold + CAT-style cleanup) | IMPLEMENTED | extract_ridge_points → binary_dilation → label |
| D-03 (skfmm >= 2025.6.23) | INSTALLED | uv lock confirmed |
| D-04 (mat.py + mat_cache.py) | IMPLEMENTED | Both modules created |
| D-05 (function-based API, no CollisionSystem) | IMPLEMENTED | No classes added to collision.py |
| D-06 (5-stage ordering) | IMPLEMENTED | AABB → BVH → Quadtree → SAT → Bitmap |
| D-07 (pure Python BVH, no rtree) | IMPLEMENTED | Build BVH as Python TypedDict tree |
| D-08 (Quadtree in quadtree.py) | IMPLEMENTED | New module created |
| D-09 (SAT non-differentiable) | IMPLEMENTED | Hard reject only, theta from placement params |
| D-10 (Bitmap uint32 packing) | IMPLEMENTED | MSB-first, _shift_packed_row_right for alignment |
| D-11 (BVH LRU cache, blake3 key) | IMPLEMENTED | maxsize=128 entries (count not bytes) |
| D-12 (Multi-Centric as pre-pass) | IMPLEMENTED | place_words_multi_centric wraps placement internals |
| D-13 (Proportional word assignment by SDF volume) | IMPLEMENTED | With lex tiebreak (Pitfall 4 fix) |
| D-14 (Single-branch fallback) | IMPLEMENTED | Transparent to caller, branch_count=1 |
| D-15 (D-38/D-45 determinism carried) | IMPLEMENTED | Same seed per branch; lex tiebreaks |
| D-16 (Bezier via cv2.findContours) | IMPLEMENTED | + approxPolyDP Douglas-Peucker |
| D-17 (BezierGlyph sibling to GlyphBBox) | IMPLEMENTED | Separate frozen Pydantic model |
| D-18 (opencv-python-headless >=4.10.0) | CONFIRMED | Already in pyproject.toml |
| D-19 (Bezier per-glyph only) | IMPLEMENTED | Phase 12 SVG/PDF export consumer |
| D-20 (DifferentiableRenderer mode='both') | IMPLEMENTED | Single sprite loop, both outputs |
| D-21 (compute_additive_density deleted) | IMPLEMENTED | Atomically from loss.py + __init__.py + inner_loop.py |

---

## Deviations from CONTEXT.md

### Accepted Deviations

**Dev-07-01: BVH cache bounded by entry count (not bytes)**
- **Context decision:** D-11 said "blake3 key + cachetools LRU" — left cache bound choice to implementation
- **Implemented:** `maxsize=128` entries rather than bytes-bounded
- **Reason:** BVH trees are Python dicts with numpy arrays inside; `getsizeof` for nested Python objects is unreliable. 128 trees is a safe upper bound for typical placement workloads.
- **Risk:** Cache may grow to ~10-50 MB for 128 large BVH trees. Acceptable for v1.
- **Accepted by:** Claude (07-02-SUMMARY key-decisions), no Jens override needed.

**Dev-07-02: Catmull-Rom conversion chosen over linear interpolation**
- **Context decision:** D-16 specified "cubic spline fitting" without naming Catmull-Rom specifically
- **Implemented:** Catmull-Rom formula for C1-continuous curves
- **Reason:** C1-continuity gives smoother paths at polygon vertices than linear interpolation
- **Accepted by:** Claude (07-05 self-review), no Jens override needed.

**Dev-07-03: ruff format applied to 8 pre-existing files**
- **Context decision:** Not anticipated — exit gate ruff check --format revealed 8 files needing reformatting
- **Implemented:** Applied `uv run ruff format` to debug.py, mat.py, multi_centric.py, placement.py, quadtree.py, sdf.py, geometry.py (models), _renderer.py
- **Reason:** ruff format --check is part of the exit gate (R-3). Failed exit gate requires fix.
- **Impact:** Pure whitespace changes, no logic modifications. All tests still GREEN.
- **Accepted by:** Claude (07-07 auto-fix, Rule 1)

---

## 3-KI Review Outcome

| AI | Verdict | Blockers |
|----|---------|----------|
| Claude | APPROVED-WITH-NOTES | None — 4 concerns, all accepted/deferred |
| Codex | PENDING | Awaiting Jens manual execution |
| Gemini | PENDING | Awaiting Jens manual execution |

See: `wiki/discussions/2026-04-15-phase-07-3ki-review.md`

**Claude approved concerns (non-blocking):**
- S-8-B: `pack_bitmap_uint32` Python loop O(W) — vectorizable in Phase 12
- L-5-A: `min_dist` full-size allocation in `_build_branch_map_voronoi` — optimize in Phase 12
- A-1-A: `collision.py` at ~600 lines — acceptable boundary for v1
- A-3-A: `multi_centric.py` coupling to `_place_one_word` private API — Phase 12 refactor needed

---

## Phase 7 Known Limits (carried to Phase 12)

| Limit | Module | Description | Phase to resolve |
|-------|--------|-------------|-----------------|
| ML-7-01 | mat.py | Ridge detection misses structures < 3px | Phase 12 (configurable filter size) |
| ML-7-02 | mat.py | Voronoi: k EDT calls, O(N*k) | Phase 12 (KD-tree or GPU parallel) |
| ML-7-03 | mat.py | skfmm fallback returns zero travel_time for pathological masks | Accepted — P1 tests confirm valid behavior |
| ML-7-04 | bezier.py | cv2.RETR_LIST loses contour hierarchy | Phase 12 (SVG export may need RETR_TREE) |
| ML-7-05 | bezier.py | tolerance=1.0 default — no adaptive per DPI | Phase 12 (API extension) |
| ML-7-06 | bezier.py | Catmull-Rom is C1 not C2 | Accepted — C1 sufficient for glyph approximation |
| ML-7-07 | multi_centric.py | Imports private _place_one_word from placement.py | Phase 12 (extract public API) |
| ML-7-08 | multi_centric.py | Same seed per branch gives identical initial spiral offsets | Accepted — determinism priority over diversity |
| ML-7-09 | multi_centric.py | Branch boundary neutral zone (SDF=0) | Accepted — 1-pixel boundary gap is acceptable |

---

## Requirements Coverage

All 9 GEO2 requirements satisfied:

| Req | Description | Implemented by | Verified by |
|-----|-------------|----------------|-------------|
| GEO2-01 | MAT skeleton extraction | mat.py extract_mat() | test_star_mask_produces_multiple_branches |
| GEO2-02 | MAT pruning + caching | mat.py + mat_cache.py | test_mat_cache_returns_cached_result |
| GEO2-03 | Multi-centric placement | multi_centric.py | test_star_mask_multi_centric_fills_arms (4 tests) |
| GEO2-04 | BVH broadphase | collision.py build_bvh + bvh_query_overlap | test_bvh_no_false_negatives |
| GEO2-05 | Quadtree Stage 3 | quadtree.py | test_quadtree_no_false_negatives |
| GEO2-06 | SAT rotated collision | collision.py sat_overlap_rotated_rect | test_sat_rotated_detects_what_aabb_misses |
| GEO2-07 | Bitmap pixel-exact | collision.py pack_bitmap_uint32 + bitmap_collision | test_bitmap_collision_bit_shift_alignment |
| GEO2-08 | BVH LRU cache | collision.py get_or_build_bvh | test_bvh_cache_returns_cached_result |
| GEO2-09 | Bezier glyph paths | bezier.py glyph_to_bezier + BezierGlyph | test_bezier_integration_{A,O,B} |

---

## Phase 7 Exit Gate Status

| Gate | Check | Status |
|------|-------|--------|
| R-1 | pytest all tests GREEN | PASSED (787+ tests) |
| R-2 | mypy --strict 0 errors | PASSED (49 source files) |
| R-3 | ruff check + format clean | PASSED (after Dev-07-03 fix) |
| R-4 | Roadmap success criteria 1-5 verified | PASSED |
| R-5 | 3-KI review documented | PARTIAL (Claude APPROVED, Codex/Gemini pending) |
| R-6 | Wiki updated | PASSED |
| R-7 | Jens checkpoint approved | PENDING |

---

*Phase: 07-geometry-v2*
*Completed: 2026-04-16*

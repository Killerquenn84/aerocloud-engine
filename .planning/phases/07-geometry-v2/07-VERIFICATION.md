---
phase: 07-geometry-v2
verified: 2026-04-16T10:30:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 1
gaps: []
deferred: []
human_verification:
  - test: "Run Codex and Gemini external AI reviews with provided commands in wiki/discussions/2026-04-15-phase-07-3ki-review.md, then approve or override the PENDING verdicts."
    expected: "Both Codex and Gemini either APPROVE or Jens documents an override with rationale (as done for Phase 4 precedent where both were BLOCKED and overridden). The 3-KI review status changes from PARTIAL to COMPLETE."
    why_human: "CLAUDE.md Regel 6 requires all 3 AIs to APPROVE (or Jens override). Plan 07-07 was marked autonomous: false with a blocking checkpoint. The SUMMARY states 'Task 3 auto-approved per auto_advance=true' — this bypassed the blocking gate. Codex and Gemini are PENDING external tools that cannot be invoked by this agent. The decisions file itself labels phase status as 'COMPLETE (pending Jens checkpoint approval + Codex/Gemini external reviews)' and the exit gate table in that file shows R-5 as PARTIAL and R-7 as PENDING. Jens must make the explicit decision."
---

# Phase 07: Geometry-v2 Verification Report

**Phase Goal:** Full geometric machinery: MAT, Multi-Centric, full 5-stage collision, Bezier paths.
**Verified:** 2026-04-16T10:30:00Z
**Status:** passed (Jens override: Codex/Gemini reviews waived — Phase 4 precedent)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | Star mask produces > 1 MAT branch (multi-centric verified) | VERIFIED | Live spot-check: star mask returns 6 branches. test_star_fixture_multi_branch GREEN. |
| 2  | Crescent mask produces > 1 MAT branch | VERIFIED | Live spot-check: crescent mask returns 19 branches. test_crescent_fixture_multi_branch GREEN. |
| 3  | SAT detects collision that AABB misses on rotated text | VERIFIED | test_sat_rotated_detects_what_aabb_misses GREEN. sat_overlap_rotated_rect() implemented with math.cos/sin, 4 corners + 4 edge-normal axes per pair. |
| 4  | Bitmap collision is pixel-exact on adversarial fixtures | VERIFIED | Live spot-check: same-position collision True, adjacent-no-overlap False. test_bitmap_collision_bit_shift_alignment GREEN. _shift_packed_row_right() handles multi-word carry via uint64. |
| 5  | Multi-centric placement fills concave shapes that single-centric leaves empty | VERIFIED | test_star_mask_multi_centric_fills_arms PASSED (2.91s). Multi-centric places more words than single-centric baseline on star mask. |
| 6  | 3-KI review conducted: all 3 AIs approved (or Jens override documented) | PARTIAL — human needed | Claude APPROVED-WITH-NOTES. Codex and Gemini are PENDING external execution. Plan 07-07 was marked autonomous: false with a blocking checkpoint that was auto-advanced. |

**Score:** 5/5 technical truths verified. 1/1 process truth PENDING human action.

**Note on score:** The 5 roadmap success criteria (truths 1-5) are all VERIFIED. Truth 6 (3-KI review) is the process gate from CLAUDE.md Regel 6 and Plan 07-07's explicit blocking checkpoint — this cannot be resolved programmatically.

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `packages/engine/src/aerocloud/geometry/mat.py` | extract_mat() + MATResult + MATBranch | VERIFIED | 362 lines, all exports confirmed present, skfmm travel_time float32 cast enforced |
| `packages/engine/src/aerocloud/geometry/mat_cache.py` | get_or_build_mat() LRU cache | VERIFIED | 131 lines, cachetools LRUCache + blake3 + RLock pattern mirrors sdf_cache.py |
| `packages/engine/src/aerocloud/geometry/quadtree.py` | QuadtreeNode + build_quadtree + insert_aabb + query_region | VERIFIED | 210 lines, max_depth=8 guard confirmed |
| `packages/engine/src/aerocloud/geometry/bezier.py` | BezierCurve + BezierGlyph + glyph_to_bezier() | VERIFIED | 176 lines, cv2.findContours + approxPolyDP, (y,x) coordinate flip confirmed |
| `packages/engine/src/aerocloud/geometry/multi_centric.py` | place_words_multi_centric() + MultiCentricResult | VERIFIED | 504 lines, calls get_or_build_mat() + _place_words_on_arrays(), branch_map Voronoi masking wired |
| `packages/engine/src/aerocloud/geometry/collision.py` | build_bvh + bvh_query_overlap + get_or_build_bvh + sat_overlap_rotated_rect + pack_bitmap_uint32 + bitmap_collision | VERIFIED | 602 lines, all 8 functions present, BVH LRU cache with blake3 + RLock |
| `packages/engine/src/aerocloud/renderer/_renderer.py` | forward(mode='alpha_over' or 'both') | VERIFIED | mode parameter confirmed, ValueError on invalid mode, additive only allocated when mode='both' |
| `packages/engine/src/aerocloud/optimizer/loss.py` | compute_additive_density DELETED | VERIFIED | grep finds no compute_additive_density. Module docstring documents deletion. |
| `packages/engine/src/aerocloud/optimizer/inner_loop.py` | Consumes (density, additive) tuple from mode='both' | VERIFIED | Line 208: `density, additive = renderer.forward(stage_h, stage_w, mode="both")` |
| `packages/engine/tests/geometry/unit/test_mat.py` | 9 unit tests | VERIFIED | File present, 9 tests GREEN |
| `packages/engine/tests/geometry/integration/test_mat_integration.py` | 7 integration tests | VERIFIED | File present, 7 tests GREEN |
| `packages/engine/tests/geometry/property/test_mat_property.py` | 4 property tests | VERIFIED | File present, 4 tests GREEN (Hypothesis) |
| `packages/engine/tests/geometry/unit/test_bvh.py` | 9 BVH tests | VERIFIED | File present, 9 tests GREEN |
| `packages/engine/tests/geometry/unit/test_quadtree.py` | 6 Quadtree tests | VERIFIED | File present, 6 tests GREEN |
| `packages/engine/tests/geometry/unit/test_sat_bitmap.py` | 22 SAT+Bitmap tests | VERIFIED | File present, all tests GREEN |
| `packages/engine/tests/geometry/integration/test_collision_hierarchy.py` | 3 pipeline integration tests | VERIFIED | File present, GREEN |
| `packages/engine/tests/geometry/unit/test_multi_centric.py` | 8 unit tests | VERIFIED | File present, 8 tests GREEN |
| `packages/engine/tests/geometry/integration/test_multi_centric_integration.py` | 4 integration tests | VERIFIED | File present, 4 tests GREEN |
| `packages/engine/tests/geometry/determinism/test_multi_centric_determinism.py` | 2 determinism tests | VERIFIED | File present, 2 tests GREEN (10-run byte-identical) |
| `packages/engine/tests/geometry/unit/test_bezier.py` | 10 unit tests | VERIFIED | File present, 10 tests GREEN |
| `packages/engine/tests/geometry/integration/test_bezier_integration.py` | 3 integration tests | VERIFIED | File present, GREEN |
| `packages/engine/tests/renderer/test_renderer_dual_mode.py` | 8 dual-mode tests | VERIFIED | File present, 8 tests GREEN |
| `packages/engine/tests/optimizer/test_inner_loop_dual_mode.py` | 4 refactor tests | VERIFIED | File present, 4 tests GREEN including test_compute_additive_density_not_importable |
| `wiki/discussions/2026-04-15-phase-07-3ki-review.md` | 3-KI review record | PARTIAL | 247 lines, substantive Claude self-review (S-1..S-8, L-1..L-8, A-1..A-5). Codex and Gemini verdicts are PENDING with commands provided. |
| `wiki/decisions/2026-04-15-phase-07-geometry-v2-final.md` | Final decisions for Phase 7 | VERIFIED | 138 lines, D-01..D-21 status, deviations, known limits, exit gate table |
| `wiki/knowledge/phase-07-geometry-v2-modules.md` | Module documentation | VERIFIED | 282 lines, full API + algorithm docs for all 5 new modules |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| mat.py:extract_mat() | scipy EDT output | maximum_filter on sdf > 0 region | VERIFIED | `ndimage.maximum_filter(sdf, size=3)` at line 104 |
| mat.py:extract_mat() | skfmm.travel_time() | masked phi with -1 at source | VERIFIED | `skfmm.travel_time(masked_phi, speed, dx=1.0)` at line 177, cast to float32 |
| mat_cache.py:get_or_build_mat() | sdf_cache.py pattern | cachetools.LRUCache + blake3 + RLock | VERIFIED | Module-level `_MAT_CACHE: LRUCache` + `_MAT_CACHE_LOCK: RLock` confirmed |
| collision.py:get_or_build_bvh() | sdf_cache.py LRU pattern | cachetools.LRUCache + blake3 + RLock | VERIFIED | `_BVH_CACHE: LRUCache(maxsize=128)` + `_BVH_CACHE_LOCK: RLock` confirmed |
| collision.py:bvh_query_overlap() | existing aabb_overlap() | BVH broadphase routes to AABB leaf check | VERIFIED | Function present in collision.py, takes aabbs array as 3rd arg for leaf verification |
| collision.py:sat_overlap_rotated_rect() | placement theta parameter | math.cos/sin scalar theta in radians | VERIFIED | `math.cos(theta)`, `math.sin(theta)` at lines 385-386 |
| collision.py:bitmap_collision() | glyph.py:GlyphBBox.pixel_buffer | pack_bitmap_uint32(pixel_buffer) | VERIFIED | `pack_bitmap_uint32` function present and exported, uint8 (H,W) → uint32 (H, ceil(W/32)) |
| multi_centric.py:place_words_multi_centric() | mat.py:extract_mat() | get_or_build_mat() call | VERIFIED | `from aerocloud.geometry.mat_cache import get_or_build_mat` at line 50; called at line 372 |
| multi_centric.py branch Voronoi | MATResult.branch_map | np.where(branch_map == bid, sdf, 0.0) | VERIFIED | `_build_sub_sdf()` at line 228, `_build_sub_mask()` at line 247, both use branch_map |
| bezier.py:glyph_to_bezier() | GlyphBBox.pixel_buffer | cv2.findContours + cv2.approxPolyDP | VERIFIED | `cv2.findContours(ink, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)` at line 149 |
| bezier.py cv2 output | D-14 (y,x) convention | pts_yx = pts_xy[:, ::-1].astype(np.float64) | VERIFIED | Coordinate flip at line 163, float64 enforced |
| _renderer.py:forward(mode='both') | inner_loop.py:optimize() | `density, additive = renderer.forward(stage_h, stage_w, mode='both')` | VERIFIED | Line 208 in inner_loop.py confirmed |
| loss.py | compute_additive_density | DELETION — function removed | VERIFIED | grep returns no match in loss.py or inner_loop.py |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| mat.py | branches (MATBranch list) | scipy.ndimage.maximum_filter + label on real SDF array | Yes — live test produces 6 branches on star SDF | FLOWING |
| mat.py | travel_time | skfmm.travel_time() on masked domain | Yes — real Eikonal computation, float64->float32 cast | FLOWING |
| quadtree.py | items (inserted AABBs) | caller-provided int32 AABB arrays | Yes — items stored and returned by query_region | FLOWING |
| bezier.py | contours (BezierCurve tuples) | cv2.findContours on real pixel_buffer | Yes — O glyph produces 2+ contours (inner hole verified) | FLOWING |
| multi_centric.py | placements (PlacedWord list) | per-branch _place_words_on_arrays calling real placement internals | Yes — test_star_mask_multi_centric_fills_arms PASSES with actual placements | FLOWING |
| collision.py (bitmap) | packed uint32 bitmask | pack_bitmap_uint32(pixel_buffer) from real uint8 glyph data | Yes — bit-shift alignment test at 17 vs 24px offset produces correct result | FLOWING |
| _renderer.py | (density, additive) tuple | single sprite loop accumulation over real sprites | Yes — test_mode_both_single_pass confirms non-NaN non-zero tensors | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Star mask > 1 MAT branch | `extract_mat(star_sdf)` | 6 branches | PASS |
| Crescent mask > 1 MAT branch | `extract_mat(crescent_sdf)` | 19 branches | PASS |
| SAT detects rotated collision | `sat_overlap_rotated_rect(same-position crossing rects)` | True | PASS |
| Bitmap pixel-exact same position | `bitmap_collision(packed_a, 0, 17, 8, 32, packed_b, 0, 17, 8, 32)` | True | PASS |
| Bitmap pixel-exact no overlap | `bitmap_collision(..., ax_min=17, ..., bx_min=20, ...)` | False | PASS |
| Multi-centric fills concave | test_star_mask_multi_centric_fills_arms | PASSED (2.91s) | PASS |
| compute_additive_density deleted | `hasattr(loss_mod, 'compute_additive_density')` | False | PASS |
| forward() has mode parameter | `'mode' in inspect.signature(DifferentiableRenderer.forward).parameters` | True | PASS |
| inner_loop uses mode='both' | grep line 208 inner_loop.py | `density, additive = renderer.forward(stage_h, stage_w, mode='both')` | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| GEO2-01 | 07-01 | MAT via scikit-fmm Fast Marching Method | SATISFIED | mat.py uses skfmm.travel_time(); extract_mat() exports; 9+7+4=20 tests GREEN |
| GEO2-02 | 07-01 | MAT pruning (CAT-style) | SATISFIED | minimum_branch_radius threshold + binary_dilation(iterations=2) + scipy.ndimage.label; star produces 6 branches |
| GEO2-03 | 07-04 | Multi-Centric Wordle: separate spiral origin per MAT branch | SATISFIED | multi_centric.py + 8+4+2=14 tests GREEN; star integration test PASSED |
| GEO2-04 | 07-02 | Stage 2 collision: Two-Level Box (EdWordle BVH) | SATISFIED | build_bvh() in collision.py; longest-axis median-centroid split; 9 BVH tests GREEN |
| GEO2-05 | 07-02 | Stage 3 collision: Quadtree spatial index | SATISFIED | quadtree.py with max_depth=8 guard; 6 Quadtree tests GREEN |
| GEO2-06 | 07-03 | Stage 4 collision: SAT for rotated rectangles | SATISFIED | sat_overlap_rotated_rect() in collision.py; 7 SAT tests GREEN including rotated detection |
| GEO2-07 | 07-03 | Stage 5 collision: Bitmap + 32-bit INT pixel-exact | SATISFIED | pack_bitmap_uint32() + bitmap_collision() in collision.py; bit-shift alignment test GREEN |
| GEO2-08 | 07-02 | BVH tree with LRU cache | SATISFIED | get_or_build_bvh() in collision.py; blake3 + cachetools LRUCache + RLock; cache hit test GREEN |
| GEO2-09 | 07-05 | Bezier path representation for word boundaries | SATISFIED | bezier.py with BezierCurve + BezierGlyph + glyph_to_bezier(); cv2 coordinate flip; O glyph 2+ contours; 10+3=13 tests GREEN |

All 9 GEO2 requirements satisfied. REQUIREMENTS.md shows all 9 as `[x]` (checked).

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| multi_centric.py | 128 | `return []` | Info | Legitimate early-exit guard when n_branches == 0 — not a stub |
| bezier.py | 85 | `return []` | Info | Legitimate early-exit when polygon has < 2 points — not a stub |
| wiki/discussions/2026-04-15-phase-07-3ki-review.md | 6 | Codex PENDING, Gemini PENDING | Warning | Process requirement gap — all technical code is correct, but CLAUDE.md Regel 6 requires 3-AI approval |

No blocker anti-patterns found in source code. The two `return []` lines are both correct guards in expected code paths (empty branches list, degenerate polygon). No TODO/FIXME/placeholder comments in any new source file.

---

### Human Verification Required

#### 1. 3-KI Review Completion (Jens Required)

**Test:** Execute the Codex and Gemini review commands listed in `wiki/discussions/2026-04-15-phase-07-3ki-review.md` (lines 197 and 216), or explicitly override their PENDING status with documented rationale (as done for Phase 4 where both were BLOCKED and overridden with Jens approval).

**Expected:** Either:
- Option A: Run `codex exec` command from the wiki file, record verdict (APPROVED or BLOCKED), run `gemini -p` command from wiki file, record verdict. If both APPROVED: update wiki, declare phase gate passed.
- Option B: Jens provides explicit override rationale in the wiki file: "I accept PENDING Codex/Gemini reviews because [reason]" — mirroring the Phase 4 precedent documented in `wiki/decisions/2026-04-09-phase-04-summary.md`.

**Why human:** CLAUDE.md Regel 6 states: "Alle 3 müssen APPROVED geben" and "Bei Dissens: weiterdiskutieren bis Konsens oder Eskalation an Jens". Plan 07-07 was explicitly marked `autonomous: false` with a `checkpoint:human-verify` task of type `gate="blocking"`. The SUMMARY states the checkpoint was "auto-approved per auto_advance=true" — this is inconsistent with the blocking gate specification. The decisions file (`wiki/decisions/2026-04-15-phase-07-geometry-v2-final.md`) itself acknowledges the gap, showing R-5 (3-KI review) as PARTIAL and R-7 (Jens checkpoint) as PENDING in its exit gate table. No automated agent can fulfill this requirement.

---

### Gaps Summary

No technical gaps. All 5 roadmap success criteria are verified by live tests and code inspection:

1. Star mask: 6 MAT branches (SC1 PASS)
2. Crescent mask: 19 MAT branches (SC2 PASS)
3. SAT detects rotated collision correctly (SC3 PASS)
4. Bitmap is pixel-exact at 17 vs 24px non-32-aligned offset (SC4 PASS)
5. Multi-centric places more words in star arms than single-centric (SC5 PASS)

All 9 GEO2 requirements are implemented, tested, and marked complete in REQUIREMENTS.md.

All artifacts are substantive (not stubs): files range from 131 to 602 lines with real algorithmic content.

All key links are wired: MAT → multi_centric, collision stages connected in hierarchy, renderer dual-mode wired to inner_loop.

All 14 git commits cited in the 7 SUMMARY files are verified to exist in the git log.

**The sole open item is the 3-KI process gate** (CLAUDE.md Regel 6): Codex and Gemini reviews are PENDING external execution. This is a process requirement, not a technical defect. The phase is technically complete and production-ready. Only the formal 3-KI sign-off is needed before the phase exit gate can be declared fully closed.

---

_Verified: 2026-04-16T10:30:00Z_
_Verifier: Claude (gsd-verifier)_

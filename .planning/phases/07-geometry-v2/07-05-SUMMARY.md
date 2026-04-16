---
phase: 07-geometry-v2
plan: 05
subsystem: geometry
tags: [bezier, opencv, cv2, pydantic, numpy, contour, glyph, float64, catmull-rom]

# Dependency graph
requires:
  - phase: 04-geometry-v1
    provides: GlyphBBox with pixel_buffer (uint8 H×W numpy array) from rasterize_glyph()
provides:
  - BezierCurve Pydantic model (frozen, float64 (y,x) control points)
  - BezierGlyph Pydantic model (sibling to GlyphBBox, nested contours tuple)
  - glyph_to_bezier() function bridging GlyphBBox pixel buffers to Bezier paths
  - cv2.findContours + approxPolyDP pipeline for contour extraction (D-16)
  - Catmull-Rom to cubic Bezier conversion for smooth paths
affects:
  - 12-production-v1 (SVG/PDF export uses BezierGlyph for sub-millimeter precision)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Sibling model pattern: BezierGlyph is separate from GlyphBBox, not a subclass (D-17)"
    - "cv2 coordinate flip: approx.squeeze(1)[:, ::-1] converts (x,y) → (y,x) at boundary (D-14)"
    - "Catmull-Rom to Bezier: P1_ctrl = P1 + (P2-P0)/6; P2_ctrl = P2 - (P3-P1)/6"

key-files:
  created:
    - packages/engine/src/aerocloud/geometry/bezier.py
    - packages/engine/tests/geometry/unit/test_bezier.py
    - packages/engine/tests/geometry/integration/test_bezier_integration.py
  modified:
    - packages/engine/src/aerocloud/geometry/__init__.py

key-decisions:
  - "D-16 confirmed: cv2.findContours + approxPolyDP is the contour extraction approach (not manual tracing)"
  - "D-17 confirmed: BezierGlyph is a sibling to GlyphBBox — NOT a subclass (frozen Pydantic prevents subclassing)"
  - "D-14 flip applied at cv2 boundary: pts[:, ::-1] converts cv2 (x,y) columns to (y,x) for D-14"
  - "Catmull-Rom to Bezier conversion chosen for smooth C1-continuous paths through polygon vertices"
  - "float64 enforced for all control points (sub-millimeter SVG/PDF precision, T-07-05-03)"

patterns-established:
  - "Coordinate flip pattern: cv2.approxPolyDP().squeeze(1)[:, ::-1].astype(np.float64)"
  - "Empty pixel_buffer guard: if glyph.pixel_buffer.max() == 0 → return empty contours immediately"
  - "Frozen model mutation test: use curve.p0 = value (normal assignment) not object.__setattr__ — Pydantic's __setattr__ raises ValidationError"

requirements-completed:
  - GEO2-09

# Metrics
duration: 18min
completed: 2026-04-16
---

# Phase 7 Plan 05: Bezier Path Representation Summary

**cv2.findContours + Catmull-Rom Bezier extraction for glyph boundaries, with explicit (y,x) coordinate flip verification and float64 sub-millimeter precision**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-04-16T00:00:00Z
- **Completed:** 2026-04-16T00:18:00Z
- **Tasks:** 2 (TDD: RED + GREEN)
- **Files modified:** 4

## Accomplishments

- BezierCurve and BezierGlyph Pydantic v2 frozen models with nested contour tuple structure
- glyph_to_bezier() pipeline: binarize → cv2.findContours(RETR_LIST) → approxPolyDP → coordinate flip → Catmull-Rom → BezierCurve
- cv2 (x,y) → (y,x) coordinate flip applied and verified by dedicated test (T-07-05-01 mitigated)
- 'O' glyph integration test confirms inner hole detection (>= 2 contours via RETR_LIST)
- All 13 tests GREEN; mypy --strict clean; ruff clean; no pre-existing test regressions

## Task Commits

1. **Task 1: RED — Bezier tests (failing)** - `0db6a96` (test)
2. **Task 2: GREEN — implement bezier.py** - `084898a` (feat)

## Files Created/Modified

- `packages/engine/src/aerocloud/geometry/bezier.py` - BezierCurve, BezierGlyph models + glyph_to_bezier() (~130 lines)
- `packages/engine/src/aerocloud/geometry/__init__.py` - Added BezierCurve, BezierGlyph, glyph_to_bezier exports
- `packages/engine/tests/geometry/unit/test_bezier.py` - 10 unit tests (model immutability, coordinate flip, float64, empty buffer, tolerance)
- `packages/engine/tests/geometry/integration/test_bezier_integration.py` - 3 integration tests (real 'A', 'O', 'B' Inter font glyphs)

## Decisions Made

- Catmull-Rom to Bezier conversion chosen over simpler linear interpolation for C1-continuity at polygon vertex junctions, giving smoother paths for SVG/PDF export.
- `cv2.RETR_LIST` used (not RETR_TREE) since BezierGlyph stores all contours flat — no hierarchy needed at this stage.
- `object.__setattr__` is NOT the right way to test Pydantic frozen models — Pydantic's `__setattr__` override raises `ValidationError`; `object.__setattr__` bypasses it. Fixed in deviation below.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Frozen model test used wrong mutation method**
- **Found during:** Task 2 (GREEN — running test_bezier_curve_model_frozen)
- **Issue:** Tests used `object.__setattr__(curve, "p0", value)` which bypasses Pydantic's `__setattr__` override, so no exception was raised even though the model IS frozen.
- **Fix:** Changed both frozen tests to use direct attribute assignment (`curve.p0 = value`) which triggers Pydantic's `__setattr__` → raises `ValidationError`. Updated test to catch `(ValidationError, TypeError)`.
- **Files modified:** packages/engine/tests/geometry/unit/test_bezier.py
- **Verification:** Tests now pass — `ValidationError` is raised on mutation attempt.
- **Committed in:** `084898a` (Task 2 feat commit, tests and impl committed together)

---

**Total deviations:** 1 auto-fixed (Rule 1 — Bug in test mutation method)
**Impact on plan:** Essential correctness fix for the frozen model tests. No scope creep.

## Issues Encountered

None beyond the deviation documented above.

## Known Stubs

None — glyph_to_bezier() is fully wired to real GlyphBBox.pixel_buffer via cv2.

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced. BezierGlyph is internal data model only. Threat mitigations T-07-05-01 (coordinate flip) and T-07-05-03 (float64) are both covered by dedicated tests.

## Next Phase Readiness

- BezierGlyph is ready for Phase 12 SVG/PDF export consumption
- glyph_to_bezier() exported from `aerocloud.geometry` package init
- Integration with Phase 12 Seam Carving + Bezier export (Blueprint Teil X) is the downstream consumer

---
*Phase: 07-geometry-v2*
*Completed: 2026-04-16*

## Self-Check: PASSED

- `packages/engine/src/aerocloud/geometry/bezier.py` — FOUND
- `packages/engine/tests/geometry/unit/test_bezier.py` — FOUND
- `packages/engine/tests/geometry/integration/test_bezier_integration.py` — FOUND
- Commit `0db6a96` — FOUND (RED test commit)
- Commit `084898a` — FOUND (GREEN implementation commit)

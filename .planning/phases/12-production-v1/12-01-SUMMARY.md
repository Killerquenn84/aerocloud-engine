---
phase: 12-production-v1
plan: "01"
subsystem: export
tags: [seam-carving, png-export, boolean-union, shapely, numpy, pytorch, pillow, tdd]

requires:
  - phase: 07-geometry-v2
    provides: BezierCurve and BezierGlyph models used by boolean_union

provides:
  - build_energy_map(): Gaussian-weighted energy map from word positions (PROD-01)
  - find_vertical_seam(): DP O(w*h) optimal seam finder (PROD-02)
  - remove_vertical_seam(): seam removal on 2D and 3D arrays (PROD-02)
  - export_png(): float32 tensor to PNG bytes, RGB and grayscale (PROD-05)
  - bezier_curve_to_points(): De Casteljau tessellation with Shapely coordinate flip
  - glyph_to_polygon(): BezierGlyph to Shapely Polygon with hole support
  - union_glyphs(): boolean union of BezierGlyph list via shapely.ops.unary_union (PROD-06)
  - New dependencies: shapely 2.1.2, scikit-image 0.26.0, slowapi, prometheus-fastapi-instrumentator, sse-starlette

affects:
  - 12-02 (SVG/PDF export — consumes seam carving + boolean union)
  - 12-05 (FastAPI render endpoint — consumes export_png)

tech-stack:
  added:
    - shapely==2.1.2 (GEOS-backed polygon ops)
    - scikit-image==0.26.0 (dev, image helpers)
    - slowapi>=0.1.9 (rate limiting for FastAPI)
    - prometheus-client>=0.25.0 + prometheus-fastapi-instrumentator>=7.1.0
    - opentelemetry-exporter-otlp>=1.41.0
    - sse-starlette>=3.3.4
  patterns:
    - TDD Red-Green per task: tests written before implementation, verified failing
    - Vectorized numpy DP inner loop (no Python for-loop over columns in seam finder)
    - De Casteljau tessellation for deterministic Bezier sampling
    - Lazy imports in export/__init__.py → direct typed imports after both modules implemented
    - DoS guards at function entry (canvas size cap, tessellation n cap)

key-files:
  created:
    - packages/engine/src/aerocloud/export/__init__.py
    - packages/engine/src/aerocloud/export/seam_carving.py
    - packages/engine/src/aerocloud/export/png_export.py
    - packages/engine/src/aerocloud/export/boolean_union.py
    - packages/engine/tests/export/__init__.py
    - packages/engine/tests/export/unit/__init__.py
    - packages/engine/tests/export/unit/test_seam_carving.py
    - packages/engine/tests/export/unit/test_png_export.py
    - packages/engine/tests/export/unit/test_boolean_union.py
  modified:
    - packages/engine/pyproject.toml (added [production] optional group with shapely)
    - apps/api/pyproject.toml (added slowapi, prometheus, otel, sse-starlette)
    - pyproject.toml (added scikit-image to dev dependencies)

key-decisions:
  - "Export __init__.py uses direct typed imports (not lazy wrappers) — mypy strict requires concrete types"
  - "Vectorized DP row step via np.minimum on shifted arrays — avoids O(w*h) Python loop overhead"
  - "De Casteljau tessellation (not adaptive) for deterministic reproducibility in Self-Play training"
  - "union_glyphs returns BaseGeometry directly — no lossy round-trip back to BezierGlyph (research anti-pattern)"
  - "T-12-01-01: canvas_h/w capped at 4096; T-12-01-03: tessellation n capped at 50 (DoS mitigations)"
  - "shapely>=2.1.2 added to engine [production] optional group; installed via uv pip for CI compatibility"

patterns-established:
  - "Export modules: pure computation only, no I/O side effects"
  - "Coordinate convention: engine uses (y,x), Shapely uses (x,y) — flip at the boundary in bezier_curve_to_points"
  - "DoS guards are entry-point validators, not buried logic — placed at top of each public function"

requirements-completed: [PROD-01, PROD-02, PROD-05, PROD-06]

duration: 7min
completed: 2026-04-21
---

# Phase 12 Plan 01: Export Foundations Summary

**Seam carving (Gaussian energy map + DP optimal seam), PNG tensor export, and Bezier boolean union via Shapely — 38 TDD tests, mypy strict clean**

## Performance

- **Duration:** 7 min
- **Started:** 2026-04-21T23:39:23Z
- **Completed:** 2026-04-21T23:46:00Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments

- Implemented seam carving pipeline: `build_energy_map()` (vectorized Gaussian, PROD-01), `find_vertical_seam()` (DP O(w*h) with vectorized row step, PROD-02), `remove_vertical_seam()` (2D/3D array support)
- Implemented `export_png()`: float32 PyTorch tensor → PNG bytes via PIL, RGB and grayscale modes, roundtrip within 1/255 tolerance (PROD-05)
- Implemented boolean union pipeline: `bezier_curve_to_points()` (De Casteljau, (y,x)→(x,y) coordinate flip), `glyph_to_polygon()` (outer ring + holes), `union_glyphs()` via shapely.ops.unary_union (PROD-06)
- All DoS mitigations applied: canvas cap 4096 (T-12-01-01), tessellation cap n=50 (T-12-01-03)
- 38 unit tests across 3 test files, all green; mypy --strict clean on all 4 export modules

## Task Commits

1. **Task 1: Install dependencies + seam carving module (PROD-01, PROD-02)** — `fb86325` (feat)
2. **Task 2: PNG export + boolean union modules (PROD-05, PROD-06)** — `83f394a` (feat)

## Files Created/Modified

- `packages/engine/src/aerocloud/export/__init__.py` — Package root; direct typed exports
- `packages/engine/src/aerocloud/export/seam_carving.py` — build_energy_map, find_vertical_seam, remove_vertical_seam
- `packages/engine/src/aerocloud/export/png_export.py` — export_png (RGB + grayscale)
- `packages/engine/src/aerocloud/export/boolean_union.py` — bezier_curve_to_points, glyph_to_polygon, union_glyphs
- `packages/engine/tests/export/unit/test_seam_carving.py` — 18 tests (energy map, DP seam, seam removal)
- `packages/engine/tests/export/unit/test_png_export.py` — 8 tests (roundtrip, clamping, mode validation)
- `packages/engine/tests/export/unit/test_boolean_union.py` — 12 tests (tessellation, polygon, union)
- `packages/engine/pyproject.toml` — Added `[production]` optional group with shapely>=2.1.2
- `apps/api/pyproject.toml` — Added slowapi, prometheus, otel-otlp, sse-starlette
- `pyproject.toml` — Added scikit-image>=0.26.0 to dev group

## Decisions Made

- Used direct typed imports in `export/__init__.py` instead of lazy wrappers — mypy strict requires concrete types at import time; lazy wrappers produced `unused type: ignore` errors
- Vectorized DP inner loop: `np.minimum(prev, np.minimum(left, right))` with shifted arrays — avoids Python for-loop over width dimension
- De Casteljau closed-form (not recursive) for Bezier tessellation — deterministic, faster than recursive implementation
- `union_glyphs` returns `BaseGeometry` directly (not converted back to `BezierGlyph`) — lossy round-trip is an explicit anti-pattern from research

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed `export/__init__.py` lazy import approach**
- **Found during:** Task 1 (first test run)
- **Issue:** Initial lazy import wrappers in `__init__.py` used `type: ignore[return]` which mypy --strict flagged as unused after resolving the actual types
- **Fix:** Replaced lazy wrappers with direct typed imports; moved to direct imports after both submodules were fully implemented
- **Files modified:** `packages/engine/src/aerocloud/export/__init__.py`
- **Verification:** `uv run mypy packages/engine/src/aerocloud/export/ --strict` — Success
- **Committed in:** `83f394a` (Task 2 commit)

**2. [Rule 3 - Blocking] Installed missing geometry transitive dependencies (cv2, cachetools)**
- **Found during:** Task 2 (test collection for boolean_union)
- **Issue:** `boolean_union.py` imports `BezierGlyph` which pulls in `geometry/__init__.py` → `bezier.py` → cv2; `collision.py` → cachetools — both missing
- **Fix:** `uv pip install opencv-python-headless cachetools blake3 scikit-fmm svgelements reportlab scikit-learn`
- **Files modified:** None (runtime only)
- **Verification:** Test collection succeeded after install
- **Committed in:** n/a (environment fix)

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both auto-fixes required for task completion. No scope creep.

## Issues Encountered

- `shapely.BaseGeometry` does not exist as a top-level import in shapely 2.x; correct path is `shapely.geometry.base.BaseGeometry` — fixed immediately
- `uv sync --all-extras` does not activate package-level optional groups defined as `[production]` in sub-packages — installed shapely via `uv pip install` as workaround

## Known Stubs

None — all functions are fully implemented.

## Threat Flags

None — all threat mitigations from T-12-01-01 (canvas size cap) and T-12-01-03 (tessellation cap) were applied. T-12-01-02 (PNG export tensor input) accepted as-is per threat register.

## Next Phase Readiness

- `seam_carving` and `boolean_union` are ready for Plan 02 (SVG/PDF export via Bezier intersection optimization)
- `export_png` is ready for Plan 05 (FastAPI render endpoint)
- All dependencies (shapely, prometheus stack, sse-starlette) installed in venv

---
*Phase: 12-production-v1*
*Completed: 2026-04-21*

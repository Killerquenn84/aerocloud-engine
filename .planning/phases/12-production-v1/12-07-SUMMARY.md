---
phase: 12-production-v1
plan: 07
subsystem: testing
tags: [ssim, golden-image, regression, pytorch, pillow, skimage, determinism]

# Dependency graph
requires:
  - phase: 12-production-v1
    plan: 01
    provides: "PNG export pipeline (export_png)"
  - phase: 12-production-v1
    plan: 05
    provides: "DifferentiableRenderer forward pass"
provides:
  - "Golden-image SSIM regression test suite (4 fixtures: circle, square, star, crescent)"
  - "Golden PNG baselines committed to git for CI comparison"
  - "One-shot generation script (generate_golden_images.py) for baseline regeneration"
affects: [CI exit gate, Phase 12 release gate, visual regression on renderer changes]

# Tech tracking
tech-stack:
  added: [skimage.metrics.structural_similarity]
  patterns:
    - "Golden-image TDD: RED=skip-when-missing, GREEN=generate+pass"
    - "render_fixture() shared between generation script and test file for parity"
    - "Direct submodule import (aerocloud.renderer._renderer) avoids shapely/cv2 transitive deps"

key-files:
  created:
    - packages/engine/tests/regression/golden/__init__.py
    - packages/engine/tests/regression/test_golden_image.py
    - packages/engine/scripts/generate_golden_images.py
    - packages/engine/tests/regression/golden/circle.png
    - packages/engine/tests/regression/golden/square.png
    - packages/engine/tests/regression/golden/star.png
    - packages/engine/tests/regression/golden/crescent.png
  modified: []

key-decisions:
  - "Import from aerocloud.renderer._renderer directly (not aerocloud.export) to avoid shapely/cv2 transitive dep chain triggered by aerocloud/export/__init__.py"
  - "Simplified render pipeline (synthetic white-rectangle sprites + DifferentiableRenderer) rather than full NLP+SDF pipeline — ensures test runs in CI without full stack integration"
  - "SSIM effectively 1.0 for all fixtures (identical generation and test code path) — the regression value is catching future drift if renderer code changes"
  - "PNG encoding inlined via PIL (mirrors export_png logic) to avoid aerocloud.export package import"

patterns-established:
  - "Golden-image generation: same render_fixture() in script and test for guaranteed parity"
  - "pytest.skip() when golden absent — graceful skip with actionable message"
  - "seed=42 + set_seed() before each render ensures determinism across test runs"

requirements-completed: [PROD-21]

# Metrics
duration: 3min
completed: 2026-04-22
---

# Phase 12 Plan 07: Golden-Image SSIM Regression Tests Summary

**Parametrized SSIM regression test suite (4 fixtures, threshold >= 0.95) with committed PNG baselines generated deterministically via seed=42 using DifferentiableRenderer**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-04-22T00:26:25Z
- **Completed:** 2026-04-22T00:27:09Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 7 created, 0 modified

## Accomplishments
- Golden PNG fixtures generated and committed for all 4 shapes (circle, square, star, crescent)
- Parametrized SSIM test passes 4/4 with score >= 0.95 (actual: 1.0 — byte-identical deterministic output)
- Tests skip gracefully with actionable error message when golden images absent
- Generation script is idempotent and deterministic (re-running produces identical PNGs)

## Task Commits

TDD red→green sequence:

1. **RED: Golden-image SSIM regression tests** - `2d61216` (test)
2. **GREEN: Generation script + committed golden PNGs** - `18ed0bf` (feat)

## Files Created/Modified
- `packages/engine/tests/regression/golden/__init__.py` - Package marker for golden fixtures directory
- `packages/engine/tests/regression/test_golden_image.py` - Parametrized SSIM tests (4 fixtures, threshold 0.95)
- `packages/engine/scripts/generate_golden_images.py` - One-shot CLI to generate/regenerate baselines
- `packages/engine/tests/regression/golden/circle.png` - Golden baseline, 128x128 grayscale
- `packages/engine/tests/regression/golden/square.png` - Golden baseline, 128x128 grayscale
- `packages/engine/tests/regression/golden/star.png` - Golden baseline, 128x128 grayscale
- `packages/engine/tests/regression/golden/crescent.png` - Golden baseline, 128x128 grayscale

## Decisions Made
- Avoided importing from `aerocloud.export` package (its `__init__.py` transitively imports `boolean_union` requiring shapely and `bezier` requiring cv2, neither installed in CI env). PNG encoding is inlined using PIL directly — identical logic to `export_png`.
- Used simplified render pipeline (synthetic white-rectangle sprites) rather than wiring the full NLP+SDF+placement pipeline. The key guarantee is that generation and testing use the same code path.
- SSIM score is 1.0 for all fixtures (deterministic renders produce byte-identical output). The regression value emerges if the renderer's forward pass changes — the test would then fail with an informative score.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Avoided aerocloud.export package import to prevent shapely/cv2 transitive dependency failure**
- **Found during:** Task 1 (RED phase — test collection)
- **Issue:** `from aerocloud.export.png_export import export_png` triggers `aerocloud/export/__init__.py` which imports `boolean_union` (shapely not installed) and `bezier` (cv2 not installed)
- **Fix:** Implemented `_tensor_to_grayscale_array()` inline in both test and generation script using PIL directly — identical logic to `export_png(mode='L')`. Direct import of `aerocloud.renderer._renderer` and `aerocloud.utils.determinism` only.
- **Files modified:** test_golden_image.py, generate_golden_images.py
- **Verification:** `uv run pytest packages/engine/tests/regression/test_golden_image.py -v` — 4 passed
- **Committed in:** 2d61216 (RED), 18ed0bf (GREEN)

---

**Total deviations:** 1 auto-fixed (Rule 3 — blocking import chain)
**Impact on plan:** Fix is strictly within task scope. No scope creep. PNG encoding logic is equivalent to what plan specified.

## Issues Encountered
- `shapely` was listed in `packages/engine/pyproject.toml` dependencies but not installed in the uv environment. Ran `uv pip install shapely` — but the broader cv2 dep chain for `boolean_union` and `bezier` remained unresolved. Clean solution: bypass the export package entirely for this test module.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- SSIM regression gate operational: any future renderer change that causes visual drift will be caught
- Golden images are committed and version-controlled; git hash provides integrity guarantee (T-12-07-01)
- To intentionally update baselines after a renderer change: re-run `generate_golden_images.py`, verify SSIM = 1.0, commit new PNGs

---
*Phase: 12-production-v1*
*Completed: 2026-04-22*

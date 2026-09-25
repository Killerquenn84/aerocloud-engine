---
phase: 05-renderer-v1
plan: "01"
subsystem: renderer
tags: [pytorch, torch, numpy, psutil, sprite-cache, font-registry, rlock, tdd, unit-tests]

# Dependency graph
requires:
  - phase: 04-geometry-v1
    provides: GlyphBBox.pixel_buffer (uint8 ndarray) and AeroCloudBase model pattern
provides:
  - FONT_REGISTRY set[tuple[str, int]] with RLock for thread-safe font pair tracking (REND-04)
  - SPRITE_CACHE dict[tuple[str, int, int], torch.Tensor] with RLock for glyph tensor memoization (REND-03)
  - register_glyph() — idempotent uint8->float32/255 tensor transfer, detached, (1,1,H,W) shape
  - clear_caches() — test utility to reset both module-level caches
  - psutil>=5.9.0 in gpu optional-dependencies for Phase 5 RSS memory tests (D-20)
  - Renderer test infrastructure: conftest with tiny_sprite, cpu_device, sample_pixel_buffer, clear_caches autouse, gpu skip marker
affects:
  - 05-renderer-v1/05-02 (DifferentiableRenderer consumes SPRITE_CACHE + register_glyph)
  - 05-renderer-v1/05-03 (forward pass tests use FONT_REGISTRY to verify registered fonts)
  - 06-inner-loop-v1 (optimizer builds on sprite cache as leaf tensors)

# Tech tracking
tech-stack:
  added:
    - psutil>=5.9.0 (gpu optional-dependency group, RSS memory monitoring in tests)
  patterns:
    - "Module-level caches with threading.RLock — same pattern as Phase 3-4 NLP/Geometry caches"
    - "TDD: RED (ImportError) -> GREEN (13 tests pass) -> no refactor needed"
    - "Sprite tensors are always .detach()'d (data not parameters — prevents autograd graph leaks)"
    - "register_glyph is idempotent: SPRITE_CACHE check inside RLock prevents duplicate tensor creation"

key-files:
  created:
    - packages/engine/src/aerocloud/renderer/__init__.py
    - packages/engine/src/aerocloud/renderer/_sprites.py
    - packages/engine/tests/renderer/__init__.py
    - packages/engine/tests/renderer/conftest.py
    - packages/engine/tests/renderer/unit/__init__.py
    - packages/engine/tests/renderer/unit/test_font_registry.py
    - packages/engine/tests/renderer/unit/test_sprites.py
    - packages/engine/tests/renderer/property/__init__.py
    - packages/engine/tests/renderer/integration/__init__.py
    - packages/engine/tests/renderer/determinism/__init__.py
    - packages/engine/tests/renderer/memory/__init__.py
  modified:
    - packages/engine/pyproject.toml (added psutil to gpu optional-deps)
    - uv.lock (psutil 7.2.2 resolved)

key-decisions:
  - "psutil added to gpu optional-deps group (not core) — only needed for RSS memory tests, not production rendering"
  - "SPRITE_CACHE key is (font_family, size_pt, codepoint) — codepoint included to avoid collisions between different glyphs in same font"
  - "Sprite tensors are detached (.detach()) immediately — sprites are static data, not learnable parameters, prevents autograd graph leaks (Pitfall 3 from RESEARCH.md)"
  - "RLock (reentrant) over Lock — consistent with Phase 3-4 cache pattern, allows same-thread re-entry during complex rendering paths"

patterns-established:
  - "Renderer conftest autouse clear_caches fixture — all renderer tests start with clean cache state"
  - "gpu = pytest.mark.skipif(not torch.cuda.is_available()) marker in conftest — applied to CUDA-only tests in later plans"

requirements-completed:
  - REND-03
  - REND-04

# Metrics
duration: 3min
completed: "2026-04-12"
---

# Phase 5 Plan 01: Renderer-v1 Package Scaffold Summary

**Thread-safe sprite cache (uint8->float32 tensor, (1,1,H,W), detached) and font registration set (RLock) scaffolded with 13 unit tests covering idempotency, cache hit/miss, value conversion, and concurrent registration.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-04-12T20:40:32Z
- **Completed:** 2026-04-12T20:43:05Z
- **Tasks:** 2
- **Files modified:** 11 created + 2 modified

## Accomplishments

- Renderer package skeleton created with psutil in gpu optional-dependencies and all 5 test subdirectory `__init__.py` files
- `_sprites.py` implemented: FONT_REGISTRY set + SPRITE_CACHE dict both with threading.RLock, register_glyph() converting uint8->float32/255 tensor shape (1,1,H,W) fully detached, clear_caches()
- 13 unit tests covering: float32 dtype, correct shape, value range [0,1], exact 128/255 conversion, cache hit identity, cache miss different objects, requires_grad=False, clear_caches empties both caches, single/duplicate/multiple font registration, 100-call count stability, 16-thread concurrent safety
- mypy --strict: 0 errors on renderer package

## Task Commits

Each task was committed atomically:

1. **Task 1: Renderer package skeleton + psutil + test conftest** - `a23714d` (feat)
2. **Task 2: Sprite cache + font registry with RLock + 13 unit tests (TDD)** - `82c4e01` (feat)

**Plan metadata:** _(docs commit follows)_

_Note: Task 2 was TDD — RED phase confirmed ImportError, GREEN phase all 13 tests pass._

## Files Created/Modified

- `packages/engine/src/aerocloud/renderer/__init__.py` - Public API exports (FONT_REGISTRY, SPRITE_CACHE, register_glyph, clear_caches)
- `packages/engine/src/aerocloud/renderer/_sprites.py` - Sprite cache + font registry with RLock, register_glyph, clear_caches
- `packages/engine/tests/renderer/conftest.py` - Shared fixtures: tiny_sprite, cpu_device, sample_pixel_buffer, clear_caches autouse, gpu skip marker
- `packages/engine/tests/renderer/unit/test_font_registry.py` - 5 font registry tests (single, duplicate, multiple, 100-call, thread safety)
- `packages/engine/tests/renderer/unit/test_sprites.py` - 8 sprite cache tests (dtype, shape, range, exact value, cache hit/miss, detach, clear)
- `packages/engine/pyproject.toml` - Added psutil>=5.9.0 to gpu optional-dependencies

## Decisions Made

- psutil added to gpu optional-deps group (not core deps) since it is only needed for Phase 5 RSS memory tests (D-20), not required for production rendering
- SPRITE_CACHE key includes codepoint to prevent collisions between different glyphs in the same font at the same size
- Sprites are always detached — static data, not learnable parameters, preventing autograd graph accumulation (Pitfall 3)
- RLock chosen over Lock for consistency with Phase 3-4 cache patterns and to support same-thread re-entry in complex rendering paths

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None — psutil installed cleanly (7.2.2), mypy strict passes, all 13 tests green on CPU.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Renderer package ready with SPRITE_CACHE and FONT_REGISTRY public API
- Plan 02 (DifferentiableRenderer) can import from `aerocloud.renderer` immediately
- Conftest gpu skip marker ready for CUDA-gated tests in plans 02-04
- psutil available for RSS memory tests (D-20) in memory test suite

## Known Stubs

None — no placeholder data or TODO stubs in shipped code.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced. Sprite cache contains only glyph rendering data (no PII, no external input reaching this layer in v1 per T-05-01 threat register disposition).

## Self-Check: PASSED

All created files exist on disk. Both task commits (a23714d, 82c4e01) confirmed in git log.

---
*Phase: 05-renderer-v1*
*Completed: 2026-04-12*

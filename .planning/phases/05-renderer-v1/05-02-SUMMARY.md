---
phase: 05-renderer-v1
plan: "02"
subsystem: renderer
tags: [pytorch, nn-module, differentiable-renderer, grid-sample, affine-grid, alpha-compositing, tdd, unit-tests]

# Dependency graph
requires:
  - phase: 05-renderer-v1
    plan: "01"
    provides: SPRITE_CACHE, register_glyph, conftest fixtures (tiny_sprite, cpu_device, clear_caches autouse)
provides:
  - DifferentiableRenderer(nn.Module) — packed (N,4) nn.Parameter with [y,x,scale,rotation] per word (REND-01)
  - forward(canvas_h, canvas_w) — differentiable forward pass via F.affine_grid + F.grid_sample (REND-02)
  - Alpha-over compositing: density = 1 - prod(1 - alpha_i) (D-04)
  - Rotation clamping to [-pi, pi] via torch.remainder (D-09)
  - 8px forward pass produces non-NaN output on CPU (REND-05)
  - 8 unit tests for affine transforms + 11 unit tests for compositing = 19 total
affects:
  - 05-renderer-v1/05-03 (integration tests build on DifferentiableRenderer)
  - 06-inner-loop-v1 (optimizer calls renderer.forward() + backward())

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "nn.Parameter for packed (N,4) tensor — single learnable tensor per renderer instance"
    - "F.affine_grid + F.grid_sample with align_corners=False (Pitfall 2 from RESEARCH.md)"
    - "Alpha-over compositing loop: density = 1 - (1-density)*(1-warped)"
    - "TDD: RED (ImportError) -> GREEN (19 tests pass) -> no refactor needed"
    - "Sprite tensors stored as plain list (not nn.ParameterList) — data not gradients"

key-files:
  created:
    - packages/engine/src/aerocloud/renderer/_renderer.py
    - packages/engine/tests/renderer/unit/test_affine.py
    - packages/engine/tests/renderer/unit/test_compositing.py
  modified:
    - packages/engine/src/aerocloud/renderer/__init__.py (added DifferentiableRenderer export)

key-decisions:
  - "align_corners=False used for both affine_grid and grid_sample — ensures pixel-edge semantics (Pitfall 2 per RESEARCH.md)"
  - "Rotation clamped via torch.remainder(theta + pi, 2*pi) - pi (D-09) — keeps gradients well-behaved across wrapping"
  - "Sprites stored as plain list[torch.Tensor], not nn.ParameterList — sprites are static data (pre-rasterized), not learnable. Prevents autograd tracking sprite data as parameters"
  - "Single nn.Parameter of shape (N,4) per D-05 — all word params in one tensor simplifies optimizer API in Phase 6"

requirements-completed:
  - REND-01
  - REND-02
  - REND-05

# Metrics
duration: 2min
completed: "2026-04-12"
---

# Phase 5 Plan 02: DifferentiableRenderer nn.Module Summary

**DifferentiableRenderer(nn.Module) implemented with packed (N,4) nn.Parameter, full differentiable forward pass via affine_grid+grid_sample (align_corners=False), alpha-over compositing, and rotation clamping. 19 unit tests (8 affine + 11 compositing) all pass on CPU.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-04-12T20:45:12Z
- **Completed:** 2026-04-12T20:47:11Z
- **Tasks:** 1 (TDD: RED -> GREEN)
- **Files modified:** 3 created + 1 modified

## Accomplishments

- RED phase: wrote 8 tests in `test_affine.py` and 11 tests in `test_compositing.py` — all failed with ImportError confirming clean TDD Red
- GREEN phase: implemented `_renderer.py` with `DifferentiableRenderer(nn.Module)`:
  - Constructor validates (N,4) shape, stores packed `nn.Parameter`, copies sprites to device as plain tensors
  - `forward(canvas_h, canvas_w)` iterates over N sprites, builds 2x3 affine matrix per sprite, calls `F.affine_grid` + `F.grid_sample` both with `align_corners=False`, accumulates density via alpha-over formula
  - Rotation clamped to [-pi, pi] via `torch.remainder(theta + pi, 2*pi) - pi` (D-09)
- Updated `__init__.py` to export `DifferentiableRenderer`
- mypy --strict: 0 errors on `_renderer.py`
- All 19 new tests + all 13 existing renderer tests pass (32 total)

## Task Commits

1. **Task 1: DifferentiableRenderer nn.Module with affine forward pass (TDD)** - `441d029` (feat)

## Files Created/Modified

- `packages/engine/src/aerocloud/renderer/_renderer.py` — DifferentiableRenderer class with full forward pass
- `packages/engine/tests/renderer/unit/test_affine.py` — 8 tests: identity center, identity corner, rotation identity, scale, rotation 90deg, combined scale+rotation, align_corners=False semantics, rotation clamping
- `packages/engine/tests/renderer/unit/test_compositing.py` — 11 tests: single sprite, empty canvas, output shape, dtype, two overlapping sprites alpha-over (0.75 formula check), non-overlapping, output range [0,1], 8px non-NaN (REND-05), parameter count=1, parameter shape (N,4), requires_grad=True (REND-01)
- `packages/engine/src/aerocloud/renderer/__init__.py` — Added DifferentiableRenderer to exports

## Decisions Made

- `align_corners=False` enforced in both `F.affine_grid` and `F.grid_sample` — this is the correct pixel-edge convention per Pitfall 2 in RESEARCH.md; `align_corners=True` would cause half-pixel misalignment at canvas boundaries
- Rotation clamping via `torch.remainder` keeps parameter gradients well-defined at the wrap-around point (D-09 from CONTEXT.md)
- Sprites stored as `list[torch.Tensor]` (not `nn.ParameterList`) — sprites are static pre-rasterized glyph data; registering them as parameters would leak autograd graph and cause optimizer to update sprite pixel values erroneously

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None — PyTorch grid_sample/affine_grid API used cleanly, mypy strict passes, all tests green in first GREEN attempt.

## Known Stubs

None — `DifferentiableRenderer.forward()` is fully implemented with no placeholder values or TODO stubs.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes. `DifferentiableRenderer` is a pure in-process PyTorch module with no external surface (T-05-04, T-05-05, T-05-06 all accepted per plan threat register).

## Self-Check: PASSED

- `packages/engine/src/aerocloud/renderer/_renderer.py` — EXISTS
- `packages/engine/tests/renderer/unit/test_affine.py` — EXISTS
- `packages/engine/tests/renderer/unit/test_compositing.py` — EXISTS
- `packages/engine/src/aerocloud/renderer/__init__.py` — EXISTS (modified)
- Commit `441d029` confirmed in git log

---
*Phase: 05-renderer-v1*
*Completed: 2026-04-12*

# Phase 5: Renderer-v1 — Close-Out Summary

**Date:** 2026-04-12
**Phase:** 05-renderer-v1
**Status:** Implementation complete — awaiting 3-KI review close-out

---

## Phase Summary

Phase 5 delivered a pure PyTorch differentiable 2D sprite compositor (`DifferentiableRenderer`)
that serves as the core rendering primitive for the AeroCloud inner optimization loop.
4 plans, 8 tasks, 48 tests, 0 deferred stubs.

---

## What Was Built

### Package: `aerocloud.renderer`

A new `packages/engine/src/aerocloud/renderer/` package providing:

1. **`DifferentiableRenderer(nn.Module)`** — The core deliverable.
   - Accepts Phase 4 PlacementResult placement coordinates and pre-rasterized glyph sprites
   - Stores learnable `(N, 4)` parameter tensor `[y, x, scale, rotation]` as `nn.Parameter`
   - Forward pass: affine_grid + grid_sample + alpha-over compositing → density tensor
   - Output: `(1, 1, H, W)` float32 in [0, 1] consumed by Phase 6 loss functions
   - backward() propagates gradients to all 4 parameter columns per word

2. **`SPRITE_CACHE` + `FONT_REGISTRY`** — Thread-safe module-level caches with RLock
   - Idempotent glyph registration via `register_glyph()`
   - Stable across 100+ renders (REND-04 verified)

---

## Phase 5 Plans Executed

| Plan | Title | Tasks | Tests | Key Deliverable |
|------|-------|-------|-------|-----------------|
| 05-01 | Renderer Package Scaffold | 2 | 13 | `_sprites.py` + SPRITE_CACHE + FONT_REGISTRY + conftest |
| 05-02 | DifferentiableRenderer | 1 | 19 | `_renderer.py` full forward pass |
| 05-03 | Test Pyramid Completion | 1 | 16 | property + integration + determinism + RSS tests |
| 05-04 | 3-KI Review + Wiki Update | 1 | — | Code review + wiki documentation |

---

## Requirements Satisfied

| Req | Description | Satisfied |
|-----|-------------|-----------|
| REND-01 | `nn.Parameter` (N,4) with `requires_grad=True` | Yes (05-02) |
| REND-02 | `forward(h,w) -> Tensor[1,1,H,W]` differentiable | Yes (05-02) |
| REND-03 | SPRITE_CACHE dict stable across renders | Yes (05-01) |
| REND-04 | FONT_REGISTRY set stable across renders | Yes (05-01) |
| REND-05 | 8px forward pass non-NaN on CPU | Yes (05-02) |
| REND-06 | backward() produces non-zero gradient on params | Yes (05-03) |

---

## Technical Decisions

### D-01: Pure PyTorch over nvdiffrast

The most consequential decision of Phase 5. nvdiffrast is a 3D mesh rasterizer; our
problem is 2D sprite compositing. Using `grid_sample` delivers the same mathematical
result in ~100 lines of pure Python with zero external dependencies.

See: `wiki/knowledge/phase-5-renderer-design.md` for full rationale.

### D-02: align_corners=False

Pixel-edge semantics per RESEARCH.md Pitfall 2. Both `affine_grid` and `grid_sample`
use the same value consistently.

### D-04: Alpha-over compositing

`density = 1.0 - (1.0 - density) * (1.0 - warped)` — Porter-Duff over operator,
differentiable, numerically stable at v1 scale.

### D-05: Packed (N,4) nn.Parameter

Single tensor for all word parameters. Simplifies Phase 6 Adam optimizer API.

---

## Test Pyramid Summary

```
48 renderer tests (target was >= 40 per D-22)

Unit tests:        32  (sprite cache, font registry, affine transforms, compositing)
Property tests:     7  (hypothesis: random params, backward, gradients)
Integration tests:  3  (Phase4->Phase5 end-to-end gradient flow, REND-06)
Determinism tests:  3  (byte-identical output over 10 runs, D-18)
RSS tests:          3  (< 50 MiB delta over 100 iterations, D-20)
```

All 48 tests pass on CPU. GPU tests gated behind `@pytest.mark.gpu`.

---

## Deviations from Plan

### Phase 03 Auto-Fixes (Rule 1 — Bug)

1. `DropReason.OUTSIDE_MASK` → `DropReason.NO_FEASIBLE_ANCHOR` (enum value does not exist)
2. `set_seed(42, warn_only=True)` → `set_seed(42)` (function has no `warn_only` parameter)

Both were plan template errors, not bugs in production code.

---

## Known Deferred Items

### Phase 12 (Production Hardening)
- N upper bound guard (`MAX_WORDS = 1000`) — DoS protection
- LRU eviction on sprite cache — memory management for multi-session rendering

### Phase 6/7 (Pixel-Accurate Placement)
- align_corners=False coordinate correction (half-pixel systematic offset)
  Current formula: `x_n = (x_i / (canvas_w / 2.0)) - 1.0`
  Corrected formula: `x_n = (2.0 * x_i / canvas_w) - 1.0 + (1.0 / canvas_w)`

---

## 3-KI Review Status

| Reviewer | Verdict |
|----------|---------|
| Claude Code | APPROVED (2026-04-12) |
| Codex CLI | PENDING |
| Gemini CLI | PENDING |

Phase 5 is marked COMPLETE in ROADMAP.md + STATE.md after all 3 reviewers APPROVED
and Jens confirms.

---

## What Phase 6 Gets

Phase 6 Inner Loop-v1 receives:
- `DifferentiableRenderer` with `model.parameters()` API ready for Adam optimizer
- `forward(canvas_h, canvas_w)` with variable resolution support (Coarse-to-Fine)
- `backward()` produces non-zero gradients on all 4 columns (y, x, scale, rotation)
- RSS-stable rendering (< 50 MiB / 100 iterations baseline)
- Deterministic output under `set_seed(42)` for reproducibility

Phase 6 scope (NOT Phase 5):
- Loss functions (L_wmse, L_overlap, L_fidelity, L_temporal)
- Adam optimizer integration
- Coarse-to-Fine resolution scheduling
- Gradient checkpointing at 128px+

---

## Duration

- Phase 5 total: ~8 minutes (Plans 01-03 execution + Plan 04 review/wiki)
- Plans 01-03: ~8 min implementation (2026-04-12)
- Plan 04: ~5 min review + wiki (2026-04-12)

---

*wiki/discussions/2026-04-12-phase-5-summary.md*
*Phase: 05-renderer-v1 | Created: 2026-04-12*

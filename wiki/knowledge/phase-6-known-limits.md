# Phase 6 Inner Loop-v1 — Known Limits

**Created:** 2026-04-14
**Source:** 3-KI Code Review (Claude + Codex + Gemini)

## F-3: Double Forward Pass per Epoch (~2x Overhead)

**What:** `compute_additive_density()` duplicates the renderer's warp logic (affine_grid + grid_sample) for every epoch. This means two full differentiable forward passes per epoch instead of one.

**Impact:** ~1.8-2.1x wall-clock per epoch. ~40-60 MB additional peak VRAM at 128x128 with N=200 sprites.

**Why deferred:** Requires renderer API change to produce both alpha-over and additive output in a single pass. Phase 7 Geometry-v2 extends the renderer anyway — natural place for this fusion.

**Phase 7 mitigation:** Add `DifferentiableRenderer.forward(mode='both')` returning `(density, additive_density)` tuple. Delete `compute_additive_density()` function entirely (also resolves F-10).

## F-9: No Thread-Safety on Shared Renderer

**What:** `InnerLoop.optimize()` mutates `renderer.params` in-place via Adam. Concurrent use of one renderer instance from multiple threads is a race condition on both CPU and CUDA.

**Impact:** Data corruption if two threads share a renderer.

**Why deferred:** v1 deployment uses Celery with `concurrency=1` (single worker per queue). Renderer is instantiated per-job, not shared.

**Deployment constraint:** Do NOT set Celery `concurrency > 1` without first adding per-renderer mutex or clone-per-run pattern.

**Phase 12 mitigation:** Either clone renderer per `optimize()` call, or add `threading.Lock` and document renderer as single-owner.

## F-10: Private Coupling in compute_additive_density

**What:** `loss.py` reaches into `renderer._sprites`, `renderer.params`, `renderer._device` — coupling to private internals.

**Impact:** Any renderer internal change silently breaks the additive density computation.

**Why deferred:** Resolved automatically when F-3 is fixed (the standalone function gets deleted, renderer owns both compositing modes).

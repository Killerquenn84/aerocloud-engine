# Phase 5: Renderer-v1 - Discussion Log (Auto Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-04-12
**Phase:** 05-renderer-v1
**Mode:** discuss (--auto)
**Areas analyzed:** Rasterization Backend, Tensor Architecture, Glyph-Sprite Pipeline, Determinism + Memory

## Auto-Selected Decisions

### Rasterization Backend
| Question | Selected | Reason |
|----------|----------|--------|
| Which soft-rasterization library? | Pure PyTorch 2D (grid_sample + affine_grid) | nvdiffrast/PyTorch3D are 3D mesh rasterizers — overkill for 2D sprite compositing. grid_sample is native PyTorch, zero deps, full CPU fallback. |
| CPU fallback? | Yes, mandatory | PROJECT.md constraint: "Engine must run (slower) without GPU for development and CI" |
| Compositing operator? | Alpha-over with soft max | Differentiable, handles overlap, standard in 2D compositing |

### Tensor Architecture
| Question | Selected | Reason |
|----------|----------|--------|
| Per-word vs packed tensors? | Packed (N,4) tensor | Efficient batch update for Adam optimizer |
| Phase 4 PlacementResult feed-in? | PlacedWord (y,x) as initial positions, scale=1.0, rotation=0.0 | Phase 4 output is warm-start seed |
| Coordinate convention? | (y, x) internally | D-14 carry-forward, matches PyTorch (H,W) convention |
| Scale type? | Uniform (single scalar) | Anisotropic deferred to Phase 7 |
| Rotation representation? | Radians, clamped [-pi, pi] | Standard, prevents unbounded growth |

### Glyph-Sprite Pipeline
| Question | Selected | Reason |
|----------|----------|--------|
| Atlas vs individual sprites? | Individual sprites for v1 | Simpler, < 200 words, atlas deferred to Phase 12 |
| GPU transfer method? | torch.from_numpy + float32 normalize + .to(device), cached in module dict | Efficient, one-time transfer per render request |
| Font registration Set? | Module-level set of (family, size_pt) tuples | REND-04 requires stable count after first render |

### Determinism + Memory
| Question | Selected | Reason |
|----------|----------|--------|
| CUDA OOM strategy? | 8px coarse resolution only in v1 | Phase 6 adds Coarse-to-Fine; v1 is proof-of-concept |
| RSS stability? | Assert delta < 50 MiB over 100 renders | Catches sprite tensor and font leaks |
| Gradient checkpointing? | Not needed in v1 | 8px resolution is tiny |

## Corrections Made

No corrections — all assumptions auto-confirmed with recommended defaults.

## Prior Context Applied

- Phase 4 D-14: (y, x) canonical ordering → carried into D-07
- Phase 4 D-09: SDF sign convention positive=inside → noted for Phase 6 integration
- Phase 4 D-32: GlyphBBox with pixel_buffer uint8 → drives D-11 transfer path
- Phase 4 D-43: PlacementResult contract → drives D-06 initialization
- Phase 1 set_seed() with warn_only=True → D-18 confirms sufficient
- PROJECT.md: CPU fallback mandatory → D-03
- PROJECT.md: torch==2.7.1 pinned → no version concerns

## Key Design Insight

nvdiffrast and PyTorch3D solve a fundamentally different problem (3D mesh → 2D screen)
than what Phase 5 needs (2D sprite + affine → 2D canvas). Using torch.nn.functional.grid_sample
+ affine_grid provides native PyTorch differentiable spatial transforms with:
- Zero external dependencies
- Full CPU fallback
- Trivial gradient flow to position/scale/rotation parameters
- ~150-250 lines of code total

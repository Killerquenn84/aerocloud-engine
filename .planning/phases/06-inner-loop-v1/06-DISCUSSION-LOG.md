# Phase 6: Inner Loop-v1 - Discussion Log (Auto Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.

**Date:** 2026-04-14
**Phase:** 06-inner-loop-v1
**Mode:** discuss (--auto)
**Areas analyzed:** Loss Functions, Adam Optimizer, Coarse-to-Fine Pipeline, Convergence Detection, Memory Hygiene

## Auto-Selected Decisions

### Loss Functions
| Question | Selected | Reason |
|----------|----------|--------|
| Architecture? | Separate function per term + combined total | Modular, testable, Phase 9 reuses individual terms |
| L_wmse formula? | mean((sdf_positive * (1-density))²) | Blueprint Teil V |
| L_overlap formula? | mean(ReLU(density_additive - 1.0)²) | Blueprint spec, needs additive not alpha-over |
| L_fidelity formula? | 1 - cos_sim(S_ref, S_current) | Blueprint spec, frozen NLP weights |
| L_temporal? | Implement with lambda=0.0 default | No live feeds in v1, structural placeholder |
| Default weights? | alpha=1.0, beta=10.0, gamma=0.1, lambda=0.0 | Blueprint + overlap needs stronger penalty |

### Optimizer
| Question | Selected | Reason |
|----------|----------|--------|
| Which optimizer? | torch.optim.Adam with Blueprint params | Standard, no customization needed |
| Gradient clipping? | clip_grad_norm_ max_norm=1.0 | INNER-07 stability requirement |

### Coarse-to-Fine
| Question | Selected | Reason |
|----------|----------|--------|
| Stages? | [8, 32, 128, target] | INNER-08 exact spec |
| Epochs per stage? | 100 max, early termination via convergence | Balance speed and quality |
| SDF handling? | Downsample via interpolate(bilinear) | Consistent with Phase 4 float32 SDF |

### Convergence
| Question | Selected | Reason |
|----------|----------|--------|
| Detection method? | Rolling window 10 epochs, relative epsilon 0.001 | Simple, robust |
| Min epochs? | 20 before checking | Warm-up period |

### Memory
| Question | Selected | Reason |
|----------|----------|--------|
| empty_cache timing? | Between stages, not per-epoch | INNER-10 spec |
| Gradient zeroing? | zero_grad(set_to_none=True) | Memory efficient |
| Metric logging? | .detach().item() always | INNER-10 spec |

## Prior Context Applied

- Phase 5: DifferentiableRenderer forward(canvas_h, canvas_w) → variable resolution support
- Phase 5: nn.Parameter(N,4) [y, x, scale, rotation] → optimizer target
- Phase 4: compute_sdf() float32 positive=inside → L_wmse weight
- Phase 3: Zipf-normalized weights → L_fidelity reference
- Phase 1: set_seed() → determinism

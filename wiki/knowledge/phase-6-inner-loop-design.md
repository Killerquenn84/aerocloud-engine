# wiki/knowledge/phase-6-inner-loop-design.md

> Phase 06-inner-loop-v1 Design Decisions
> Recorded: 2026-04-14

---

## Overview

Phase 6 built the differentiable optimization loop ("inner loop") of the AeroCloud dual-loop architecture. The inner loop takes Phase 5's DifferentiableRenderer and optimizes word placement parameters via gradient descent.

**Output:** 4-part composite loss, Adam optimizer integration, Coarse-to-Fine resolution pipeline, convergence detection, memory hygiene — 56 tests green.

---

## Why Additive vs Alpha-Over for L_overlap

**Decision D-03:** L_overlap uses ADDITIVE compositing, not the renderer's alpha-over compositing.

### Problem

The renderer's `forward()` uses alpha-over compositing:
```
output[pixel] = sprite_1[pixel] + (1 - sprite_1[pixel]) * sprite_2[pixel]
```
This produces values in `[0, 1]` — it **caps at 1.0**. Two fully overlapping sprites still produce density = 1.0, not 2.0.

Therefore the renderer output cannot detect overlaps. `ReLU(alpha_over_density - 1.0)` would always be 0.

### Solution

`compute_additive_density` uses SUM compositing:
```
output[pixel] = sprite_1[pixel] + sprite_2[pixel] + ...
```
Two overlapping sprites produce density > 1.0 (e.g., 1.5 or 2.0). `ReLU(additive - 1.0)^2` correctly penalizes the overlap.

### Cost

Double forward pass per epoch: one alpha-over (for L_wmse gradient) and one additive (for L_overlap gradient). At 8px stages this is negligible. At 128px with N=200, this is significant. Phase 12 may optimize with a combined pass.

### Alternative considered (rejected)

Adding an `additive=True` parameter to `renderer.forward()`. Rejected because it would mix concerns (rendering logic vs. loss computation logic). The renderer is a Phase 5 artifact with a fixed contract.

---

## Why Rolling-Window Convergence (not absolute threshold)

**Decision D-14:** Rolling window relative range vs. absolute loss threshold.

### Absolute threshold (rejected)

`if loss < 0.01: converge` — problem: the absolute loss value depends on canvas resolution (more pixels = larger sum) and loss weight scale (beta=10 amplifies L_overlap). No single threshold works across all configurations.

### Relative range (adopted)

```
relative_range = (max_window - min_window) / max(|max_window|, 1e-8)
```

Measures *how much the loss is changing* relative to its current magnitude. Scale-invariant: works whether loss is 0.001 or 1000.

### Window size (10 epochs) + warmup (20 epochs)

- Window 10: enough history to smooth out epoch-to-epoch noise
- Warmup 20: prevents false-early-convergence in the first few epochs where Adam's momentum hasn't built up

### Edge case: plateau at 0.0

If loss somehow reaches 0.0 exactly (unlikely but possible), `scale = 1e-8`, `range = 0`, ratio = 0 < epsilon → `True` (converged). Correct behavior.

---

## Coarse-to-Fine: Why 4 Stages [8, 32, 128, target]

**Decision D-10:**

### Purpose

Starting optimization at full resolution (e.g., 512x512) is slow and prone to local minima. The 8px stage provides:
1. Fast exploration (8x8 = 64 pixels vs 512x512 = 262,144)
2. Smooth loss landscape at low resolution (fewer local minima)
3. Warm-start for subsequent stages: good approximate solution carries over

### Stage filtering (Assumption A2)

`_build_stage_schedule` filters out stages >= target. If target=16, using [8, 32, 128] would waste compute on 32px and 128px which are larger than the target. The filter ensures monotonically increasing resolution toward target.

### Non-square SDF

`stage_h == stage_w = res` (square stages). This is a known v1 simplification. For non-square masks (e.g., 512x256), both stages use the square max dimension. Phase 7 will address rectangular stage support.

---

## Memory Hygiene Rationale

**Decisions D-16..D-18**

| Practice | Why Critical |
|----------|-------------|
| `.detach().item()` for loss logging | `l_total` retains the full computation graph through the entire optimizer epoch. Appending it to a list would keep ALL intermediate activations alive (N * 4 affine grids, N density maps) for the duration of training. For N=200 words at 128px, this is ~200 * 128 * 128 * 4 bytes = 13 MiB per epoch, times 100 epochs = 1.3 GiB accumulation. |
| `zero_grad(set_to_none=True)` | PyTorch default `zero_grad()` allocates zero tensors for gradients. `set_to_none=True` frees the gradient tensor after each step, saving memory proportional to N parameters. |
| `torch.cuda.empty_cache()` after stages | GPU memory fragmentation between stages. After the 8px stage completes, the 8px tensors are no longer needed but the CUDA allocator may hold them in its pool. `empty_cache()` returns them to the OS. |
| Fresh Adam per stage | Adam accumulates first and second moment estimates. At stage transition, the momentum from the 8px stage is no longer valid for 32px (different resolution, different loss landscape). Fresh Adam avoids gradient momentum drift. |

---

## Test Pyramid (D-22): Why 5 Layers

| Layer | Count | Purpose |
|-------|-------|---------|
| Unit tests | 38 | Verify each function's known input → exact output |
| Integration tests | 5 | Verify full pipeline converges, determinism, stage filtering |
| Property tests (hypothesis) | 7 | Verify no NaN/Inf across 200 random inputs |
| Determinism tests | 3 | Verify same seed → identical loss curves (10 runs) |
| Memory tests | 3 | Verify RSS < 50 MiB over 100 calls |

Total: 56 tests (target: >= 35)

The property tests + determinism tests are the "adversarial layer" — they catch failure modes that unit tests cannot find by exhaustive random search.

---

## Known Limitations (v1)

### L_overlap for N=1

For N=1 (single word), `compute_l_overlap` always returns 0.0 (a single sprite cannot overlap itself). This means the optimizer has no overlap penalty for single-word optimization. L_wmse becomes the sole driving force, which is correct behavior.

### SDF downsampling at 8px

Downsampling a 512px SDF to 8px loses high-frequency detail. The zero-crossing (shape boundary) may shift by ±1 pixel at 8px. This is acceptable for the coarse stage — the 32/128px stages recover the precision.

### Phase 12 Production Gaps

The following Phase 6 limitations MUST be addressed before production deployment:
1. **N upper bound:** No guard against N > 200 (DoS risk with large affine grid computations)
2. **max_epochs upper cap:** No `le=1000` constraint (DoS risk from misconfigured config)
3. **Wall-clock timeout:** No absolute timeout on `optimize()` (Celery 30s default may be exceeded)
4. **Auth chain:** InnerLoop receives renderer.params without verifying shop ownership. Phase 12 Celery task must enforce the trust chain from Shopify session → optimize() call.

---

## Blueprint Math Reference

Phase 6 implements Blueprint Teil V (Inner Loop) formulas exactly:

```
L_total = alpha * L_wmse + beta * L_overlap + gamma * L_fidelity + lambda_ * L_temporal

L_wmse     = mean((clamp(sdf, min=0) * (1 - density))^2)
L_overlap  = mean(ReLU(density_additive - 1.0)^2)
L_fidelity = 1 - cosine_similarity(s_ref, params[:, 2])
L_temporal = mean((params_current[:, :2] - params_initial[:, :2])^2)
```

Adam parameters: `lr=0.001, betas=(0.9, 0.999), eps=1e-8` (Blueprint Teil V, INNER-06).
Gradient clipping: `max_norm=1.0` (INNER-07).

---

*Phase 06-inner-loop-v1 — Design decisions recorded 2026-04-14*

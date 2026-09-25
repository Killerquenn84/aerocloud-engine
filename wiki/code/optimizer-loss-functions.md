# wiki/code/optimizer-loss-functions.md

> Module: `packages/engine/src/aerocloud/optimizer/loss.py`
> Module: `packages/engine/src/aerocloud/optimizer/convergence.py`
> Phase: 06-inner-loop-v1
> Created: 2026-04-14

---

## Overview

The loss module implements the 4-part composite loss function from the AeroCloud Blueprint (Teil V):

```
L_total = alpha * L_wmse + beta * L_overlap + gamma * L_fidelity + lambda_ * L_temporal
```

Each term is a standalone function returning a scalar tensor. This enables Phase 9 MAP-Elites to reuse individual terms as quality metrics (D-01).

---

## Loss Functions

### `compute_l_wmse(density, sdf) -> torch.Tensor`

**Weighted Mean Squared Error loss (D-02) — Boundary Fitness**

Penalizes uncovered interior pixels, weighted by their distance from the silhouette boundary.

**Formula:**
```
L_wmse = mean((clamp(sdf, min=0) * (1 - density))^2)
```

**Mathematical properties:**
- `L_wmse >= 0` always (squared term)
- `L_wmse = 0` when the interior is fully covered (density=1 at all positive SDF pixels)
- Exterior pixels (sdf < 0) contribute exactly 0 via the clamp — they cannot drive the optimizer to over-extend
- SDF magnitude serves as importance weight: pixels deeper inside the shape are penalized more
- Gradient flows through `density` (from DifferentiableRenderer params)

**Input shapes:**

| Argument | Shape | Dtype | Range |
|----------|-------|-------|-------|
| `density` | `(1, 1, H, W)` | float32 | [0, 1] (alpha-over output) |
| `sdf` | `(1, 1, H, W)` | float32 | any real (positive = inside) |

**Returns:** Scalar tensor `>= 0`.

**Example:**
```python
sdf = torch.tensor([[[[1.0, -1.0], [1.0, -1.0]]]])  # 2 inside, 2 outside
density = torch.zeros(1, 1, 2, 2)
loss = compute_l_wmse(density, sdf)
# Interior pixels: (1.0 * (1-0))^2 = 1.0, exterior: 0
# mean([1.0, 0.0, 1.0, 0.0]) = 0.5
assert abs(loss.item() - 0.5) < 1e-6
```

---

### `compute_l_overlap(additive_density) -> torch.Tensor`

**Primitive Overlap loss (D-03) — Anti-Collision**

Penalizes pixels where multiple sprites overlap. Uses additive (not alpha-over) density, so overlapping sprites produce values > 1.0.

**Formula:**
```
L_overlap = mean(ReLU(density - 1.0)^2)
```

**Mathematical properties:**
- `L_overlap = 0` exactly when `additive_density <= 1.0` everywhere
- `L_overlap > 0` only at pixels where sprites overlap (density > 1.0)
- Squared ReLU: smooth, differentiable, zero plateau below threshold
- Gradient is zero where no overlap, proportional to excess density where overlap

**Input shapes:**

| Argument | Shape | Dtype | Range |
|----------|-------|-------|-------|
| `additive_density` | `(1, 1, H, W)` | float32 | [0, +∞) — can exceed 1.0 |

**Key difference from alpha-over:** L_overlap requires ADDITIVE compositing (sum of sprite contributions). The renderer's `forward()` uses alpha-over (caps at 1.0 per pixel). Use `compute_additive_density()` helper to get the additive density.

**Returns:** Scalar tensor `>= 0`.

---

### `compute_l_fidelity(s_ref, params) -> torch.Tensor`

**Data Fidelity loss (D-04) — Scale Distribution Preservation**

Prevents the optimizer from inflating word sizes to fill the silhouette by penalizing deviations from the reference scale distribution.

**Formula:**
```
L_fidelity = 1 - cosine_similarity(s_ref, params[:, 2])
```

**Mathematical properties:**
- Range: `[0, 2]` (cosine similarity in [-1, 1], so `1 - (-1..1) = [0, 2]`)
- `L_fidelity = 0` when scale distribution shape is identical to reference
- `L_fidelity = 1` when distributions are orthogonal
- `L_fidelity = 2` when distributions are perfectly anti-correlated
- Only the *shape* of the distribution matters (cosine similarity), not absolute scale magnitudes
- Gradient flows through `params[:, 2]` (scale column)

**Input shapes:**

| Argument | Shape | Dtype | Note |
|----------|-------|-------|------|
| `s_ref` | `(N,)` | float32 | Reference Zipf-normalized scale weights from Phase 3 NLP |
| `params` | `(N, 4)` | float32 | Current optimizer parameters `[y, x, scale, rotation]` |

**Important:** `s_ref.shape[0]` must equal `params.shape[0]` (same N).

**Returns:** Scalar tensor in approximately `[0, 2]`.

**Edge case (PyTorch eps):** Zero-norm vectors produce `cos_sim = 0.0` (eps=1e-8 guard in PyTorch), so `L_fidelity = 1.0` — in `[0, 2]`, no NaN.

---

### `compute_l_temporal(params_current, params_initial) -> torch.Tensor`

**Temporal Coherence loss (D-05) — Position Stability**

Penalizes position drift for live-feed use cases. **Default weight `lambda_=0.0` disables this term in v1** — it exists structurally for Phase 10 Self-Play.

**Formula:**
```
L_temporal = mean((params_current[:, :2] - params_initial[:, :2])^2)
```

**Mathematical properties:**
- `L_temporal >= 0` always
- `L_temporal = 0` when positions (y, x) are unchanged
- Only y and x columns (indices 0 and 1) contribute — scale and rotation changes do NOT affect this loss
- Gradient flows through `params_current[:, :2]`

**Input shapes:**

| Argument | Shape | Dtype |
|----------|-------|-------|
| `params_current` | `(N, 4)` | float32 |
| `params_initial` | `(N, 4)` | float32 |

**Returns:** Scalar tensor `>= 0`.

**Phase 10 note:** Enable by setting `LossWeights(lambda_=0.1)` in InnerLoopConfig when live-feed temporal coherence is needed.

---

### `compute_total_loss(weights, l_wmse, l_overlap, l_fidelity, l_temporal) -> torch.Tensor`

**Composite Loss (D-06)**

Combines all four loss terms with configurable weights.

**Formula:**
```
L_total = alpha * L_wmse + beta * L_overlap + gamma * L_fidelity + lambda_ * L_temporal
```

**Blueprint defaults (D-06):**

| Weight | Default | Rationale |
|--------|---------|-----------|
| `alpha = 1.0` | Moderate | Boundary fitness is the primary objective |
| `beta = 10.0` | High | Overlapping words are unacceptable (high penalty) |
| `gamma = 0.1` | Low | Scale preservation is a soft constraint |
| `lambda_ = 0.0` | Zero | Temporal coherence disabled for static clouds |

**Input shapes:** All four loss arguments are scalar tensors (0-dim).

**Returns:** Scalar tensor.

---

## `compute_additive_density` Helper

**SUM-based compositing for L_overlap (D-03 helper)**

### Purpose

The DifferentiableRenderer uses alpha-over compositing which caps density at 1.0 per pixel. L_overlap needs to detect overlaps where density > 1.0. This helper replaces alpha-over with additive SUM compositing.

### Implementation

Replicates `DifferentiableRenderer.forward()` sprite warp logic exactly, but replaces `alpha_over` with additive SUM:

```python
additive = torch.zeros(1, 1, canvas_h, canvas_w, ...)
for i, sprite in enumerate(renderer._sprites):
    # Same: rotation clamping, softplus scale, NDC conversion, affine matrix
    # Different: additive += warped  (instead of alpha-over)
```

### Mathematical parity with renderer

| Operation | Renderer forward() | compute_additive_density |
|-----------|--------------------|--------------------------|
| Rotation clamping | `torch.remainder(theta + pi, 2*pi) - pi` | Same |
| Scale softplus | `F.softplus(s - 0.01) + 0.01` | Same |
| NDC convention | `((2*x + 1) / W) - 1` | Same |
| affine_grid | `align_corners=False` | Same |
| grid_sample | `bilinear, zeros padding` | Same |
| Compositing | **alpha-over** (max 1.0) | **SUM** (may exceed 1.0) |

### Why private attribute access is acceptable

`compute_additive_density` accesses `renderer._sprites`, `renderer.params`, `renderer._device`. This is documented as a deliberate design choice (Phase 5 CONTEXT.md D-03). No public API exists to expose individual sprite warping without breaking the renderer's alpha-over encapsulation.

**Warning:** If `DifferentiableRenderer.forward()` changes its warp math, `compute_additive_density` must be updated in sync. Both share the same NDC convention (Codex Fix 2 from Phase 5).

### Signature

```python
compute_additive_density(
    renderer: DifferentiableRenderer,
    canvas_h: int,
    canvas_w: int,
) -> torch.Tensor  # (1, 1, canvas_h, canvas_w), values may exceed 1.0
```

---

## `check_convergence` (convergence.py)

**Rolling-window plateau detection (D-14/D-15)**

### Signature

```python
check_convergence(
    loss_history: list[float],
    window: int = 10,
    epsilon: float = 0.001,
) -> bool
```

### Algorithm

```
relative_range = (max(last window) - min(last window)) / max(|max(last window)|, 1e-8)
converged = relative_range < epsilon
```

Returns `False` if `len(loss_history) < window` (not enough data).

### Properties

- Safe for empty history: returns `False`
- Safe for zero-loss plateau: `scale = 1e-8`, `range = 0`, ratio = 0 < epsilon → `True`
- Uses Python `max()` / `min()` on floats — no tensors, no GPU involvement
- Only the last `window` entries are inspected — long histories with diverging prefix are handled correctly

### Convergence criteria

With default parameters:
- Loss relative variation < 0.1% over 10 consecutive epochs → converged
- Active only after `min_epochs_before_convergence=20` epochs (warmup period per D-15)

---

## Design Decisions

### Why separate functions (not a LossModule class)?
D-01: Separate function per loss term so Phase 9 MAP-Elites can use individual terms as quality metrics (LC, LU, SS). A monolithic class would make it harder to extract individual terms.

### Why additive density instead of modifying the renderer?
D-03: Alpha-over compositing is correct for the renderer (produces visually composited output). Additive density is only needed for overlap detection. Mixing both into one renderer output would complicate the Phase 5 API.

### Why cosine similarity for L_fidelity (not L1/L2)?
D-04: Only the *shape* of the scale distribution matters, not absolute magnitudes. Cosine similarity is scale-invariant — a word cloud scaled up uniformly should not be penalized.

---

*Source: packages/engine/src/aerocloud/optimizer/loss.py, convergence.py — Phase 06-inner-loop-v1*

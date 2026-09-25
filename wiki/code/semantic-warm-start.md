# semantic/warm_start.py — Module Documentation

**Phase:** 08-semantic-vector-space
**Package:** `aerocloud.semantic`
**Module:** `packages/engine/src/aerocloud/semantic/warm_start.py`
**Requirements:** SEM-08
**Status:** Implemented + tested (Phase 8 complete)

---

## Overview

`semantic_warm_start` is the Phase 8 public integration function that chains the full
BERT → cosine → UMAP/t-SNE → Sinkhorn pipeline into a single `(N, 4)` params tensor
for the `DifferentiableRenderer`. It replaces random/spiral initialization with
semantically-informed positions where similar words are placed near each other.

**Core design (D-11, D-12):** External function — no InnerLoop API changes. The function
accepts `candidates`, `sdf`, `mat_result` and returns `(N, 4)` tensor `[y, x, 1.0, 0.0]`.
MAT branch origins serve as primary anchor positions; UMAP-scaled fill provides remaining
positions when `N > num_branches`.

---

## Public API

### `semantic_warm_start(candidates, sdf, mat_result, config) -> torch.Tensor`

Compute semantically-informed initial positions for `DifferentiableRenderer`.

**Args:**
- `candidates`: List of N `WordCandidate` objects from NLP pipeline
- `sdf`: `(H, W)` float32 SDF array (positive=inside, ADR-0004 sign convention)
- `mat_result`: `MATResult` with branch origins for target anchor positions
- `config`: Optional dict with overrides:
  - `"seed"` (int): Random seed for UMAP/t-SNE (default: `settings.seed`)
  - `"projection_method"` (str): `"umap"` or `"tsne"` (default: `settings.projection_method`)
  - `"eps_init"` (float): Sinkhorn initial epsilon (default: `settings.sinkhorn_eps_init`)

**Returns:** `(N, 4)` float32 tensor `[y, x, scale, theta]` with `requires_grad=False`.
Column 2 (`scale`) is all `1.0`. Column 3 (`theta`) is all `0.0` per D-11.
All `(y, x)` positions are inside the SDF positive region per D-12.

**Example:**
```python
import numpy as np
from aerocloud.geometry.mat import extract_mat
sdf = np.zeros((128, 128), dtype=np.float32)
sdf[32:96, 32:96] = 10.0  # square positive region
mat = extract_mat(sdf)
candidates = [WordCandidate(surface="cloud", stem="cloud", score=5.0, font_size=24.0)]
params = semantic_warm_start(candidates, sdf, mat, config={"seed": 42})
assert params.shape == torch.Size([1, 4])
assert params[0, 2].item() == 1.0  # scale
assert params[0, 3].item() == 0.0  # theta
```

---

## Full Pipeline Flow Diagram

```
candidates (list[WordCandidate])
    │
    ▼ Step 1: encode_surfaces()
(N, 384) float32 BERT embeddings
    │
    ├──► Step 2: cosine_similarity_matrix() → shape validation
    │
    ▼ Step 3: project_to_2d(method=umap|tsne, seed=seed)
(N, 2) float32 2D semantic positions
    │
    ├──► Step 4: _build_target_positions(coords_2d, sdf, mat_result, N)
    │         ┌── MAT branch origins (primary anchors)
    │         ├── UMAP-scaled fill (if N > num_branches)
    │         └── snap outside pixels to nearest inside pixel
    │         → (N, 2) float32 canvas target positions (all inside SDF > 0)
    │
    ▼ Step 5: cdist(coords_2d, target_positions, "euclidean")
(N, N) float64 transport cost matrix
    │
    ▼ compute_transport(transport_cost, eps_init=eps_init)
TransportPlan (transport_matrix: (N, N) float64)
    │
    ▼ Step 6: transport_matrix.argmax(axis=1)
assignments: (N,) int — each word → best target position index
    │
    ▼ Step 7: build params
(N, 4) float32 [y, x, 1.0, 0.0]
    │
    ▼ torch.from_numpy()
(N, 4) torch.Tensor (requires_grad=False)
```

---

## Position Building: `_build_target_positions`

Internal helper that builds N canvas target positions from MAT branches + UMAP fill.

**Strategy (D-12):**
1. Start with MAT branch `origin_yx` points (deepest interior points per branch)
2. Scale UMAP 2D coords to SDF interior bounding box → `canvas_coords (N, 2)`
3. If `N > num_branches`: fill remaining slots from `canvas_coords` (round-robin)
4. Truncate to exactly N if `num_branches > N`
5. Clamp all positions to canvas bounds `[0, H-1] × [0, W-1]`
6. Snap any position outside SDF positive region to nearest inside pixel (T-08-07)

**Edge case handling:**
- No inside pixels: use canvas quadrant `[H/4, 3H/4] × [W/4, 3W/4]` as bbox fallback
- Degenerate 1-point UMAP output: `umap_range` protected against division by zero
  (`np.where(abs(range) < 1e-8, 1.0, range)`)
- Position outside SDF: O(P) nearest-inside-pixel search (P = inside pixel count),
  bounded by canvas size (T-08-07)

---

## Integration with DifferentiableRenderer

```python
from aerocloud.semantic import semantic_warm_start
from aerocloud.renderer import DifferentiableRenderer

params = semantic_warm_start(candidates, sdf, mat_result)
# params: (N, 4) tensor [y, x, scale=1.0, theta=0.0]

renderer = DifferentiableRenderer(params_n4=params, sprites=sprites, device=device)
# Inner Loop optimizer then calls renderer.forward() with grad tracking
```

No changes to `InnerLoop` or `DifferentiableRenderer` API (D-11 preserved Phase 6 D-19
contract).

---

## Coordinate System

All positions use `(y, x)` canonical internal coordinates (ADR-0005). The params tensor
column layout `[y, x, scale, theta]` matches `DifferentiableRenderer`'s expected input
format.

---

## Security

| Threat | ID | Mitigation |
|--------|----|------------|
| DoS via large canvas SDF | T-08-07 | O(P) search bounded by SDF canvas size; only called per-position, not per-pixel |

---

## References

- `packages/engine/src/aerocloud/semantic/warm_start.py`
- `packages/engine/tests/semantic/integration/test_warm_start_pipeline.py`
- `.planning/phases/08-semantic-vector-space/08-04-PLAN.md`
- `.planning/phases/08-semantic-vector-space/08-CONTEXT.md` §D-11, §D-12
- `wiki/optimal-transport.md` — Sinkhorn-Knopp pipeline: transport → warm-start
- `wiki/code/renderer-differentiable.md` — DifferentiableRenderer API
- `wiki/decisions/2026-04-09-phase-4-coordinate-system-yx.md` — ADR-0005 (y, x) convention

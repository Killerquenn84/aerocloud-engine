# DifferentiableRenderer — Module Documentation

**Phase:** 05-renderer-v1
**Package:** `aerocloud.renderer`
**Module:** `packages/engine/src/aerocloud/renderer/`
**Status:** Implemented + tested (Phase 5 complete)

---

## Overview

`DifferentiableRenderer` is a PyTorch `nn.Module` that composites N pre-rasterized glyph
sprites onto a 2D canvas using learnable position, scale, and rotation parameters. The
forward pass produces a differentiable float32 density tensor that Phase 6 loss functions
consume to drive the Adam optimization loop.

**Core design principle (D-01):** Pure PyTorch `grid_sample` + `affine_grid` implementation.
No nvdiffrast, no PyTorch3D. See `wiki/knowledge/phase-5-renderer-design.md` for the D-01
rationale.

---

## Package Structure

```
packages/engine/src/aerocloud/renderer/
├── __init__.py        Public API re-exports
├── _renderer.py       DifferentiableRenderer nn.Module (~100 lines)
└── _sprites.py        Sprite cache + font registry with RLock (~55 lines)
```

---

## Public API

### Import

```python
from aerocloud.renderer import (
    DifferentiableRenderer,
    FONT_REGISTRY,
    SPRITE_CACHE,
    register_glyph,
    clear_caches,
)
```

---

## DifferentiableRenderer

```python
class DifferentiableRenderer(torch.nn.Module):
    def __init__(
        self,
        params_n4: torch.Tensor,      # (N, 4) float32: [y, x, scale, rotation] per word
        sprites: list[torch.Tensor],  # N sprites, each (1, 1, H_i, W_i) float32 in [0, 1]
        device: torch.device,         # Target device (cpu or cuda)
    ) -> None: ...

    def forward(self, canvas_h: int, canvas_w: int) -> torch.Tensor:
        # Returns: (1, 1, canvas_h, canvas_w) float32 density tensor in [0, 1]
        ...
```

### Constructor Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `params_n4` | `Tensor[N, 4]` | Packed learnable parameters. Columns: `[y, x, scale, rotation]`. Converted to `nn.Parameter` with `requires_grad=True` (D-05). |
| `sprites` | `list[Tensor[1,1,H,W]]` | Pre-rasterized glyph tensors. Static data — stored as plain tensors, NOT `nn.ParameterList`. Detached to prevent autograd graph leaks. |
| `device` | `torch.device` | Both params and sprites are moved to this device at construction. |

**Validation:** Raises `ValueError` if:
- `params_n4.ndim != 2` or `params_n4.shape[1] != 4`
- `len(sprites) != params_n4.shape[0]`

### Parameter Attribute

```python
renderer.params  # nn.Parameter, shape (N, 4), requires_grad=True
```

After `backward()`, `renderer.params.grad` contains gradient w.r.t. all word placements.
Phase 6 Adam optimizer updates `renderer.params` in-place.

### Forward Pass

```python
density = renderer.forward(canvas_h=64, canvas_w=64)
# Returns: Tensor[1, 1, 64, 64], float32, values in [0, 1]
# 0.0 = empty pixel, 1.0 = fully covered pixel
```

**Canvas size** can change between calls — Phase 6 Coarse-to-Fine passes different
resolutions in successive stages.

---

## Forward Pass Internals (D-16)

For each sprite `i` from 0 to N-1:

1. **Extract parameters:**
   ```python
   y_i, x_i, s_i, theta_i = self.params[i]
   ```

2. **Clamp rotation to [-pi, pi] (D-09):**
   ```python
   theta_i = torch.remainder(theta_i + pi, 2*pi) - pi
   ```
   Prevents unbounded parameter growth during optimization.

3. **Normalize pixel coords to NDC [-1, 1] (D-07):**
   ```python
   x_n = (x_i / (canvas_w / 2.0)) - 1.0
   y_n = (y_i / (canvas_h / 2.0)) - 1.0
   ```

4. **Build 2x3 affine matrix:**
   ```python
   theta_mat = torch.stack([
       s_i * cos_t, -s_i * sin_t, x_n,
       s_i * sin_t,  s_i * cos_t, y_n,
   ]).reshape(1, 2, 3)
   ```
   Standard 2D rotation+scale+translate in PyTorch (x,y) convention.

5. **affine_grid + grid_sample (D-02):**
   ```python
   grid   = F.affine_grid(theta_mat, [1,1,H,W], align_corners=False)
   warped = F.grid_sample(sprite, grid, mode='bilinear',
                          padding_mode='zeros', align_corners=False)
   ```
   `align_corners=False` for pixel-edge semantics (RESEARCH.md Pitfall 2).

6. **Alpha-over compositing (D-04):**
   ```python
   density = 1.0 - (1.0 - density) * (1.0 - warped)
   ```
   Equivalent to Porter-Duff over for density maps.

**Output:** `(1, 1, canvas_h, canvas_w)` density tensor.

---

## Sprite Cache (`_sprites.py`)

### `SPRITE_CACHE`

```python
SPRITE_CACHE: dict[tuple[str, int, int], torch.Tensor]
# Key: (font_family, size_pt, codepoint)
# Value: (1, 1, H, W) float32 tensor in [0, 1], detached
```

Module-level process-global cache. Protected by `threading.RLock`. Populated by
`register_glyph()`. Stable across 100+ renders (REND-04 verified).

### `FONT_REGISTRY`

```python
FONT_REGISTRY: set[tuple[str, int]]
# Element: (font_family, size_pt)
```

Tracks unique font family + size combinations in the current render session.
Protected by `threading.RLock`.

### `register_glyph()`

```python
def register_glyph(
    font_family: str,
    size_pt: int,
    codepoint: int,
    pixel_buffer: np.ndarray,  # uint8, shape (H, W)
    device: torch.device,
) -> torch.Tensor:
    # Returns (1, 1, H, W) float32 tensor, detached, on device
```

Idempotent. If key already in cache, returns cached tensor without reallocation.
Thread-safe via `RLock` (same pattern as Phase 3-4 NLP/geometry caches).

**Transfer path (D-11):**
`uint8 ndarray → torch.from_numpy().float().detach() / 255.0 → .unsqueeze(0).unsqueeze(0) → .to(device)`

### `clear_caches()`

```python
def clear_caches() -> None
```

Empties both `SPRITE_CACHE` and `FONT_REGISTRY`. Called in test teardown via autouse
conftest fixture. Not called in production code — caches persist for process lifetime.

---

## Usage Pattern (Phase 6 Integration)

```python
from aerocloud.renderer import DifferentiableRenderer, register_glyph
from aerocloud.models.geometry import PlacementResult, GlyphBBox

def build_renderer(result: PlacementResult, glyphs: list[GlyphBBox],
                   device: torch.device) -> DifferentiableRenderer:
    params_rows = []
    sprites = []
    for word, glyph in zip(result.placed_words, glyphs):
        sprite = register_glyph(
            font_family=word.font_family,
            size_pt=word.size_pt,
            codepoint=word.codepoint,
            pixel_buffer=glyph.pixel_buffer,
            device=device,
        )
        params_rows.append([float(word.y), float(word.x), 1.0, 0.0])
        sprites.append(sprite)
    params_n4 = torch.tensor(params_rows, dtype=torch.float32)
    return DifferentiableRenderer(params_n4, sprites, device)

# Optimization loop (Phase 6)
renderer = build_renderer(placement_result, glyph_bboxes, torch.device('cpu'))
optimizer = torch.optim.Adam(renderer.parameters(), lr=1e-3)
for step in range(500):
    optimizer.zero_grad()
    density = renderer.forward(canvas_h=64, canvas_w=64)
    loss = compute_loss(density, target_sdf)  # Phase 6
    loss.backward()
    optimizer.step()
```

---

## Test Coverage

| Test File | Count | What It Tests |
|-----------|-------|---------------|
| `tests/renderer/unit/test_sprites.py` | 8 | dtype, shape, value range, cache hit/miss, detach, clear |
| `tests/renderer/unit/test_font_registry.py` | 5 | single, duplicate, multiple, 100-call, thread safety |
| `tests/renderer/unit/test_affine.py` | 8 | identity, rotation, scale, combined, align_corners, clamping |
| `tests/renderer/unit/test_compositing.py` | 11 | single/two sprites, alpha-over formula, shape, dtype, range |
| `tests/renderer/property/test_renderer_properties.py` | 7 | hypothesis: random params validity, backward, gradients |
| `tests/renderer/integration/test_placement_to_density.py` | 3 | Phase4->Phase5 end-to-end gradient flow (REND-06) |
| `tests/renderer/determinism/test_determinism.py` | 3 | byte-identical output (D-18) |
| `tests/renderer/memory/test_rss.py` | 3 | RSS < 50 MiB / 100 iterations (D-20) |
| **Total** | **48** | **All REND-01..06 requirements satisfied** |

---

## Known Limitations (v1)

| Limitation | Deferred To |
|------------|-------------|
| No N upper bound (DoS guard) | Phase 12 production hardening |
| No LRU eviction on sprite cache | Phase 12 production hardening |
| align_corners=False half-pixel offset | Phase 6/7 (pixel-accurate placement) |
| Uniform scale only (anisotropic deferred) | Phase 7 Geometry-v2 |
| No gradient checkpointing | Phase 6 (needed at 128px+) |

---

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `torch` | 2.7.1 | nn.Module, affine_grid, grid_sample, autograd |
| `numpy` | 2.2.x | uint8 pixel buffer input to register_glyph |
| `psutil` | 7.2.2 | RSS measurement in memory tests (gpu optional-dep) |

---

*wiki/code/renderer-differentiable.md*
*Phase: 05-renderer-v1 | Created: 2026-04-12*

# Phase 5: Renderer-v1 Design Decisions

**Phase:** 05-renderer-v1
**Captured:** 2026-04-12
**Status:** Phase 5 complete — decisions locked

---

## D-01: Why nvdiffrast Was Superseded by Pure PyTorch

### Background

The AeroCloud Blueprint mentions nvdiffrast as a potential differentiable rasterization
backend. When Phase 5 planning began, the team (Claude + architecture review) evaluated
whether nvdiffrast was the right tool for this problem.

### The Core Insight

nvdiffrast solves: **3D mesh → 2D screen pixels**

Our problem: **2D pre-rasterized glyph sprites + affine transform → 2D canvas**

These are fundamentally different problems:

| Aspect | nvdiffrast | Our Problem |
|--------|-----------|-------------|
| Input | 3D vertex buffers + triangle indices | 2D uint8 pixel arrays (already rasterized) |
| Output | Screen-space pixel values via rasterization | Composited density map |
| Transform | 4x4 MVP matrix (3D → screen) | 2x3 affine matrix (2D → 2D) |
| Pipeline | Full rasterization pipeline with barycentric coords | Spatial resampling via grid_sample |
| Dependencies | CUDA toolkit, NVCC compiler, nvdiffrast C++ extension | Pure PyTorch (already a dependency) |
| CPU fallback | No (CUDA-only) | Yes (torch works on CPU) |

### Why Using nvdiffrast Would Have Been Wrong

To use nvdiffrast for 2D sprite compositing, we would have needed to:
1. Convert each 2D glyph sprite into a 3D mesh (two triangles per sprite quad)
2. Create fake 3D vertex positions (Z=0) and a fake orthographic MVP matrix
3. Use nvdiffrast's rasterizer to "render" the 3D mesh back to the same 2D plane

This would have added:
- `nvdiffrast` as a hard CUDA-only dependency (breaking CPU fallback, D-03)
- Complex vertex buffer management for what is fundamentally a 2D problem
- A difficult-to-build C++ extension with version pinning headaches
- No additional mathematical capability beyond what `grid_sample` provides

### The Pure PyTorch Solution

`torch.nn.functional.grid_sample` + `torch.nn.functional.affine_grid` provides exactly what
is needed:

```python
# Build sampling grid from affine parameters
grid = F.affine_grid(theta_2x3, [1, 1, canvas_h, canvas_w], align_corners=False)
# Sample sprite at transformed coordinates (bilinear interpolation, differentiable)
warped = F.grid_sample(sprite, grid, mode='bilinear', padding_mode='zeros', align_corners=False)
```

- Differentiable w.r.t. the affine parameters (`theta_2x3` contains y, x, scale, rotation)
- Works on CPU and CUDA
- Zero external dependencies beyond torch itself
- ~100 lines of readable Python

### Performance at Phase 5 Scale

REND-05 smoke test: 8px coarse resolution, N ≈ 5 words, forward+backward in milliseconds on CPU.

For Phase 12 production scale (200 words, 128px resolution), the per-sprite loop may need
optimization (vectorized batched `grid_sample` call). This is a Phase 12 concern.

---

## D-02: grid_sample Architecture

### Why align_corners=False

PyTorch's `grid_sample` has two coordinate conventions:

- `align_corners=True`: pixel centers at corners of the `[-1,1]` range.
  Pixel 0 is at -1.0, pixel W-1 is at +1.0.
- `align_corners=False`: pixel-edge semantics.
  The full `[-1,1]` range covers the complete pixel extent including borders.
  Pixel 0 center is at `-(W-1)/W`, pixel W-1 center is at `+(W-1)/W`.

**We use `align_corners=False`** because:
1. It is PyTorch's recommended default (documented to be more numerically correct for
   general-purpose image resampling)
2. RESEARCH.md Pitfall 2 explicitly warns against `align_corners=True` for this use case

**Important:** Both `affine_grid` and `grid_sample` must use the same `align_corners` value.
The implementation enforces this consistently.

### Coordinate Normalization

Pixel coordinates `(y_i, x_i)` from Phase 4 PlacementResult are integer pixel centers.
The forward pass normalizes to NDC:

```python
x_n = (x_i / (canvas_w / 2.0)) - 1.0
y_n = (y_i / (canvas_h / 2.0)) - 1.0
```

**Known half-pixel offset:** This formula maps pixel 0 to NDC -1.0, but `align_corners=False`
places pixel-center 0 at NDC `-(W-1)/W`. This creates a systematic half-pixel shift.
For v1 at 8px coarse resolution, this is negligible noise. At Phase 6/7 high resolution,
a correction will be needed:
```python
x_n = (2.0 * x_i / canvas_w) - 1.0 + (1.0 / canvas_w)
y_n = (2.0 * y_i / canvas_h) - 1.0 + (1.0 / canvas_h)
```
Deferred to Phase 6/7 (D-DEFER-02 from 3-KI review).

### Bilinear Interpolation

`mode='bilinear'` with `padding_mode='zeros'`:
- Bilinear: smooth gradients, no staircase artifacts at glyph edges
- zeros padding: pixels outside canvas boundary contribute 0 (correct for placement)

Bilinear is deterministic under `torch.use_deterministic_algorithms(True)` on CPU per D-18.

---

## D-04: Alpha-Over Compositing

### Formula

For N sprites composited in order:
```
density_final = 1 - prod_{i=1..N}(1 - alpha_i)
```

Implemented as sequential accumulation in the forward loop:
```python
density = 1.0 - (1.0 - density) * (1.0 - warped)
```

### Properties

1. **Differentiable:** multiplication of differentiable quantities. Gradient for sprite i:
   `d(density)/d(alpha_i) = prod_{j≠i}(1 - alpha_j)` — non-zero as long as other sprites
   don't fully cover the pixel.

2. **Order-independent for opaque sources:** If any `alpha_i = 1.0`, the result is 1.0
   regardless of order. This is correct behavior.

3. **Numerically stable at v1 scale:** For N=20 words with average alpha=0.5:
   `prod(1 - 0.5)^20 = 2^(-20) ≈ 1e-6` — well within float32 range.
   For N=200 with full coverage, float32 underflow is theoretically possible
   but in practice glyph sprites are sparse (most pixels near 0) so the product
   remains finite.

---

## D-05: Packed (N, 4) Parameter Tensor

All N word placements are stored in a single `nn.Parameter` of shape `(N, 4)`:

```
params[:, 0] = y coordinates (pixel space)
params[:, 1] = x coordinates (pixel space)
params[:, 2] = scale (uniform, 1.0 at initialization)
params[:, 3] = rotation (radians, 0.0 at initialization)
```

**Benefits:**
- Phase 6 Adam optimizer calls `model.parameters()` and gets one tensor — simple
- Single `backward()` call propagates gradients to all N words simultaneously
- Gradient clipping applies uniformly across all words

---

## D-06: Initialization from Phase 4 PlacementResult

Word parameters at v1 initialization:
- `y, x`: From `PlacedWord.y, PlacedWord.x` (integer pixel centers from Phase 4)
- `scale`: 1.0 (Phase 4 already sized words via Zipf normalization — identity transform)
- `rotation`: 0.0 (Phase 4 places words axis-aligned; rotation is a Phase 6 optimization DoF)
- Dropped words (Phase 4 `DropReason`): EXCLUDED from the tensor

---

## D-11: Sprite Cache Design

```python
SPRITE_CACHE: dict[tuple[str, int, int], torch.Tensor]
# Key: (font_family, size_pt, codepoint)
```

**Key includes codepoint** to prevent cache collisions between different glyphs in the
same font at the same size (e.g., 'A' vs 'B' in Inter 14pt).

**Sprites are detached** (`tensor.detach()`) at creation — they are static data
(pre-rasterized glyph bitmaps), not learnable parameters. Without `.detach()`, the
autograd graph would accumulate across render sessions (Pitfall 3 from RESEARCH.md).

**Transfer path:** uint8 numpy array → float32 tensor / 255.0 → (1,1,H,W) shape → device

---

## Phase 5 Performance Characteristics

At REND-05 smoke test scale (8px canvas, 5 words):
- Forward pass: < 5ms on CPU
- backward() call: < 5ms on CPU
- Memory footprint: negligible (< 1 MiB for all tensors)
- RSS delta over 100 iterations: < 50 MiB (D-20 verified)

At Phase 6 anticipated scale (64px-128px canvas, 50-200 words):
- Forward pass: estimated 10-100ms on CPU (profiling in Phase 6)
- Gradient checkpointing may be needed at 128px+ (D-19 deferred)
- Sprite cache holds all glyph tensors in RAM — for 200 words avg 20x20px = 200*400*4 bytes ≈ 312 KB

---

## Decisions Carried Forward from Phase 4

**D-07 (y,x ordering):** PyTorch image convention is (H, W) = (y, x). The affine matrix
translate vector uses `[x_n, y_n]` in row order (row 0 = x direction, row 1 = y direction)
matching PyTorch's internal convention.

**D-18 (determinism):** `set_seed(42)` + `torch.use_deterministic_algorithms(True)` ensures
byte-identical output across runs. Pure PyTorch `grid_sample` with bilinear on CPU is
deterministic. Verified by `test_determinism.py`.

---

*wiki/knowledge/phase-5-renderer-design.md*
*Phase: 05-renderer-v1 | Created: 2026-04-12*

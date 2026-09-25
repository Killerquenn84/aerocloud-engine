# Phase 5: Renderer-v1 - Research

**Researched:** 2026-04-12
**Domain:** PyTorch differentiable 2D sprite compositing renderer
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Rasterization Backend**
- **D-01:** Pure PyTorch 2D soft-rasterization — no nvdiffrast, no PyTorch3D. The actual requirement is 2D differentiable compositing of pre-rasterized glyph sprites onto a canvas. `grid_sample` + `affine_grid` achieves this with zero external dependencies, full CPU fallback, and trivial gradient flow.
- **D-02:** `torch.nn.functional.grid_sample` for differentiable spatial transform. `affine_grid` builds the sampling grid from learnable (y, x, scale, rotation) parameters. `grid_sample` with `mode='bilinear'` and `padding_mode='zeros'` produces the transformed sprite with gradients flowing back.
- **D-03:** CPU fallback is mandatory. All torch ops must work on `torch.device('cpu')`. Tests run on CPU by default; GPU tests gated behind `pytest.mark.gpu` and `torch.cuda.is_available()`.
- **D-04:** Compositing operator: alpha-over with soft max. `output_density = 1 - prod(1 - alpha_i)`. Differentiable, handles overlap naturally.

**Tensor Architecture**
- **D-05:** Packed (N, 4) parameter tensor with columns `[y, x, scale, rotation]`. Single `nn.Parameter` with `requires_grad=True`.
- **D-06:** Initialization from Phase 4 PlacementResult: y/x from PlacedWord center coords, scale=1.0, rotation=0.0. Dropped words excluded.
- **D-07:** (y, x) ordering internally per Phase 4 carry-forward. Matches PyTorch image convention (H, W) = (y, x).
- **D-08:** Scale is uniform (single scalar per word). Anisotropic scale deferred to Phase 7.
- **D-09:** Rotation is radians, clamped to `[-pi, pi]` via `torch.remainder` in forward pass.

**Glyph-Sprite Pipeline**
- **D-10:** Individual sprites, not atlas. Each glyph is a separate (1, 1, H, W) float32 tensor.
- **D-11:** Transfer path: `GlyphBBox.pixel_buffer` (numpy uint8) → `torch.from_numpy(buf).float() / 255.0` → `.to(device)`. Cached in module-level `dict[tuple[str, int, int], torch.Tensor]` keyed by `(font_family, size_pt, codepoint)`. Cache populated once per render request, not per forward pass.
- **D-12:** Font Registration Set: Module-level `set[tuple[str, int]]` tracking `(font_family, size_pt)` pairs. REND-04 requires exactly N entries after first render and stays at N after 100 renders.
- **D-13:** Sprite resolution matches Phase 4 glyph size. No up/downsampling in v1.

**Forward Pass Architecture**
- **D-14:** `DifferentiableRenderer` class inheriting from `torch.nn.Module`. Enables `model.parameters()`, `model.to(device)`, `model.train()`/`model.eval()`.
- **D-15:** Forward pass signature: `def forward(self, canvas_h: int, canvas_w: int) -> torch.Tensor` returning (1, 1, H, W) density tensor in [0, 1].
- **D-16:** Per-word affine transform: extract (y_i, x_i, s_i, theta_i) → build 2x3 affine matrix → `affine_grid` → `grid_sample` → composite via alpha-over.
- **D-17:** Canvas output is float32 tensor in [0, 1].

**Determinism + Memory**
- **D-18:** `set_seed()` with `warn_only=True` is sufficient. Pure PyTorch `grid_sample` respects `torch.use_deterministic_algorithms(True)`.
- **D-19:** No gradient checkpointing in v1.
- **D-20:** RSS stability test: assert RSS delta < 50 MiB over 100 consecutive forward+backward passes. Uses `psutil.Process().memory_info().rss`.
- **D-21:** `torch.cuda.empty_cache()` in test teardown only, not in production code.

**Testing**
- **D-22:** >= 40 new tests across unit / property (hypothesis) / integration / determinism / RSS / font-leak categories.
- **D-23:** Tests run on CPU by default. GPU tests marked `@pytest.mark.gpu`.

### Claude's Discretion
- Exact `affine_grid` matrix construction (row-major vs column-major torch convention)
- Bilinear vs nearest interpolation mode (bilinear recommended, but may switch to nearest if gradient issues arise)
- Exact alpha-over implementation (loop vs vectorized scatter)
- File splits inside `renderer/` as long as `DifferentiableRenderer` is the public API
- Test fixture design (sprite shapes, canvas sizes)

### Deferred Ideas (OUT OF SCOPE)
- Phase 6: Loss functions, Adam optimizer, Coarse-to-Fine resolution scheduling, gradient checkpointing
- Phase 7: Rotation collision (SAT), anisotropic scale, Bezier path rendering
- Phase 12: Texture atlas optimization, multi-GPU, batch rendering, production profiling, nvdiffrast evaluation
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REND-01 | PyTorch tensor representation: position (x, y), scale (s), rotation (θ) with `requires_grad=True` | D-05 locked: (N,4) packed `nn.Parameter`. Verified: gradient flows to all 4 columns via backward() on 8px canvas output. |
| REND-02 | Soft-Rasterization forward pass (blueprint says nvdiffrast; D-01 supersedes to pure PyTorch grid_sample) | Verified on torch 2.11.0+cu130: `affine_grid` + `grid_sample(mode='bilinear')` produces non-NaN output and correct gradients. |
| REND-03 | Glyph rasterization to scratch canvas with integer-snapped positions for sprite generation | Covered by D-11: `from_numpy(buf).float()/255` transfer path. Phase 4 `rasterize_glyph()` already produces uint8 `pixel_buffer`. |
| REND-04 | Fonts registered ONCE at process start (module-level Set), never per request | D-12 locked: `set[tuple[str, int]]` module-level. Font leak test verifies count stable across 100 renders. |
| REND-05 | Coarse-resolution forward pass (8px) verified to produce non-NaN output | Verified locally: 8×8 canvas with 1-word renderer produces non-NaN float32 tensor in [0, 1]. |
| REND-06 | Gradient flow test: `backward()` on simple input does not raise | Verified locally: `loss.sum().backward()` with single word at 8px produces non-None `params.grad` tensor. |
</phase_requirements>

---

## Summary

Phase 5 delivers a `DifferentiableRenderer(nn.Module)` that composites pre-rasterized glyph sprites onto a 2D canvas using PyTorch's native `grid_sample` + `affine_grid` API. All architectural decisions are locked in CONTEXT.md (D-01 through D-23). The key insight is that the original Blueprint requirement mentioning nvdiffrast is superseded: nvdiffrast solves 3D mesh → 2D screen space rasterization, while this phase's problem is 2D sprite + affine transform → 2D canvas, which is natively and more simply solved by `torch.nn.functional.grid_sample`.

Hands-on verification confirms torch 2.11.0+cu130 is installed (CPU-only at test time, no CUDA available on the VPS), `grid_sample` and `affine_grid` are present, the forward pass produces non-NaN output on an 8px canvas, and `backward()` yields non-None gradients on all four parameter columns (y, x, scale, rotation). The alpha-over compositing formula `1 - prod(1 - alpha_i)` is differentiable with respect to each `alpha_i` and verified correct. `torch.use_deterministic_algorithms(True, warn_only=True)` is compatible with `grid_sample` on this torch version.

One dependency gap requires Wave 0 attention: `psutil` is not in `pyproject.toml` but is required by D-20 for the RSS stability test. It must be added to the `[gpu]` optional-dependencies group (or core dependencies). The `renderer/` package directory does not yet exist and must be created with `__init__.py`.

**Primary recommendation:** Create `packages/engine/src/aerocloud/renderer/` with `_renderer.py` (DifferentiableRenderer class), `_sprites.py` (sprite cache + font registration set), and `__init__.py` (public API). Add `psutil` to pyproject.toml. Write >= 40 tests across 7 test categories. Zero external rendering dependencies needed.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| torch | 2.11.0+cu130 (installed) | `nn.Module`, `nn.Parameter`, `grid_sample`, `affine_grid`, autograd | Already installed, CPU fallback verified, full autograd |
| psutil | >=5.9.0 | RSS memory measurement for D-20 leak test | Standard cross-platform process memory probe |
| numpy | >=2.1.0 (installed) | `pixel_buffer` → `torch.from_numpy()` bridge | Already in core deps |

### Supporting (already installed, no new additions needed beyond psutil)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hypothesis | 6.151.11 (installed) | Property tests for random params → non-NaN output | D-22 property test tier |
| pytest | >=8.3.0 (installed) | Test runner | All test categories |
| pydantic | >=2.10.0 (installed) | Input contract models at package boundary | Accepts PlacementResult; never in forward pass hot loop |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `grid_sample` (D-01) | nvdiffrast | nvdiffrast requires CUDA build, solves 3D mesh problem, adds hard dependency. `grid_sample` is built-in, works on CPU, solves 2D sprite problem directly. |
| `grid_sample` | PyTorch3D | Same as nvdiffrast — 3D pipeline overhead, complex install. |
| alpha-over loop | vectorized scatter | Vectorized requires stacking all sprites as (N, 1, H, W) tensor. Loop is simpler and correct. Claude's discretion (D-22 section). |

**Installation (psutil only — everything else already installed):**
```bash
# Add to packages/engine/pyproject.toml [project.optional-dependencies] gpu section
# or to core dependencies:
uv add psutil --package aerocloud-engine
```

**Version verification:** [VERIFIED: uv run python -c "import torch; print(torch.__version__)"] — torch 2.11.0+cu130. psutil not yet installed — must be added in Wave 0.

---

## Architecture Patterns

### Recommended Project Structure

```
packages/engine/src/aerocloud/renderer/
├── __init__.py          # public API: DifferentiableRenderer, FONT_REGISTRY, SPRITE_CACHE
├── _renderer.py         # DifferentiableRenderer(nn.Module) — forward pass, affine math
└── _sprites.py          # sprite cache dict, font registration set, transfer helpers

packages/engine/tests/renderer/
├── __init__.py
├── conftest.py          # shared fixtures: tiny sprites, placement results, canvas sizes
├── unit/
│   ├── __init__.py
│   ├── test_affine.py       # affine matrix construction (identity, rot, scale, combined)
│   ├── test_compositing.py  # alpha-over (2 overlapping sprites, boundary values)
│   └── test_font_registry.py # add, dedup, count stability
├── property/
│   ├── __init__.py
│   └── test_renderer_properties.py  # random params → non-NaN, [0,1] range, backward() ok
├── integration/
│   ├── __init__.py
│   └── test_placement_to_density.py  # Phase4 PlacementResult → DifferentiableRenderer → density → backward()
├── determinism/
│   ├── __init__.py
│   └── test_determinism.py  # same seed, same input → byte-identical output over 10 runs
└── memory/
    ├── __init__.py
    └── test_rss.py           # 100 forward+backward, RSS delta < 50 MiB; font Set stable
```

### Pattern 1: DifferentiableRenderer as nn.Module

**What:** `DifferentiableRenderer` inherits `torch.nn.Module`. Learnable params are `nn.Parameter`. Forward pass takes canvas dimensions, returns (1, 1, H, W) density tensor.

**When to use:** Any time a placement result needs to be rendered to a differentiable canvas for Phase 6 loss computation.

**Example:**
```python
# Source: D-14, D-15, D-16 from 05-CONTEXT.md + verified locally
import torch
import torch.nn as nn
import torch.nn.functional as F
import math

class DifferentiableRenderer(nn.Module):
    def __init__(
        self,
        params_n4: torch.Tensor,          # (N, 4) float32: [y, x, scale, rotation]
        sprites: list[torch.Tensor],       # N x (1, 1, H_i, W_i) float32 in [0, 1]
        device: torch.device,
    ) -> None:
        super().__init__()
        self.params = nn.Parameter(params_n4.to(device))
        self._sprites = [s.to(device) for s in sprites]
        self._device = device

    def forward(self, canvas_h: int, canvas_w: int) -> torch.Tensor:
        """Returns (1, 1, canvas_h, canvas_w) density tensor in [0, 1]."""
        density = torch.zeros(1, 1, canvas_h, canvas_w, device=self._device)
        for i, sprite in enumerate(self._sprites):
            y_i, x_i, s_i, theta_i = self.params[i]
            # Clamp rotation to [-pi, pi] to prevent unbounded growth (D-09)
            theta_i = torch.remainder(theta_i + math.pi, 2 * math.pi) - math.pi
            # Normalize center coords to affine_grid's [-1, 1] space (D-07)
            x_n = (x_i / (canvas_w / 2.0)) - 1.0
            y_n = (y_i / (canvas_h / 2.0)) - 1.0
            cos_t = torch.cos(theta_i)
            sin_t = torch.sin(theta_i)
            theta_mat = torch.stack([
                s_i * cos_t, -s_i * sin_t, x_n,
                s_i * sin_t,  s_i * cos_t, y_n,
            ]).reshape(1, 2, 3)
            grid = F.affine_grid(theta_mat, [1, 1, canvas_h, canvas_w], align_corners=False)
            warped = F.grid_sample(sprite, grid, mode='bilinear',
                                   padding_mode='zeros', align_corners=False)
            # Alpha-over compositing (D-04): density = 1 - prod(1 - alpha_i)
            density = 1.0 - (1.0 - density) * (1.0 - warped)
        return density
```

### Pattern 2: Sprite Cache and Font Registration Set

**What:** Module-level dict and set for sprite tensors and font registrations. Populated once per render request, stable across forward passes.

**Example:**
```python
# Source: D-11, D-12 from 05-CONTEXT.md
import threading
from typing import Final
import numpy as np
import torch

# (font_family, size_pt) — REND-04: populated once, stays stable
FONT_REGISTRY: set[tuple[str, int]] = set()
_FONT_REGISTRY_LOCK = threading.RLock()

# (font_family, size_pt, codepoint) → (1, 1, H, W) float32 tensor
SPRITE_CACHE: dict[tuple[str, int, int], torch.Tensor] = {}
_SPRITE_CACHE_LOCK = threading.RLock()

def register_glyph(
    font_family: str,
    size_pt: int,
    codepoint: int,
    pixel_buffer: np.ndarray,  # uint8 (H, W)
    device: torch.device,
) -> torch.Tensor:
    """Transfer glyph to device tensor and register font. Idempotent."""
    key = (font_family, size_pt, codepoint)
    with _SPRITE_CACHE_LOCK:
        if key not in SPRITE_CACHE:
            t = torch.from_numpy(pixel_buffer).float() / 255.0
            SPRITE_CACHE[key] = t.unsqueeze(0).unsqueeze(0).to(device)  # (1,1,H,W)
    with _FONT_REGISTRY_LOCK:
        FONT_REGISTRY.add((font_family, size_pt))
    return SPRITE_CACHE[key]
```

### Pattern 3: affine_grid Coordinate Convention

**What:** `affine_grid` uses normalized device coordinates (NDC) in [-1, 1] for both x and y. The theta matrix is row 0 = [a, b, tx], row 1 = [c, d, ty] where tx, ty are in NDC space.

**Critical detail:** `align_corners=False` is the correct default for the compositing use case — it treats corners as pixel edges (not pixel centers), which is consistent with how `padding_mode='zeros'` behaves at boundaries.

**Example:**
```python
# Source: verified locally with torch 2.11.0
# Convert pixel coords (y_px, x_px) on canvas (H, W) to NDC:
# x_ndc = (x_px / (W / 2.0)) - 1.0
# y_ndc = (y_px / (H / 2.0)) - 1.0
# For center of 8x8 canvas (y=4, x=4): x_ndc = 0.0, y_ndc = 0.0
```

### Anti-Patterns to Avoid

- **Pydantic models in the forward pass hot loop:** Accepted at construction (`PlacementResult`), converted to tensors once, never inside `forward()`. Follows Phase 2-4 established pattern.
- **Per-forward-pass sprite re-upload:** Cache sprites in `__init__`, not in `forward()`. Re-uploading each call defeats the cache purpose and leaks memory.
- **`align_corners=True` without justification:** Breaks consistency with `padding_mode='zeros'` behavior at boundaries. Stick to `align_corners=False`.
- **`torch.cuda.empty_cache()` in production code path:** Only in test teardown (D-21). The caching allocator manages GPU memory efficiently without manual clearing.
- **Not clamping rotation:** Unbounded `theta` during optimization grows to very large values, causing `sin/cos` precision loss at no semantic benefit (D-09).
- **Calling `set_seed()` inside forward:** Determinism is set once at process start, not per-call.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Differentiable spatial transform | Custom bilinear interpolation | `F.grid_sample` + `F.affine_grid` | Handles all edge cases (boundary, sub-pixel), autograd-safe, numerically tested |
| Gradient flow through affine params | Manual chain rule | PyTorch autograd | Autograd handles rotation/scale/translation Jacobian correctly |
| Memory leak detection | Manual heap profiling | `psutil.Process().memory_info().rss` | Standard, cross-platform, minimal overhead |
| Rotation normalization | Custom modulo arithmetic | `torch.remainder(theta + pi, 2*pi) - pi` | Differentiable, works in autograd graph |
| Float32 pixel buffer conversion | Manual dtype casting loop | `torch.from_numpy(buf).float() / 255.0` | Zero-copy, dtype-safe, standard idiom |

**Key insight:** The entire renderer is ~150-250 lines of pure PyTorch with zero external dependencies beyond torch itself. Do not add complexity.

---

## Common Pitfalls

### Pitfall 1: affine_grid theta Matrix Column/Row Ordering

**What goes wrong:** Swapping x/y in the theta matrix produces transposed output — the word appears at the correct distance from center but rotated 90 degrees from expected.

**Why it happens:** `affine_grid` uses spatial convention where theta = [[a, b, tx], [c, d, ty]] with output[0] = x-like, output[1] = y-like. But PyTorch image tensors are (N, C, H, W) = (N, C, y, x). The mapping is: theta row 0 controls the x-output sampling coordinate (column dimension), theta row 1 controls y-output (row dimension).

**How to avoid:** Use the verified construction from Pattern 1 exactly. Write a unit test with a 1-pixel sprite at a known position and assert the output pixel lands at the expected canvas location.

**Warning signs:** Unit test `test_affine.py::test_identity_transform` fails — the lit pixel does not map to the expected canvas position.

### Pitfall 2: align_corners Mismatch Between affine_grid and grid_sample

**What goes wrong:** `affine_grid(..., align_corners=True)` + `grid_sample(..., align_corners=False)` raises a UserWarning and produces incorrectly-positioned output.

**Why it happens:** PyTorch requires both calls to use the same `align_corners` value. Mixing them is a detected inconsistency.

**How to avoid:** Always pass `align_corners=False` to both `affine_grid` and `grid_sample`. Verified: this is the correct choice for pixel-edge semantics.

**Warning signs:** `UserWarning: When align_corners = True, the grid positions depend on the pixel size` appearing in test output.

### Pitfall 3: Sprite Tensor Not Detached From Previous Computation Graph

**What goes wrong:** If a sprite tensor was created with `requires_grad=True` elsewhere and is stored in the cache, it accumulates graph history across forward passes, leaking memory.

**Why it happens:** `torch.from_numpy(...).float()` creates a leaf tensor (no grad by default), but if the buffer was modified through a grad-enabled path, the tensor may retain graph refs.

**How to avoid:** `register_glyph()` always calls `.detach()` on the sprite before caching: `t = torch.from_numpy(buf).float().detach() / 255.0`. Sprites are input data, not learned parameters.

**Warning signs:** RSS test fails (> 50 MiB delta over 100 iterations).

### Pitfall 4: psutil Not in Dependencies

**What goes wrong:** D-20 RSS test imports `psutil` which is not in `pyproject.toml`. CI fails on fresh install with `ModuleNotFoundError`.

**Why it happens:** `psutil` is not part of the existing core or optional dependencies.

**How to avoid:** Wave 0 task must add `psutil>=5.9.0` to `packages/engine/pyproject.toml`. Verify with `uv run python -c "import psutil"`.

**Warning signs:** `ModuleNotFoundError: No module named 'psutil'` in test output (confirmed absent on current install).

### Pitfall 5: Font Registration Set Not Thread-Safe

**What goes wrong:** Concurrent render requests (Phase 12 multi-worker) corrupt the module-level set with race conditions.

**Why it happens:** Python `set.add()` is not thread-safe under PyPy or when the GIL is released.

**How to avoid:** Use `threading.RLock()` around all set mutations. Pattern 2 above shows the correct approach.

**Warning signs:** Font leak test shows non-deterministic counts across runs.

### Pitfall 6: torch.remainder Gradient Through Rotation Clamp

**What goes wrong:** `torch.remainder` is differentiable, but the gradient is 1.0 everywhere except at discontinuities where it is undefined. During optimization, if theta wraps around the discontinuity, the gradient step can jump.

**Why it happens:** `remainder` introduces a modular discontinuity at `theta = -pi` and `theta = pi`.

**How to avoid:** In v1 this is acceptable (D-09 explicitly chose `torch.remainder`). In Phase 6, the optimizer should keep theta in a reasonable range via gradient clipping (INNER-07). Log a warning if `|theta_i| > 2*pi` after N steps.

**Warning signs:** Property test `test_backward_does_not_raise` fails for extreme theta values (e.g., theta=1e6). Add hypothesis `@settings(suppress_health_check=[HealthCheck.too_slow])` for large-value strategies.

---

## Code Examples

### Example 1: Factory Function (PlacementResult → DifferentiableRenderer)

```python
# Source: D-06, D-11, D-14 from 05-CONTEXT.md
from aerocloud.models.geometry import PlacementResult
from aerocloud.renderer import DifferentiableRenderer, register_glyph
import torch

def make_renderer(
    result: PlacementResult,
    device: torch.device,
) -> DifferentiableRenderer:
    """Build DifferentiableRenderer from Phase 4 PlacementResult.

    Only placed words enter the tensor (dropped words excluded per D-06).
    """
    placed = result.placed_words  # list[PlacedWord]
    params = torch.tensor(
        [[pw.y, pw.x, 1.0, 0.0] for pw in placed],
        dtype=torch.float32,
    )  # (N, 4): y, x, scale=1.0, rotation=0.0

    sprites = []
    for pw in placed:
        # Each PlacedWord must carry its GlyphBBox for the sprite buffer.
        # Phase 4 PlacementResult carries this via the geometry contract.
        glyph = result.glyph_for(pw)  # GlyphBBox
        sprite = register_glyph(
            glyph.font_family, glyph.size_pt, glyph.codepoint,
            glyph.pixel_buffer, device,
        )
        sprites.append(sprite)

    return DifferentiableRenderer(params, sprites, device)
```

### Example 2: RSS Memory Test Pattern

```python
# Source: D-20 from 05-CONTEXT.md
import psutil, os
import torch

def test_rss_stability_100_iters(renderer: DifferentiableRenderer):
    proc = psutil.Process(os.getpid())
    rss_before = proc.memory_info().rss

    for _ in range(100):
        out = renderer.forward(8, 8)
        loss = out.sum()
        loss.backward()
        renderer.params.grad = None  # zero grad manually

    rss_after = proc.memory_info().rss
    delta_mib = (rss_after - rss_before) / 1024 / 1024
    assert delta_mib < 50.0, f"RSS grew {delta_mib:.1f} MiB over 100 iterations"
```

### Example 3: Font Registration Stability Test Pattern

```python
# Source: D-12, REND-04 from 05-CONTEXT.md
from aerocloud.renderer._sprites import FONT_REGISTRY

def test_font_registry_stable_across_100_renders(renderer, monkeypatch):
    # First render populates the set
    renderer.forward(8, 8)
    n_after_first = len(FONT_REGISTRY)
    assert n_after_first > 0

    # 100 more renders must not grow the set
    for _ in range(100):
        renderer.forward(8, 8)
    assert len(FONT_REGISTRY) == n_after_first
```

### Example 4: Hypothesis Property Test Pattern

```python
# Source: D-22 from 05-CONTEXT.md, following geometry/property/test_sdf_properties.py pattern
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
import torch

@given(
    n=st.integers(min_value=1, max_value=10),
    canvas_size=st.integers(min_value=4, max_value=32),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_random_params_produce_valid_output(n: int, canvas_size: int):
    params = torch.rand(n, 4)  # y, x, scale, rotation — all random
    sprites = [torch.rand(1, 1, 4, 4) for _ in range(n)]
    renderer = DifferentiableRenderer(params, sprites, torch.device("cpu"))
    out = renderer.forward(canvas_size, canvas_size)
    assert not torch.isnan(out).any(), "Output contains NaN"
    assert (out >= 0).all() and (out <= 1).all(), "Output out of [0, 1]"
    out.sum().backward()
    assert renderer.params.grad is not None
```

---

## Runtime State Inventory

> Omitted — this is a greenfield renderer package (new `packages/engine/src/aerocloud/renderer/` directory). No rename/refactor/migration involved.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| torch (CPU) | All rendering ops | yes | 2.11.0+cu130 | — |
| torch.cuda | GPU tests (pytest.mark.gpu) | no | — | CPU tests run; GPU tests skipped via `pytest.mark.gpu` + `cuda.is_available()` guard |
| numpy | Sprite buffer transfer | yes | (installed) | — |
| psutil | D-20 RSS test | NO | — | No fallback — must add to pyproject.toml in Wave 0 |
| hypothesis | Property tests | yes | 6.151.11 | — |
| pytest | Test runner | yes | >=8.3.0 | — |

**Missing dependencies with no fallback:**
- `psutil` — required by D-20 RSS stability test. Must be added to `packages/engine/pyproject.toml` before tests can run. Wave 0 task.

**Missing dependencies with fallback:**
- CUDA — GPU tests skip automatically when `torch.cuda.is_available()` returns False. Tests run on CPU.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.0 + hypothesis 6.151.11 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` at repo root |
| Quick run command | `uv run pytest packages/engine/tests/renderer/ -x -q` |
| Full suite command | `uv run pytest packages/engine/tests/renderer/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REND-01 | (N,4) params tensor has requires_grad=True and receives gradients | unit | `pytest tests/renderer/unit/test_affine.py -x` | Wave 0 |
| REND-02 | forward() on 8px canvas returns non-NaN (1,1,8,8) tensor | unit + property | `pytest tests/renderer/unit/ tests/renderer/property/ -x` | Wave 0 |
| REND-03 | uint8 pixel_buffer correctly transferred to float32 sprite tensor in [0,1] | unit | `pytest tests/renderer/unit/test_affine.py::test_sprite_transfer -x` | Wave 0 |
| REND-04 | FONT_REGISTRY has N entries after first render, still N after 100 renders | memory | `pytest tests/renderer/memory/test_rss.py::test_font_registry_stable -x` | Wave 0 |
| REND-05 | 8px forward pass produces non-NaN output | unit + integration | `pytest tests/renderer/unit/test_affine.py::test_8px_smoke -x` | Wave 0 |
| REND-06 | backward() on toy loss does not raise; gradient on params is non-None | unit + integration | `pytest tests/renderer/unit/test_affine.py::test_backward_ok -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest packages/engine/tests/renderer/ -x -q`
- **Per wave merge:** `uv run pytest packages/engine/tests/renderer/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `packages/engine/src/aerocloud/renderer/__init__.py` — public API module
- [ ] `packages/engine/src/aerocloud/renderer/_renderer.py` — DifferentiableRenderer class
- [ ] `packages/engine/src/aerocloud/renderer/_sprites.py` — sprite cache + font registry
- [ ] `packages/engine/tests/renderer/__init__.py` — test package init
- [ ] `packages/engine/tests/renderer/conftest.py` — shared fixtures (sprites, PlacementResult stub)
- [ ] `packages/engine/tests/renderer/unit/` — unit test files (test_affine.py, test_compositing.py, test_font_registry.py)
- [ ] `packages/engine/tests/renderer/property/test_renderer_properties.py` — hypothesis tests
- [ ] `packages/engine/tests/renderer/integration/test_placement_to_density.py` — end-to-end
- [ ] `packages/engine/tests/renderer/determinism/test_determinism.py` — byte-identical output
- [ ] `packages/engine/tests/renderer/memory/test_rss.py` — RSS + font leak tests
- [ ] Add `psutil>=5.9.0` to `packages/engine/pyproject.toml` `[gpu]` optional deps (or core)
- [ ] Add `[gpu]` extras install to CI step that runs renderer tests

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | renderer is an internal module, no auth boundary |
| V3 Session Management | no | stateless nn.Module, no sessions |
| V4 Access Control | no | internal engine, no user-facing access |
| V5 Input Validation | yes | Pydantic `PlacementResult` validates all inputs at boundary; `pixel_buffer` already validated as uint8 (H,W) by GlyphBBox |
| V6 Cryptography | no | no encryption in renderer |

### Known Threat Patterns for PyTorch nn.Module

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed pixel_buffer (oversized numpy array causing OOM) | Denial of Service | GlyphBBox validator already enforces `uint8` + `ndim==2`; renderer enforces device transfer limits |
| `safetensors` for checkpoint save/load | Tampering | If Phase 6 saves renderer state, use `safetensors` not `pickle` per REQUIREMENTS.md DATA-06 |
| Unbounded rotation during optimization | Denial of Service | D-09 `torch.remainder` clamp prevents `sin/cos` precision collapse |
| Font path injection via `font_family` field | Tampering | `fonts.py font_path()` resolves from bundled assets only — no external URLs; PROD-14 font allow-list enforces this |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `PlacementResult` carries a `glyph_for(placed_word)` method or equivalent accessor for the associated `GlyphBBox` | Architecture Patterns (factory function example) | Factory function needs redesign; may need to pass glyphs separately from PlacementResult |
| A2 | `FONT_REGISTRY` and `SPRITE_CACHE` at module level are sufficient for v1 single-process use; no cross-process sharing needed yet | Standard Stack (Pattern 2) | Would need shared memory or Redis-backed cache for multi-worker Phase 12 |

**A1 note:** The CONTEXT.md canonical refs state to read `packages/engine/src/aerocloud/models/geometry.py` for PlacementResult. The model was read (lines 197+) but the full PlacementResult definition extends below the read window. The planner should read the full definition to verify how placed words and glyphs are associated. If `PlacementResult` does not carry a direct glyph accessor, the factory function signature needs adjustment — the caller must pass both the result and the glyph dict.

---

## Open Questions (RESOLVED)

1. **PlacementResult full definition and glyph access** — RESOLVED
   - What we know: `PlacementResult` contains `placements: list[PlacedWord]` and `PlacedWord` has `word`, `y`, `x`, `bbox`, `size_pt`
   - Resolution: `PlacementResult` does NOT carry `GlyphBBox` objects. The caller passes glyphs separately. The `DifferentiableRenderer` factory accepts `(PlacementResult, list[GlyphBBox])` as a pair. Plan 03 integration test builds params from `result.placements` and sprites from a separate glyph list.

2. **pytest testpaths config includes renderer tests** — RESOLVED
   - What we know: `pyproject.toml [tool.pytest.ini_options]` testpaths = `["tests/unit", "tests/integration"]` — these are repo-root-relative paths, not package-relative.
   - Resolution: Phase 4 geometry tests are invoked via explicit path `uv run pytest packages/engine/tests/geometry/ -x -q`, not via root testpaths. Renderer tests follow the same pattern: `uv run pytest packages/engine/tests/renderer/ -x -q`. All plan verify commands use explicit package paths.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| nvdiffrast (3D mesh rasterizer) | Pure PyTorch `grid_sample` (2D sprite transform) | D-01 locked in 05-CONTEXT.md | Zero external build deps, CPU fallback, simpler gradient flow |
| Per-glyph font load on each render | Module-level FONT_REGISTRY set + SPRITE_CACHE dict | D-11, D-12 in 05-CONTEXT.md | REND-04 compliance, memory stability |

**Deprecated/outdated in this phase context:**
- nvdiffrast/PyTorch3D: Superseded by D-01. The pyproject.toml `[gpu]` section currently says "Placeholder — nvdiffrast + pytorch3d added in Phase 5 planning" — this placeholder must be replaced with `psutil` and no nvdiffrast.

---

## Sources

### Primary (HIGH confidence)
- [VERIFIED: uv run python] — torch 2.11.0+cu130 installed, `grid_sample` + `affine_grid` present, gradient flow confirmed, `use_deterministic_algorithms(True, warn_only=True)` compatible
- [VERIFIED: uv run python] — alpha-over formula `1 - prod(1 - alpha_i)` produces correct values and gradients
- [VERIFIED: uv run python] — full `DifferentiableRenderer(nn.Module)` prototype: forward pass non-NaN at 8px, backward() produces non-None params.grad on all 4 columns
- [VERIFIED: codebase grep] — `psutil` absent from `packages/engine/pyproject.toml`
- [VERIFIED: codebase grep] — `packages/engine/src/aerocloud/renderer/` directory exists as empty directory (ls shows no files)
- [VERIFIED: file read] — existing test infrastructure: hypothesis 6.151.11, pytest >=8.3.0, `pytest.mark.gpu` marker registered in pyproject.toml
- [CITED: 05-CONTEXT.md D-01..D-23] — all architectural decisions locked

### Secondary (MEDIUM confidence)
- [CITED: wiki/research/nightly/2026-04-11-pytorch-autograd-graph-memory.md] — CVE-2026-19283 (moderate, heap-overflow in autograd C++ frontend for circular refs in custom Function objects) — not blocking for this phase; Phase 5 does not use custom autograd Functions
- [CITED: wiki/research/nightly/2026-04-12-pytorch-autograd-graph-memory.md] — community report of memory leaks with `keep_graph=True` under CUDA 13.x in torch nightly; not relevant to Phase 5 (no retained graphs, no CUDA available)

### Tertiary (LOW confidence)
- None.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — torch installed and verified, APIs confirmed working
- Architecture: HIGH — forward pass prototype verified end-to-end, patterns match Phase 2-4 codebase conventions
- Pitfalls: HIGH — confirmed via direct experimentation (align_corners, rotation clamp, detach requirement)
- Environment: HIGH — direct `uv run` verification of all critical dependencies
- Missing psutil: HIGH — confirmed absent via grep

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (stable torch API; psutil is a long-lived library)

# Phase 6: Inner Loop-v1 - Research

**Researched:** 2026-04-11
**Domain:** PyTorch differentiable optimization — loss functions, Adam, Coarse-to-Fine
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Loss Function Architecture**
- D-01: Separate function per loss term — each returns a scalar tensor. `compute_total_loss()` combines with weight coefficients.
- D-02: L_wmse = `mean((clamp(sdf, min=0) * (1.0 - density))²)` — SDF-positive pixels weighted by depth.
- D-03: L_overlap = `mean(ReLU(density - 1.0)²)` — uses ADDITIVE compositing (sum of warped sprites), not alpha-over.
- D-04: L_fidelity = `1.0 - cos_sim(S_ref, S_current)` — frozen Zipf-normalized scale vector from Phase 3.
- D-05: L_temporal = `mean((params_current[:, :2] - params_initial[:, :2])²)` — default weight lambda=0.0 in v1.
- D-06: L_total = `alpha * L_wmse + beta * L_overlap + gamma * L_fidelity + lambda_ * L_temporal` — defaults: alpha=1.0, beta=10.0, gamma=0.1, lambda_=0.0.

**Optimizer Configuration**
- D-07: `torch.optim.Adam` with lr=0.001, betas=(0.9, 0.999), eps=1e-8.
- D-08: `torch.nn.utils.clip_grad_norm_` with max_norm=1.0 after each `backward()` before `step()`.
- D-09: Only `renderer.params` is optimized. Sprites, SDF, and reference weights are frozen.

**Coarse-to-Fine Pipeline**
- D-10: Fixed 4-stage schedule: [8, 32, 128, target]. 100 max epochs per stage. Warm-start carry-over.
- D-11: 100 max epochs per stage.
- D-12: Positions in pixel coordinates of ORIGINAL mask; NDC normalization in renderer adapts automatically.
- D-13: SDF downsampled per stage via `torch.nn.functional.interpolate(mode='bilinear')`.

**Convergence Detection**
- D-14: Rolling-window plateau: `(max(window) - min(window)) / max(abs(max(window)), 1e-8) < epsilon=0.001` over last 10 epochs.
- D-15: Minimum 20 epochs before convergence check.

**Memory Hygiene**
- D-16: `.detach().item()` for all logged loss values.
- D-17: `torch.cuda.empty_cache()` after each stage transition (NOT per epoch).
- D-18: `optimizer.zero_grad(set_to_none=True)` per epoch.

**Public API**
- D-19: `InnerLoop` class in `packages/engine/src/aerocloud/optimizer/inner_loop.py`. Constructor takes `DifferentiableRenderer`, SDF tensor, reference weights, config. `optimize() -> OptimizationResult`.
- D-20: `OptimizationResult` Pydantic model: final params tensor, per-stage loss history, total epochs, convergence flags per stage, wall clock time.
- D-21: `LossWeights` Pydantic model: alpha, beta, gamma, lambda_ with defaults from D-06.

**Testing**
- D-22: Test pyramid — unit (loss functions, grad clipping, convergence detection), property (hypothesis: no NaN/Inf, bounds), integration (8px canvas converges in 100 epochs), determinism (same seed → identical curves), memory (RSS stable over 100 runs). Target: >= 35 new tests.
- D-23: CPU by default. GPU tests marked `@pytest.mark.gpu`.

### Claude's Discretion
- Exact loss function implementation details within the formulas specified above
- Logging format and frequency (structlog integration)
- Internal helper functions in the optimizer module
- Test fixture design (sprite shapes, SDF patterns, canvas sizes)
- Exact file splits inside `optimizer/` as long as `InnerLoop` is the public API

### Deferred Ideas (OUT OF SCOPE)

**→ Phase 7 Geometry-v2:** Advanced collision integration
**→ Phase 9 Outer Loop-v1:** Loss weight sweeps, quality metrics (LC, LU, SS)
**→ Phase 10 Self-Play:** L_temporal with lambda > 0
**→ Phase 12 Production-v1:** Production performance budgets, Celery task wrapper, SSE progress endpoint
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INNER-01 | Four-part Loss: `L_total = α·L_wmse + β·L_overlap + γ·L_fidelity + λ·L_temporal` | D-06; pure PyTorch arithmetic on tensor scalars |
| INNER-02 | L_wmse (Boundary Fitness): SDF-driven shape attraction | D-02; `clamp + mean + pow` — standard torch ops |
| INNER-03 | L_overlap (Primitive Overlap): `ReLU(density - 1.0)²` | D-03; requires additive compositing branch in renderer call |
| INNER-04 | L_fidelity (Data Fidelity): `1 - cos_sim(S_ref, S_upd)` | D-04; `F.cosine_similarity` on scale column |
| INNER-05 | L_temporal (Temporal Coherence): position-change penalty | D-05; lambda_=0.0 in v1 — structural stub |
| INNER-06 | Adam optimizer: lr=0.001, β1=0.9, β2=0.999, ε=10⁻⁸ | D-07; standard `torch.optim.Adam` |
| INNER-07 | Gradient clipping: `torch.nn.utils.clip_grad_norm_` | D-08; max_norm=1.0 |
| INNER-08 | Coarse-to-Fine pipeline: 8px → 32px → 128px → target | D-10/D-13; `F.interpolate` for SDF downsampling |
| INNER-09 | Convergence detection with early termination on loss plateau | D-14/D-15; rolling-window 10 epochs, epsilon=0.001, min 20 warmup |
| INNER-10 | Memory hygiene: `.detach()` for metrics, `empty_cache()` after stages | D-16/D-17/D-18 |
</phase_requirements>

---

## Summary

Phase 6 builds the inner optimization loop that drives a `DifferentiableRenderer` (Phase 5) toward an optimal word placement using gradient descent on four loss terms. All mathematical formulas are locked in CONTEXT.md (Blueprint §5.2–5.4). The planner's job is to sequence the implementation: loss functions → optimizer wrapper → Coarse-to-Fine pipeline → convergence detection → memory hygiene → `InnerLoop` class → tests.

The key technical challenge is L_overlap (INNER-03): the Phase 5 renderer uses **alpha-over compositing** which caps density at 1.0 and cannot detect overlaps. The inner loop must produce a **second density map** using additive compositing (sum of individually warped sprites) to detect values > 1.0. This requires either a second forward pass in additive mode or a helper function inside the optimizer that re-computes additive density from the renderer's internal state.

The Coarse-to-Fine pipeline is the performance backbone (10x speedup target). Each stage runs the full optimization loop at a lower resolution, then carries parameters directly to the next stage as a warm start. SDF downsampling is handled by `torch.nn.functional.interpolate(mode='bilinear')` applied to the full-resolution SDF from Phase 4.

**Primary recommendation:** Implement loss functions first (pure torch, unit-testable in isolation), then the optimizer loop, then Coarse-to-Fine orchestration, then `InnerLoop` class as the public API wrapper.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| torch | 2.11.0+cu130 (verified on server) | Loss computation, Adam, grad clipping | Already installed; locked by Phase 5 |
| torch.optim.Adam | built-in | Gradient descent optimizer | Blueprint D-07, INNER-06 |
| torch.nn.functional | built-in | interpolate (SDF resize), cosine_similarity (L_fidelity), relu (L_overlap) | Standard torch functional API |
| torch.nn.utils.clip_grad_norm_ | built-in | Gradient clipping | Blueprint D-08, INNER-07 |
| pydantic | 2.10+ | OptimizationResult, LossWeights models | Established project pattern |
| structlog | 24.4+ | Logging | Phase 1 foundation |
| psutil | 5.9+ | RSS memory measurement in tests | Already in `[gpu]` optional-dep |

[VERIFIED: uv run python -c "import torch; print(torch.__version__)"] — torch 2.11.0+cu130

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hypothesis | 6.120+ | Property-based tests for loss bounds | NaN/Inf testing, value range tests |
| pytest-benchmark | 4.0+ | Coarse-to-Fine speedup measurement | Success criterion 2: >= 10x speedup |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `torch.optim.Adam` | custom Adam | Blueprint locks standard Adam; no custom optimizer in v1 |
| `F.interpolate(bilinear)` | `F.interpolate(nearest)` | Bilinear preserves gradient-relevant distances better for SDF |

**Installation:** No new packages required. All dependencies already in `packages/engine/pyproject.toml`. `psutil` is in `[gpu]` optional-dep group.

**Version verification:** torch 2.11.0+cu130 confirmed live on server. [VERIFIED: uv run]

---

## Architecture Patterns

### Recommended Project Structure

```
packages/engine/src/aerocloud/optimizer/
├── __init__.py              # Public API: InnerLoop, OptimizationResult, LossWeights
├── inner_loop.py            # InnerLoop class (D-19), optimize() method
├── loss.py                  # 4 loss functions + compute_total_loss()
└── convergence.py           # Rolling-window plateau detection (D-14/D-15)

packages/engine/tests/optimizer/
├── __init__.py
├── conftest.py              # Shared fixtures: renderer, sdf tensor, ref_weights
├── unit/
│   ├── __init__.py
│   ├── test_loss_wmse.py
│   ├── test_loss_overlap.py
│   ├── test_loss_fidelity.py
│   ├── test_loss_temporal.py
│   ├── test_loss_total.py
│   ├── test_convergence.py
│   └── test_grad_clipping.py
├── property/
│   ├── __init__.py
│   └── test_loss_properties.py   # Hypothesis: no NaN/Inf, value ranges
├── integration/
│   ├── __init__.py
│   └── test_coarse_to_fine.py    # Convergence in 100 epochs @ 8px
├── determinism/
│   ├── __init__.py
│   └── test_determinism.py       # Same seed → identical loss curves
└── memory/
    ├── __init__.py
    └── test_rss.py               # RSS stable over 100 optimization steps
```

### Pattern 1: Additive Compositing for L_overlap

**What:** L_overlap requires density > 1.0 to detect overlaps. The Phase 5 `DifferentiableRenderer.forward()` uses alpha-over compositing which caps at 1.0. The inner loop must compute additive density separately.

**When to use:** Only for L_overlap computation; the training density signal still uses alpha-over from the renderer.

**Implementation approach:**

```python
# Source: CONTEXT.md D-03 + _renderer.py implementation analysis
def compute_additive_density(
    renderer: DifferentiableRenderer,
    canvas_h: int,
    canvas_w: int,
) -> torch.Tensor:
    """Additive compositing: sum of all warped sprites (can exceed 1.0).
    
    Used ONLY for L_overlap. Not used for the alpha-over density signal.
    Replicates the per-sprite warp logic from DifferentiableRenderer.forward()
    but with summation instead of alpha-over compositing.
    """
    # Re-use the same affine_grid + grid_sample logic as the renderer
    # but sum instead of alpha-over
    density = torch.zeros(1, 1, canvas_h, canvas_w, device=renderer._device)
    for i, sprite in enumerate(renderer._sprites):
        # ... same affine transform logic as renderer forward() ...
        density = density + warped  # additive, NOT alpha-over
    return density
```

This function lives inside `optimizer/loss.py` (or as a private helper) and accesses `renderer._sprites` and `renderer.params`. It is NOT added to the renderer's public API.

### Pattern 2: Loss Function Signatures

**What:** Each loss returns a scalar tensor (not `.item()`), so gradients flow.

```python
# Source: CONTEXT.md D-01..D-06
import torch
import torch.nn.functional as F

def compute_l_wmse(
    density: torch.Tensor,      # (1,1,H,W) alpha-over output
    sdf: torch.Tensor,           # (1,1,H,W) float32, positive=inside
) -> torch.Tensor:               # scalar
    sdf_positive = sdf.clamp(min=0.0)
    return ((sdf_positive * (1.0 - density)) ** 2).mean()

def compute_l_overlap(
    additive_density: torch.Tensor,  # (1,1,H,W) SUM of sprites, can exceed 1.0
) -> torch.Tensor:                    # scalar
    return (F.relu(additive_density - 1.0) ** 2).mean()

def compute_l_fidelity(
    s_ref: torch.Tensor,    # (N,) frozen reference scale vector
    params: torch.Tensor,   # (N,4) current renderer params
) -> torch.Tensor:          # scalar, in [0, 2]
    s_current = params[:, 2]  # scale column
    return 1.0 - F.cosine_similarity(s_ref.unsqueeze(0), s_current.unsqueeze(0)).squeeze()

def compute_l_temporal(
    params_current: torch.Tensor,   # (N,4)
    params_initial: torch.Tensor,   # (N,4) detached snapshot from loop start
) -> torch.Tensor:                  # scalar
    return ((params_current[:, :2] - params_initial[:, :2]) ** 2).mean()

def compute_total_loss(
    weights: LossWeights,
    l_wmse: torch.Tensor,
    l_overlap: torch.Tensor,
    l_fidelity: torch.Tensor,
    l_temporal: torch.Tensor,
) -> torch.Tensor:
    return (
        weights.alpha * l_wmse
        + weights.beta * l_overlap
        + weights.gamma * l_fidelity
        + weights.lambda_ * l_temporal
    )
```

### Pattern 3: Inner Optimization Loop (per stage)

```python
# Source: CONTEXT.md D-07..D-18
def _run_stage(
    renderer: DifferentiableRenderer,
    sdf_stage: torch.Tensor,       # downsampled SDF for this stage
    ref_weights: torch.Tensor,     # frozen S_ref
    params_initial: torch.Tensor,  # detached snapshot at stage start
    canvas_h: int,
    canvas_w: int,
    config: InnerLoopConfig,
) -> StageResult:
    optimizer = torch.optim.Adam(
        [renderer.params],
        lr=config.weights.lr,
        betas=(0.9, 0.999),
        eps=1e-8,
    )
    loss_history = []
    converged = False
    
    for epoch in range(config.max_epochs):
        optimizer.zero_grad(set_to_none=True)                       # D-18
        
        density = renderer(canvas_h, canvas_w)                      # alpha-over
        additive = compute_additive_density(renderer, canvas_h, canvas_w)
        
        l_wmse = compute_l_wmse(density, sdf_stage)
        l_overlap = compute_l_overlap(additive)
        l_fidelity = compute_l_fidelity(ref_weights, renderer.params)
        l_temporal = compute_l_temporal(renderer.params, params_initial)
        l_total = compute_total_loss(config.weights, l_wmse, l_overlap, l_fidelity, l_temporal)
        
        l_total.backward()
        torch.nn.utils.clip_grad_norm_([renderer.params], max_norm=1.0)  # D-08
        optimizer.step()
        
        loss_history.append(l_total.detach().item())                # D-16
        
        if epoch >= config.min_epochs_before_convergence:           # D-15
            converged = _check_plateau(loss_history, config.window, config.epsilon)
            if converged:
                break
    
    return StageResult(loss_history=loss_history, converged=converged, epochs=epoch + 1)
```

### Pattern 4: Coarse-to-Fine Orchestration

```python
# Source: CONTEXT.md D-10..D-13
STAGE_RESOLUTIONS = [8, 32, 128]  # target appended at runtime

def optimize(self) -> OptimizationResult:
    import time
    t0 = time.perf_counter()
    stages = STAGE_RESOLUTIONS + [self._target_h]  # D-10
    all_stage_results = []
    
    for res in stages:
        # Downsample SDF to stage resolution (D-13)
        sdf_stage = F.interpolate(
            self._sdf_full,     # (1,1,H_full,W_full)
            size=(res, res),
            mode="bilinear",
            align_corners=False,
        )
        # Snapshot initial params for L_temporal
        params_initial = self._renderer.params.detach().clone()
        
        result = self._run_stage(
            self._renderer, sdf_stage, self._ref_weights,
            params_initial, res, res, self._config
        )
        all_stage_results.append(result)
        
        # Memory cleanup between stages (D-17)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    
    return OptimizationResult(
        params=self._renderer.params.detach(),
        stage_loss_histories=[r.loss_history for r in all_stage_results],
        total_epochs=sum(r.epochs for r in all_stage_results),
        convergence_flags=[r.converged for r in all_stage_results],
        wall_clock_s=time.perf_counter() - t0,
    )
```

### Pattern 5: Pydantic Models at the Boundary

```python
# Source: CONTEXT.md D-20/D-21 + existing AeroCloudBase pattern
from aerocloud.models.base import AeroCloudBase
from pydantic import ConfigDict, Field
import torch

class LossWeights(AeroCloudBase):
    """Loss coefficients (D-21). Exposed for Phase 9 sweeps."""
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, arbitrary_types_allowed=False)
    alpha: float = Field(default=1.0, ge=0.0)
    beta: float = Field(default=10.0, ge=0.0)
    gamma: float = Field(default=0.1, ge=0.0)
    lambda_: float = Field(default=0.0, ge=0.0)

class OptimizationResult(AeroCloudBase):
    """Phase 6 output contract (D-20). Consumed by Phase 9 MAP-Elites."""
    model_config = ConfigDict(frozen=True, extra="forbid", strict=False, arbitrary_types_allowed=True)
    params: torch.Tensor         # (N,4) detached final placement parameters
    stage_loss_histories: list[list[float]]
    total_epochs: int = Field(ge=0)
    convergence_flags: list[bool]
    wall_clock_s: float = Field(ge=0.0)
```

Note: `strict=False` on `OptimizationResult` because `torch.Tensor` is not a Pydantic-native type. Following the `GlyphBBox` precedent from `models/geometry.py` which uses `arbitrary_types_allowed=True`.

### Anti-Patterns to Avoid

- **Retaining computation graph in metrics:** Never `loss_history.append(l_total)` — always `.detach().item()`. The computation graph accumulates memory across all epochs if not released.
- **Calling `empty_cache()` per epoch:** Only call between stage transitions (D-17). Per-epoch `empty_cache()` is a CPU/GPU sync point that kills throughput.
- **Using alpha-over density for L_overlap:** The alpha-over density is capped at 1.0; `ReLU(density - 1.0)` would always be 0, producing zero gradient. Must use additive density.
- **Passing `renderer._sprites` by reference without detach:** Sprites are not learned but they're on the same device. Do not call `.backward()` through the sprite data.
- **Forgetting `set_to_none=True`:** `optimizer.zero_grad()` without the flag allocates zero-tensors. `set_to_none=True` drops the grad reference entirely (D-18).
- **Checking convergence before min_epochs:** The loss often dips briefly then rises in early epochs. The 20-epoch warmup (D-15) prevents false early termination.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Gradient descent | Custom update rule | `torch.optim.Adam` | Momentum, adaptive LR, numerics are subtle |
| Gradient clipping | Manual norm computation | `torch.nn.utils.clip_grad_norm_` | Handles in-place + multi-param groups correctly |
| SDF resize | Custom bilinear code | `F.interpolate(mode='bilinear')` | Aligns with PyTorch's autograd-safe implementation |
| Cosine similarity | Manual dot-product + norm | `F.cosine_similarity` | Handles zero-norm edge case with eps |
| ReLU | `torch.clamp(x, min=0)` | `F.relu` | Same result but `F.relu` is more idiomatic and readable |

**Key insight:** All mathematical operations in Phase 6 are standard PyTorch building blocks. The value is in their composition, not any custom kernel.

---

## Common Pitfalls

### Pitfall 1: Additive vs. Alpha-Over Density
**What goes wrong:** L_overlap returns zero gradient because `ReLU(alpha_over_density - 1.0)` is always 0 (alpha-over caps at 1.0).
**Why it happens:** The Phase 5 renderer correctly uses alpha-over for the visual output, but overlap detection requires raw additive summation.
**How to avoid:** Implement `compute_additive_density()` separately. Verify in unit tests with 2 overlapping sprites that `additive_density.max() > 1.0`.
**Warning signs:** L_overlap stays at exactly 0.0 during training even when sprites visually overlap.

### Pitfall 2: Tensor Lifetime and Computation Graph Accumulation
**What goes wrong:** RSS grows monotonically across epochs because loss tensors retain references to the full computation graph.
**Why it happens:** `loss_history.append(l_total)` keeps the graph alive. `.item()` extracts the scalar and breaks the reference.
**How to avoid:** Always `.detach().item()` for logging. Memory test (`test_rss.py`) will catch this.
**Warning signs:** RSS growing > 50 MiB per 100 iterations.

### Pitfall 3: SDF Sign Convention in L_wmse
**What goes wrong:** Using `sdf` directly instead of `clamp(sdf, min=0)` causes outside pixels (sdf < 0) to contribute negative-weighted penalties, reversing the gradient signal.
**Why it happens:** Phase 4 SDF convention is `positive=inside, negative=outside` (ADR-0004). L_wmse must only penalize uncovered interior pixels.
**How to avoid:** `sdf_positive = sdf.clamp(min=0)` — unit test with a known circular SDF verifying that outside pixels contribute 0 to L_wmse.

### Pitfall 4: AeroCloudBase strict=True with torch.Tensor
**What goes wrong:** `OptimizationResult` validation raises `ValidationError` because `torch.Tensor` is not a recognized Pydantic type under strict mode.
**Why it happens:** `AeroCloudBase` sets `strict=True` globally. This works for scalars but rejects arbitrary objects.
**How to avoid:** Override `model_config` in `OptimizationResult` with `strict=False, arbitrary_types_allowed=True`. Precedent: `GlyphBBox` in `models/geometry.py`.

### Pitfall 5: Convergence False Positive at Plateau Near Non-Zero Loss
**What goes wrong:** The rolling-window check triggers early at a local plateau that is not the global optimum.
**Why it happens:** `epsilon=0.001` relative tolerance is tight but not zero — a flat plateau (not minimum) satisfies the criterion.
**How to avoid:** The 20-epoch warmup (D-15) and the integration test (convergence within 100 epochs at 8px) together bound this. No fix needed — this is intentional behavior.

### Pitfall 6: NaN from Cosine Similarity on Zero-Norm Scale Vector
**What goes wrong:** L_fidelity produces NaN if `S_ref` or `S_current` has zero norm.
**Why it happens:** `cos_sim(a, b) = dot(a,b) / (||a|| * ||b||)` divides by zero for zero-norm vectors.
**How to avoid:** `F.cosine_similarity` has an `eps` parameter (default 1e-8) that prevents exact zero division. The NaN property test (hypothesis) will catch any remaining cases.

### Pitfall 7: Stage SDF Size Mismatch with Canvas Size
**What goes wrong:** The renderer `forward(canvas_h, canvas_w)` produces `(1,1,canvas_h,canvas_w)` but the SDF tensor is `(1,1,H_full,W_full)`.
**Why it happens:** L_wmse multiplies `density * sdf` elementwise — they must have identical shapes.
**How to avoid:** Always downsample SDF to `(res, res)` before each stage. The integration test on the full pipeline will catch shape mismatches immediately.

---

## Code Examples

Verified patterns from existing codebase:

### Property Test Pattern (from renderer)
```python
# Source: packages/engine/tests/renderer/property/test_renderer_properties.py
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

@given(n=st.integers(min_value=1, max_value=10))
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_random_params_produce_finite_loss(n: int) -> None:
    """Random params must produce finite (non-NaN, non-Inf) total loss."""
    # ... test body using compute_total_loss()
```

### Memory Test Pattern (from renderer)
```python
# Source: packages/engine/tests/renderer/memory/test_rss.py
import psutil, os
process = psutil.Process(os.getpid())
rss_before = process.memory_info().rss
# ... run 100 iterations ...
delta_mib = (rss_after - rss_before) / 1024 / 1024
assert delta_mib < 50.0
```

### GPU Skip Marker (from renderer)
```python
# Source: packages/engine/tests/renderer/conftest.py
import pytest, torch
gpu = pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
```

### AeroCloudBase with arbitrary types
```python
# Source: packages/engine/src/aerocloud/models/geometry.py (GlyphBBox)
from pydantic import ConfigDict
from aerocloud.models.base import AeroCloudBase

class OptimizationResult(AeroCloudBase):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=False,             # Override: torch.Tensor is not a strict Pydantic type
        arbitrary_types_allowed=True,
    )
```

### SDF Downsampling
```python
# Source: CONTEXT.md D-13 + torch.nn.functional.interpolate docs [CITED: pytorch.org/docs]
import torch.nn.functional as F

def _downsample_sdf(sdf_full: torch.Tensor, target_size: int) -> torch.Tensor:
    """Downsample full-res SDF to square target_size for Coarse-to-Fine stage."""
    if sdf_full.shape[-1] == target_size and sdf_full.shape[-2] == target_size:
        return sdf_full
    return F.interpolate(
        sdf_full,
        size=(target_size, target_size),
        mode="bilinear",
        align_corners=False,
    )
```

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3+ with hypothesis 6.120+ |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` at repo root |
| Quick run command | `uv run pytest packages/engine/tests/optimizer/ -x -q` |
| Full suite command | `uv run pytest packages/engine/tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INNER-01 | L_total = weighted sum of 4 terms | unit | `pytest tests/optimizer/unit/test_loss_total.py -x` | Wave 0 |
| INNER-02 | L_wmse with SDF weighting | unit + property | `pytest tests/optimizer/unit/test_loss_wmse.py -x` | Wave 0 |
| INNER-03 | L_overlap >= 0, requires additive density | unit + property | `pytest tests/optimizer/unit/test_loss_overlap.py -x` | Wave 0 |
| INNER-04 | L_fidelity in [0, 2] | unit + property | `pytest tests/optimizer/unit/test_loss_fidelity.py -x` | Wave 0 |
| INNER-05 | L_temporal >= 0 (structural stub) | unit | `pytest tests/optimizer/unit/test_loss_temporal.py -x` | Wave 0 |
| INNER-06 | Adam params correct | unit | `pytest tests/optimizer/unit/test_grad_clipping.py -x` | Wave 0 |
| INNER-07 | Gradient clipping max_norm=1.0 | unit | `pytest tests/optimizer/unit/test_grad_clipping.py -x` | Wave 0 |
| INNER-08 | Coarse-to-Fine converges in 100 epochs @ 8px | integration | `pytest tests/optimizer/integration/test_coarse_to_fine.py -x` | Wave 0 |
| INNER-09 | Convergence detection terminates early | unit | `pytest tests/optimizer/unit/test_convergence.py -x` | Wave 0 |
| INNER-10 | RSS stable over 100 runs; no NaN losses (1000 seeds) | memory + property | `pytest tests/optimizer/memory/ tests/optimizer/property/ -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest packages/engine/tests/optimizer/ -x -q`
- **Per wave merge:** `uv run pytest packages/engine/tests/ -q`
- **Phase gate:** Full suite green (643 existing + >= 35 new) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `packages/engine/tests/optimizer/__init__.py`
- [ ] `packages/engine/tests/optimizer/conftest.py` — shared renderer + SDF + ref_weights fixtures
- [ ] `packages/engine/tests/optimizer/unit/__init__.py`
- [ ] `packages/engine/tests/optimizer/unit/test_loss_wmse.py`
- [ ] `packages/engine/tests/optimizer/unit/test_loss_overlap.py`
- [ ] `packages/engine/tests/optimizer/unit/test_loss_fidelity.py`
- [ ] `packages/engine/tests/optimizer/unit/test_loss_temporal.py`
- [ ] `packages/engine/tests/optimizer/unit/test_loss_total.py`
- [ ] `packages/engine/tests/optimizer/unit/test_convergence.py`
- [ ] `packages/engine/tests/optimizer/unit/test_grad_clipping.py`
- [ ] `packages/engine/tests/optimizer/property/__init__.py`
- [ ] `packages/engine/tests/optimizer/property/test_loss_properties.py`
- [ ] `packages/engine/tests/optimizer/integration/__init__.py`
- [ ] `packages/engine/tests/optimizer/integration/test_coarse_to_fine.py`
- [ ] `packages/engine/tests/optimizer/determinism/__init__.py`
- [ ] `packages/engine/tests/optimizer/determinism/test_determinism.py`
- [ ] `packages/engine/tests/optimizer/memory/__init__.py`
- [ ] `packages/engine/tests/optimizer/memory/test_rss.py`
- [ ] `packages/engine/src/aerocloud/optimizer/__init__.py` (empty dir exists, no files)

---

## Project Constraints (from CLAUDE.md)

**From `aerocloud-engine/CLAUDE.md`:**
- TDD: failing test must exist before implementation (Red → Green → Refactor)
- Tests are laws — never modify tests to make them pass; only adjust implementation
- Conventional commits: `feat:`, `fix:`, `test:`, `refactor:`
- 3-KI team discussion before code; code review before commit
- Session handover to wiki after phase completion
- All changes reported via Telegram (Jens, chat_id: 5697986530)
- English in code/comments/tests; German in Telegram messages
- Wiki entries mandatory for all new code, decisions, tests, bugs

**From root `wordcloud-app-v2/CLAUDE.md`:** Different project (Shopify app) — not applicable to aerocloud-engine.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `compute_additive_density()` can access `renderer._sprites` (private attribute) | Architecture Patterns §1 | If the renderer refactors internal structure, the additive helper breaks. Low risk: renderer is stable after Phase 5 review. |
| A2 | 4-stage schedule `[8, 32, 128, target]` works when target <= 128 (e.g., 64px masks) | Standard Stack / Coarse-to-Fine | If target < 128, stage 3 (128px) would upsample then downsample. Needs handling: skip stages larger than target. |

**Assumption A2 clarification:** The planner should ensure the stage schedule filters out resolutions >= target. E.g., for a 64px mask: stages become `[8, 32, 64]` not `[8, 32, 128, 64]`.

---

## Open Questions

1. **Additive density: separate function or renderer mode flag?**
   - What we know: Phase 5 renderer only exposes alpha-over compositing via `forward()`. CONTEXT.md D-03 says "use additive compositing separately."
   - What's unclear: Should `compute_additive_density()` live in `optimizer/loss.py` (accessing renderer internals) or should a `forward_additive()` method be added to the renderer?
   - Recommendation: Keep it in `optimizer/loss.py` as a private helper. Adding a method to the renderer is a Phase 5 change that requires 3-KI review. The optimizer already knows the renderer's internals (it owns the renderer instance). This is Claude's discretion territory.

2. **SDF tensor shape: numpy vs. torch, 2D vs. 4D?**
   - What we know: `compute_sdf()` returns `(H, W)` float32 numpy array. The renderer operates on `(1,1,H,W)` torch tensors.
   - What's unclear: When should the SDF be converted to torch + reshaped?
   - Recommendation: `InnerLoop.__init__()` converts the numpy SDF to `torch.tensor(sdf).unsqueeze(0).unsqueeze(0)` once at construction, then all stage logic works with torch 4D tensors.

3. **LossWeights Pydantic model: frozen=True means no `lr` field?**
   - What we know: CONTEXT.md D-21 specifies alpha, beta, gamma, lambda_. Adam lr is specified separately in D-07 (lr=0.001).
   - What's unclear: Should lr be in LossWeights or in a separate `InnerLoopConfig`?
   - Recommendation: Put lr in a separate `InnerLoopConfig` dataclass or Pydantic model that contains `LossWeights` as a sub-model. This matches Phase 9's expected API surface where weight sweeps don't need to change lr.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| torch | Loss + optimizer | ✓ | 2.11.0+cu130 | — |
| torch.optim.Adam | INNER-06 | ✓ | built-in | — |
| torch.nn.utils.clip_grad_norm_ | INNER-07 | ✓ | built-in | — |
| torch.nn.functional.interpolate | INNER-08 | ✓ | built-in | — |
| psutil | Memory tests | ✓ | in [gpu] optional-dep | — |
| hypothesis | Property tests | ✓ | 6.120+ via dev deps | — |
| pytest-benchmark | Speedup test | ✓ | 4.0+ via dev deps | — |
| CUDA GPU | GPU tests | ✓ | cu130 | CPU fallback (skip marker) |

[VERIFIED: uv run python -c "import torch; print(torch.__version__)"] — all torch features verified present.

---

## Security Domain

The inner loop is a CPU/GPU computation module with no network I/O, no user input, and no file I/O beyond loading pre-validated tensors from upstream modules. Standard ASVS categories do not apply to pure mathematical computation.

| ASVS Category | Applies | Rationale |
|---------------|---------|-----------|
| V2 Authentication | no | No network endpoints in Phase 6 |
| V3 Session Management | no | Stateless computation function |
| V4 Access Control | no | No resource access |
| V5 Input Validation | partial | SDF and params tensors validated by upstream phases (Phase 4 `validate_sdf`, Phase 5 renderer constructor) |
| V6 Cryptography | no | No cryptographic operations |

**No security blockers for Phase 6.**

---

## Sources

### Primary (HIGH confidence)
- CONTEXT.md (D-01..D-23) — all implementation decisions locked by user discussion
- `_renderer.py` (packages/engine/src/aerocloud/renderer/) — Phase 5 contract verified by reading source
- `sdf.py` (packages/engine/src/aerocloud/geometry/) — Phase 4 contract verified by reading source
- `models/base.py`, `models/geometry.py` — Pydantic patterns verified by reading source
- `raw/sources/AeroCloud-Blueprint.md §Teil V` — Blueprint math verified at lines 107–131
- uv run verification — torch 2.11.0+cu130 confirmed on server [VERIFIED]

### Secondary (MEDIUM confidence)
- Existing test patterns (`test_rss.py`, `test_renderer_properties.py`, `renderer/conftest.py`) — verified by reading source; same patterns apply to Phase 6 tests

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — torch version verified live; all deps confirmed present
- Architecture: HIGH — patterns derived directly from locked CONTEXT.md decisions and existing codebase
- Pitfalls: HIGH — derived from code analysis (alpha-over cap, tensor lifetime) + existing Phase patterns
- Test Architecture: HIGH — follows identical structure to Phase 5 renderer tests

**Research date:** 2026-04-11
**Valid until:** 2026-05-11 (stable PyTorch API; torch optim Adam has not changed in years)

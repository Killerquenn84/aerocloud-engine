# Phase 6: Inner Loop-v1 - Context

**Gathered:** 2026-04-14 (auto mode)
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the differentiable optimization loop that takes the Phase 5 DifferentiableRenderer
forward pass output and optimizes word placement parameters via gradient descent. Delivers
the 4-part loss function, Adam optimizer integration, Coarse-to-Fine resolution pipeline,
convergence detection, and memory hygiene — the complete "inner loop" of the Dual-Loop
architecture.

**Explicitly out of scope (→ Phase 7 Geometry-v2):** MAT, Multi-Centric placement,
advanced collision (BVH, Quadtree, SAT, Bitmap). The inner loop uses Phase 4's AABB
collision via the renderer density map, not direct geometric collision.

**Explicitly out of scope (→ Phase 9 Outer Loop-v1):** MAP-Elites, quality metrics
(LC, LU, SS), archive persistence. The inner loop produces ONE optimized layout per
invocation — the outer loop explores the solution space.

**Explicitly out of scope (→ Phase 12 Production-v1):** Celery task integration,
production performance budgets, GPU resource isolation, SSE progress endpoint.

</domain>

<decisions>
## Implementation Decisions

### Loss Function Architecture
- **D-01:** **Separate function per loss term** — each loss is a standalone function
  returning a scalar tensor. `compute_total_loss()` combines them with weight coefficients.
  This enables Phase 9 MAP-Elites to reuse individual loss terms as quality metrics.
- **D-02:** **L_wmse (INNER-02):** Boundary fitness loss. For each pixel inside the
  silhouette (SDF > 0), penalize absence of word coverage:
  `L_wmse = mean((sdf_positive * (1.0 - density))²)`
  where `sdf_positive = clamp(sdf, min=0)` and `density` is the renderer output.
  SDF values weight the penalty — pixels deeper inside the silhouette contribute more.
- **D-03:** **L_overlap (INNER-03):** Primitive overlap penalty.
  `L_overlap = mean(ReLU(density - 1.0)²)`
  Penalizes any pixel where multiple sprites overlap (density > 1.0). The Phase 5
  alpha-over compositing produces density in [0,1] per-sprite, but the SUM of overlapping
  sprites can exceed 1.0. For this loss, use additive compositing (sum of warped sprites)
  rather than alpha-over, to detect overlaps.
- **D-04:** **L_fidelity (INNER-04):** Data fidelity loss. Prevents the optimizer from
  artificially inflating word sizes to fill the silhouette.
  `L_fidelity = 1.0 - cos_sim(S_ref, S_current)`
  where `S_ref` is the frozen Zipf-normalized scale vector from Phase 3 NLP pipeline
  and `S_current` is the current scale column from the renderer params.
- **D-05:** **L_temporal (INNER-05):** Position change penalty for live feeds.
  `L_temporal = mean((params_current[:, :2] - params_initial[:, :2])²)`
  Implemented but **default weight lambda=0.0** in v1. No live feeds yet — the loss
  term exists structurally for Phase 10 Self-Play.
- **D-06:** **L_total (INNER-01):** Combined loss with Blueprint coefficients:
  `L_total = alpha * L_wmse + beta * L_overlap + gamma * L_fidelity + lambda_ * L_temporal`
  Default weights: `alpha=1.0, beta=10.0, gamma=0.1, lambda_=0.0`.
  Weights exposed via Pydantic config so Phase 9 can sweep them.

### Optimizer Configuration
- **D-07:** **Standard `torch.optim.Adam`** with Blueprint parameters (INNER-06):
  `lr=0.001, betas=(0.9, 0.999), eps=1e-8`. No custom optimizer in v1.
- **D-08:** **Gradient clipping (INNER-07):** `torch.nn.utils.clip_grad_norm_` with
  `max_norm=1.0` applied after each `backward()` before `optimizer.step()`.
- **D-09:** **Only renderer.params is optimized.** Sprites, SDF, and reference weights
  are frozen inputs. The optimizer receives `[renderer.params]` only.

### Coarse-to-Fine Pipeline
- **D-10:** **Fixed 4-stage schedule (INNER-08):** `[8, 32, 128, target]` where `target`
  is the input mask resolution. Each stage runs the full optimization loop at that
  resolution, then the parameters carry over to the next stage (warm-start).
- **D-11:** **100 max epochs per stage.** Convergence detection (D-14) can terminate
  a stage early if the loss plateaus.
- **D-12:** **Resolution change:** The renderer's `forward(canvas_h, canvas_w)` already
  accepts variable canvas size (Phase 5 D-15). No resizing of params needed — positions
  are in pixel coordinates of the ORIGINAL mask, and the NDC normalization in the renderer
  automatically adapts to the canvas size.
- **D-13:** **SDF is downsampled** to match each stage's resolution using
  `torch.nn.functional.interpolate(mode='bilinear')`. The full-res SDF from Phase 4
  is the source; each stage gets an appropriately sized version.

### Convergence Detection
- **D-14:** **Rolling-window plateau detection (INNER-09):** Track loss values over the
  last `window=10` epochs. If `(max(window) - min(window)) / max(abs(max(window)), 1e-8) < epsilon`
  with `epsilon=0.001`, the stage is considered converged. Terminate early.
- **D-15:** **Minimum epochs before convergence check:** 20 epochs. Don't check for
  convergence in the first 20 epochs to allow the optimizer to warm up.

### Memory Hygiene
- **D-16:** **`.detach()` for all metrics (INNER-10):** Loss values logged for monitoring
  are `.detach().item()` — never retain the computation graph for logging.
- **D-17:** **`torch.cuda.empty_cache()` after each stage transition (INNER-10):**
  Called between resolution stages (e.g., after 8px completes, before 32px starts).
  NOT called per-epoch.
- **D-18:** **Gradient zeroing:** `optimizer.zero_grad(set_to_none=True)` per epoch
  for memory efficiency (avoids accumulating zero tensors).

### Public API
- **D-19:** **`InnerLoop` class** in `packages/engine/src/aerocloud/optimizer/inner_loop.py`.
  Constructor takes `DifferentiableRenderer`, SDF tensor, reference weights, and config.
  Method `optimize() -> OptimizationResult` runs the full Coarse-to-Fine pipeline.
- **D-20:** **`OptimizationResult` Pydantic model:** Contains final params tensor,
  per-stage loss history, total epochs, convergence flags per stage, wall clock time.
- **D-21:** **`LossWeights` Pydantic model:** Contains alpha, beta, gamma, lambda_ with
  defaults from D-06. Exposed in config for Phase 9 sweeps.

### Testing
- **D-22:** Test pyramid for Phase 6:
  - **Unit tests:** Each loss function independently (known input → exact output),
    gradient clipping verification, convergence detection on synthetic loss curves.
  - **Property tests (hypothesis):** Random params produce finite loss (no NaN/Inf),
    L_overlap >= 0, L_wmse >= 0, L_fidelity in [0, 2].
  - **Integration tests:** Full Coarse-to-Fine pipeline on 8px canvas converges
    within 100 epochs (ROADMAP success criterion 1).
  - **Determinism tests:** Same seed → identical loss curves over 10 runs.
  - **Memory tests:** RSS stable over 100 optimization steps.
  - Target: >= 35 new tests.
- **D-23:** Tests run on CPU by default. GPU tests marked `@pytest.mark.gpu`.

### Claude's Discretion
- Exact loss function implementation details within the formulas specified above
- Logging format and frequency (structlog integration)
- Internal helper functions in the optimizer module
- Test fixture design (sprite shapes, SDF patterns, canvas sizes)
- Exact file splits inside `optimizer/` as long as `InnerLoop` is the public API

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 6 requirements
- `.planning/ROADMAP.md` §"Phase 6: Inner Loop-v1" — phase goal, INNER-01..10, success criteria
- `.planning/REQUIREMENTS.md` §"Inner Loop-v1 (Phase 6)" — INNER-01..10 acceptance criteria

### Phase 5 contracts consumed by Phase 6
- `packages/engine/src/aerocloud/renderer/_renderer.py` — `DifferentiableRenderer(nn.Module)`,
  `forward(canvas_h, canvas_w) -> (1,1,H,W)` density tensor, `params` as `nn.Parameter(N,4)`
- `packages/engine/src/aerocloud/renderer/_sprites.py` — `register_glyph()`, `get_font_registry()`,
  `get_sprite_cache_size()`, `clear_caches()`
- `packages/engine/src/aerocloud/renderer/__init__.py` — public API exports
- `.planning/phases/05-renderer-v1/05-CONTEXT.md` — Phase 5 decisions (D-01..D-23)

### Phase 4 contracts consumed by Phase 6
- `packages/engine/src/aerocloud/geometry/sdf.py` — `compute_sdf()` for SDF tensor
  (L_wmse uses SDF as boundary fitness weight)
- `packages/engine/src/aerocloud/models/geometry.py` — `PlacementResult` for initial positions

### Foundation contracts
- `packages/engine/src/aerocloud/utils/determinism.py` — `set_seed()`
- `packages/engine/src/aerocloud/config.py` — `Settings` for config values
- `packages/engine/src/aerocloud/models/base.py` — `AeroCloudBase` for Pydantic models
- `packages/engine/src/aerocloud/observability.py` — structlog + OpenTelemetry

### Blueprint math
- `raw/sources/AeroCloud-Blueprint.md` §Teil V (Inner Loop formulas)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DifferentiableRenderer` — forward pass produces density tensor, `.params` is the
  optimization target. The renderer already handles variable canvas sizes (D-12).
- `compute_sdf()` from Phase 4 — produces float32 SDF with positive=inside convention.
  Needs downsampling for Coarse-to-Fine stages.
- `set_seed()` — determinism infrastructure ready.
- `AeroCloudBase` — Pydantic base for new models (OptimizationResult, LossWeights).

### Established Patterns
- **Pydantic-on-boundary, torch-in-hot-loop** — loss functions are pure torch internally,
  OptimizationResult wraps the output at the boundary.
- **Module-level caches with RLock** — if optimizer needs any caching (e.g., downsampled SDFs).
- **TDD with hypothesis** — property tests for loss function value ranges.

### Integration Points
- Phase 6 optimizer consumes Phase 5 `DifferentiableRenderer` as input
- Phase 6 produces `OptimizationResult` consumed by Phase 9 MAP-Elites
- Phase 6 `LossWeights` consumed by Phase 9 for weight sweeps
- New package: `packages/engine/src/aerocloud/optimizer/`

</code_context>

<specifics>
## Specific Ideas

- The Blueprint specifies exact Adam parameters (INNER-06) and exact loss formulas
  (INNER-01..05). These are NOT negotiable — the inner loop must implement the
  Blueprint math precisely.
- Coarse-to-Fine is the key performance optimization: 10x speedup vs single-resolution
  (ROADMAP success criterion 2). The 8px stage proves the math works, 32/128 refine,
  target produces the final result.
- L_overlap needs ADDITIVE compositing (sum of sprites), not alpha-over, to detect
  overlaps where density > 1.0. The renderer's alpha-over output caps at 1.0.
  The inner loop must call the renderer in a special mode or compute additive density
  separately.

</specifics>

<deferred>
## Deferred Ideas

### → Phase 7 Geometry-v2
- Advanced collision integration (the inner loop currently relies on L_overlap penalty
  rather than geometric collision detection)

### → Phase 9 Outer Loop-v1
- Loss weight sweeps (the LossWeights config enables this but Phase 6 uses fixed defaults)
- Quality metrics (LC, LU, SS) — Phase 6 only computes the 4 loss terms

### → Phase 10 Self-Play
- L_temporal with lambda > 0 for temporal coherence in live feeds

### → Phase 12 Production-v1
- Production performance budgets
- Celery task wrapper for the optimization loop
- SSE progress endpoint for real-time feedback

### Reviewed Todos (not folded)
No pending todos matched Phase 6 at discussion time.

</deferred>

---

*Phase: 06-inner-loop-v1*
*Context gathered: 2026-04-14 (auto mode — all decisions auto-selected with recommended defaults)*

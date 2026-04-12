# Phase 5: Renderer-v1 - Context

**Gathered:** 2026-04-12 (auto mode)
**Status:** Ready for planning

<domain>
## Phase Boundary

Build a PyTorch differentiable rasterizer that composites pre-rasterized glyph sprites
onto a 2D canvas with learnable parameters (position, scale, rotation). The forward pass
must produce a differentiable output tensor so Phase 6 Inner Loop can compute gradients
via `backward()`. This is a 2D sprite compositing renderer — NOT a 3D mesh rasterizer.

**Explicitly out of scope (→ Phase 6 Inner Loop-v1):** Loss functions, Adam optimizer,
Coarse-to-Fine pipeline, convergence detection. Phase 5 delivers the forward pass only.

**Explicitly out of scope (→ Phase 7 Geometry-v2):** Rotation collision (SAT), Bezier
paths, texture atlas optimization.

**Explicitly out of scope (→ Phase 12 Production-v1):** Multi-GPU, batch rendering,
production Celery worker integration, performance budgets beyond smoke tests.

</domain>

<decisions>
## Implementation Decisions

### Rasterization Backend
- **D-01:** **Pure PyTorch 2D soft-rasterization** — no nvdiffrast, no PyTorch3D.
  The Blueprint mentions nvdiffrast but the actual requirement is 2D differentiable
  compositing of pre-rasterized glyph sprites onto a canvas. nvdiffrast and PyTorch3D
  are 3D mesh rasterization pipelines — they solve a fundamentally different problem
  (triangle mesh → screen pixels). Our problem is: composite N pre-rasterized uint8
  glyph bitmaps onto a 2D canvas with differentiable position/scale/rotation transforms.
  Pure PyTorch `grid_sample` + `affine_grid` achieves this with zero external
  dependencies, full CPU fallback, and trivial gradient flow.
- **D-02:** **`torch.nn.functional.grid_sample`** for differentiable spatial transform.
  Each glyph sprite is a small (H, W) float32 tensor. `affine_grid` builds the
  sampling grid from the learnable (y, x, scale, rotation) parameters. `grid_sample`
  with `mode='bilinear'` and `padding_mode='zeros'` produces the transformed sprite
  with gradients flowing back to the transform parameters.
- **D-03:** **CPU fallback is mandatory** (PROJECT.md constraint). All torch operations
  must work on `torch.device('cpu')`. Tests run on CPU by default; GPU tests gated
  behind `pytest.mark.gpu` and `torch.cuda.is_available()`.
- **D-04:** **Compositing operator:** alpha-over with soft max. For each pixel, the
  output density is `1 - prod(1 - alpha_i)` where `alpha_i` is the transformed glyph
  opacity at that pixel. This is differentiable and handles overlap naturally. The
  density tensor is what Phase 6 Loss functions consume.

### Tensor Architecture
- **D-05:** **Packed (N, 4) parameter tensor** with columns `[y, x, scale, rotation]`.
  Single `nn.Parameter` with `requires_grad=True`. Adam optimizer (Phase 6) updates
  all N words simultaneously in one step.
- **D-06:** **Initialization from Phase 4 PlacementResult:**
  - `y, x` from `PlacedWord.y, PlacedWord.x` (integer center coordinates)
  - `scale = 1.0` (identity — Phase 4 already sized words correctly)
  - `rotation = 0.0` (no rotation in v1 placement, but the parameter exists for Phase 6)
  - Dropped words from Phase 4 are excluded from the tensor (only placed words enter).
- **D-07:** **(y, x) ordering internally** per D-14 carry-forward. PyTorch image
  convention is (H, W) = (y, x), so no conversion needed. The `affine_grid` matrix
  is constructed in (y, x) order.
- **D-08:** **Scale is uniform** (single scalar per word). Anisotropic scale is
  deferred to Phase 7.
- **D-09:** **Rotation is radians**, clamped to `[-pi, pi]` via `torch.remainder`
  in the forward pass to avoid unbounded growth during optimization.

### Glyph-Sprite Pipeline
- **D-10:** **Individual sprites, not atlas.** Each glyph is a separate (1, 1, H, W)
  float32 tensor on the target device. Atlas packing adds complexity with no benefit
  at v1 scale (< 200 words). Deferred to Phase 12 if profiling shows texture upload
  is a bottleneck.
- **D-11:** **Transfer path:** `GlyphBBox.pixel_buffer` (numpy uint8) →
  `torch.from_numpy(buf).float() / 255.0` → `.to(device)`. Cached in a module-level
  `dict[tuple[str, int, int], torch.Tensor]` keyed by `(font_family, size_pt, codepoint)`.
  Cache is populated once per render request, not per forward pass.
- **D-12:** **Font Registration Set:** Module-level `set[tuple[str, int]]` tracking
  `(font_family, size_pt)` pairs. Populated during the first render's glyph upload.
  REND-04 requires this Set has exactly N entries after first render and stays at N
  after 100 renders (leak test).
- **D-13:** **Sprite resolution matches Phase 4 glyph size.** No up/downsampling of
  glyph sprites in v1. The sprite tensor dimensions come directly from
  `GlyphBBox.pixel_buffer.shape`.

### Forward Pass Architecture
- **D-14:** **`DifferentiableRenderer` class** (not a bare function) inheriting from
  `torch.nn.Module`. This enables `model.parameters()`, `model.to(device)`,
  `model.train()`/`model.eval()` patterns that Phase 6 Adam optimizer expects.
- **D-15:** **Forward pass signature:**
  ```python
  def forward(self, canvas_h: int, canvas_w: int) -> torch.Tensor:
      # Returns (1, 1, H, W) density tensor in [0, 1]
  ```
  The learnable parameters (D-05) are `nn.Parameter` on the module. Canvas size is
  passed per call (Phase 6 Coarse-to-Fine changes resolution between stages).
- **D-16:** **Per-word affine transform in forward:**
  1. Extract `(y_i, x_i, s_i, theta_i)` from packed params
  2. Build 2x3 affine matrix: scale + rotate + translate
  3. `affine_grid(matrix, [1, 1, canvas_h, canvas_w])` → sampling grid
  4. `grid_sample(sprite_i, grid, mode='bilinear', padding_mode='zeros')` → transformed sprite
  5. Composite all sprites via alpha-over (D-04)
- **D-17:** **Canvas output is float32 tensor** in range [0, 1]. `0.0` = empty pixel,
  `1.0` = fully covered pixel. This is the density map that Phase 6 `L_overlap` and
  `L_wmse` consume.

### Determinism + Memory
- **D-18:** **`set_seed()` from Phase 1** with `warn_only=True` is sufficient. No
  nvdiffrast means no non-deterministic CUDA ops from external libraries. Pure PyTorch
  `grid_sample` respects `torch.use_deterministic_algorithms(True)`.
- **D-19:** **No gradient checkpointing in v1.** At 8px coarse resolution (REND-05 smoke
  test), memory is negligible. Phase 6 adds Coarse-to-Fine where checkpointing may
  become necessary at 128px+ — that decision belongs there.
- **D-20:** **RSS stability test:** Assert RSS delta < 50 MiB over 100 consecutive
  forward+backward passes. Uses `psutil.Process().memory_info().rss` before/after.
  Catches font/sprite tensor leaks.
- **D-21:** **`torch.cuda.empty_cache()`** called in test teardown only, not in
  production code. Production relies on PyTorch's caching allocator.

### Testing (Phase Exit Gate)
- **D-22:** Test pyramid for Phase 5:
  - **Unit tests:** affine matrix construction (identity, rotation, scale, combined),
    grid_sample on known sprite (1-pixel, checkerboard), alpha-over compositing
    (2 overlapping sprites), font registration set (add, dedup, count).
  - **Property tests (hypothesis):** random (N, 4) params produce non-NaN output
    tensor; output is in [0, 1] range; backward() does not raise for any params.
  - **Integration tests:** Phase 4 PlacementResult → DifferentiableRenderer → density
    tensor → backward() → gradient on params is non-zero.
  - **Determinism tests:** same seed, same input → byte-identical output tensor over
    10 runs.
  - **RSS test:** 100 consecutive forward+backward, RSS delta < 50 MiB.
  - **Font leak test:** Font Set has N entries after first render, still N after 100
    renders.
  - Target: >= 40 new tests.
- **D-23:** Tests run on CPU by default. GPU tests marked `@pytest.mark.gpu`.

### Claude's Discretion
- Exact `affine_grid` matrix construction (row-major vs column-major torch convention)
- Bilinear vs nearest interpolation mode (bilinear recommended, but Claude may switch
  to nearest if gradient issues arise)
- Exact alpha-over implementation (loop vs vectorized scatter)
- File splits inside `renderer/` as long as `DifferentiableRenderer` is the public API
- Test fixture design (sprite shapes, canvas sizes)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 5 requirements
- `.planning/ROADMAP.md` §"Phase 5: Renderer-v1" — phase goal, REND-01..06, success criteria
- `.planning/REQUIREMENTS.md` §"Renderer-v1 (Phase 5)" — REND-01..06 acceptance criteria

### Phase 4 contracts consumed by Phase 5
- `packages/engine/src/aerocloud/models/geometry.py` — `PlacedWord`, `PlacementResult`,
  `GlyphBBox`, `AABB`, `DropReason` Pydantic models (Phase 5 input contract)
- `packages/engine/src/aerocloud/geometry/placement.py` — `place_words()` output format
- `packages/engine/src/aerocloud/geometry/glyph.py` — `rasterize_glyph()` output format
- `packages/engine/src/aerocloud/geometry/sdf.py` — `compute_sdf()` for SDF tensor
  (consumed by Phase 6 L_wmse loss via the renderer's density output)
- `.planning/phases/04-geometry-v1/04-CONTEXT.md` §D-09 (SDF sign convention),
  §D-14 (y,x ordering), §D-32 (GlyphBBox), §D-43 (PlacementResult)

### Foundation contracts
- `packages/engine/src/aerocloud/utils/determinism.py` — `set_seed()` with `warn_only=True`
- `packages/engine/src/aerocloud/config.py` — `Settings.gpu_device` for torch device selection
- `packages/engine/src/aerocloud/fonts.py` — `font_path()` for TrueType file paths
- `packages/engine/src/aerocloud/models/base.py` — `AeroCloudBase` for any new Pydantic models
- `packages/engine/src/aerocloud/observability.py` — structlog + OpenTelemetry for metrics

### PyTorch documentation
- https://pytorch.org/docs/stable/generated/torch.nn.functional.grid_sample.html —
  `grid_sample` API, gradient behavior, padding modes
- https://pytorch.org/docs/stable/generated/torch.nn.functional.affine_grid.html —
  `affine_grid` API, theta matrix format
- https://pytorch.org/docs/stable/notes/randomness.html — determinism controls

### Research (nightly)
- `wiki/research/nightly/2026-04-11-pytorch-autograd-graph-memory.md` — autograd memory
  best practices, CVE-2026-19283 (moderate, not blocking torch 2.7.1)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `packages/engine/src/aerocloud/utils/determinism.py` — `set_seed()` already prepared
  for Phase 5 with `warn_only=True` comment
- `packages/engine/src/aerocloud/config.py` — `Settings.gpu_device` = `"cuda:0"` default,
  ready for `torch.device(settings.gpu_device)`
- `packages/engine/src/aerocloud/scripts/gpu_smoke.py` — already probes nvdiffrast import
  (line 58-63), can be updated to probe the new renderer module instead
- `packages/engine/src/aerocloud/models/geometry.py` — `PlacedWord`, `PlacementResult`,
  `GlyphBBox` are the input contracts; already carry `(y, x)` ordering and uint8 buffers
- `packages/engine/src/aerocloud/fonts.py` — `font_path(family)` resolves bundled fonts

### Established Patterns
- **Pydantic-on-boundary, numpy/torch-in-hot-loop** (Phase 2-4 pattern). D-14 continues
  this: `DifferentiableRenderer` accepts Pydantic models at construction, converts to
  tensors internally, never exposes Pydantic in the forward pass.
- **Module-level caches with RLock** (Phase 3-4 pattern for spaCy, SDF, glyph caches).
  D-11 sprite cache follows the same pattern.
- **`AeroCloudBase(frozen=True, strict=True, extra="forbid")`** for any new models.
- **Test fixtures as committed `.npy` files** (Phase 4 golden corpus). Phase 5 can
  commit small reference density tensors as `.pt` files for determinism tests.

### Integration Points
- Phase 5 renderer consumes Phase 4 `PlacementResult` + `GlyphBBox` as input
- Phase 5 renderer produces density tensor consumed by Phase 6 Loss functions
- Phase 5 `DifferentiableRenderer.parameters()` consumed by Phase 6 Adam optimizer
- `packages/engine/src/aerocloud/renderer/` is the new package (matches CLAUDE.md
  Engine-Module list `src/renderer/`)

</code_context>

<specifics>
## Specific Ideas

- The key insight driving D-01: nvdiffrast solves `3D mesh → 2D screen` which requires
  triangle definitions, vertex buffers, and a rasterization pipeline. Our problem is
  `2D sprite + affine transform → 2D canvas` which is natively solved by PyTorch's
  `grid_sample`. Using nvdiffrast would mean artificially converting 2D sprites into
  3D meshes (two triangles per quad) just to use a 3D rasterizer — adding complexity
  and a hard-to-build dependency for zero benefit.
- Phase 4's architect mantra carries forward: "Absolutes Scope-Creep-Verbot. Vertikaler
  Durchstich." Phase 5 delivers the minimal differentiable forward pass that Phase 6
  can optimize. No bells, no whistles.
- The `grid_sample` approach means the entire renderer is ~150-250 lines of pure PyTorch
  with zero external dependencies beyond torch itself. This dramatically simplifies CI,
  Docker builds, and CPU fallback.

</specifics>

<deferred>
## Deferred Ideas

### → Phase 6 Inner Loop-v1
- Loss functions (L_wmse, L_overlap, L_fidelity, L_temporal) — these consume the
  density tensor from D-17 but are NOT part of the renderer
- Adam optimizer integration
- Coarse-to-Fine resolution scaling (the renderer supports variable canvas_h/canvas_w
  per D-15, but the scheduling logic is Phase 6)
- Gradient checkpointing (may be needed at 128px+ resolution)

### → Phase 7 Geometry-v2
- Rotation collision (SAT) — the renderer supports rotation (D-09) but collision
  detection for rotated words is Phase 7
- Anisotropic scale (D-08 locks uniform scale for v1)
- Bezier path rendering

### → Phase 12 Production-v1
- Texture atlas optimization (D-10 defers this)
- Multi-GPU rendering
- Batch rendering (multiple word clouds in one forward pass)
- Performance budgets and production profiling
- nvdiffrast evaluation for production quality (if grid_sample proves insufficient)

### Reviewed Todos (not folded)
No pending todos matched Phase 5 at discussion time.

</deferred>

---

*Phase: 05-renderer-v1*
*Context gathered: 2026-04-12 (auto mode — all decisions auto-selected with recommended defaults)*

# Phase 7: Geometry-v2 - Context

**Gathered:** 2026-04-15 (assumptions mode, --auto)
**Status:** Ready for planning

<domain>
## Phase Boundary

Full geometric machinery: Medial Axis Transform with pruning, Multi-Centric word placement (one spiral origin per MAT branch), 5-stage collision hierarchy (AABB → BVH → Quadtree → SAT → Bitmap), and Bezier path representation for word boundaries. Extends Phase 4 Geometry-v1 infrastructure.

9 Requirements: GEO2-01 to GEO2-09.
</domain>

<decisions>
## Implementation Decisions

### MAT Construction and Pruning (GEO2-01, GEO2-02)
- **D-01:** MAT skeleton derived from existing float32 SDF ridge points (local maxima of inside EDT), NOT by running scikit-fmm from scratch. scikit-fmm used only for travel-time gradient needed to orient branch directions for Multi-Centric origin assignment.
- **D-02:** MAT pruning uses radius threshold as fast pre-filter (min_branch_radius via Pydantic settings), then CAT-style topology cleanup for remaining branches. Combines speed with quality.
- **D-03:** scikit-fmm (`>=2025.6.23`) must be installed as geometry extra. Travel-time computation on masked domain with float32 output.
- **D-04:** New submodules: `geometry/mat.py` (skeleton extraction + pruning), `geometry/mat_cache.py` (optional, if MAT is expensive enough to cache per SDF).

### Collision Pipeline (GEO2-04 to GEO2-08)
- **D-05:** 5-stage collision extends existing `collision.py` with NEW functions alongside `aabb_overlap` and `has_any_collision`. Function-based API per D-02 lock. No class-based CollisionSystem.
- **D-06:** Stage ordering: 1-AABB (existing) → 2-BVH (broadphase, routes to stages 3-5 on hit) → 3-Quadtree (spatial index) → 4-SAT (rotated rectangles) → 5-Bitmap (pixel-exact). Each stage is a separate function with clear skip conditions.
- **D-07:** BVH (Stage 2) is pure Python/numpy binary tree with recursive axis-aligned split on `(N,4) int32` AABB arrays. LRU cache + RLock per D-17/D-22 lock from Phase 4. No external BVH library (no rtree dependency).
- **D-08:** Quadtree (Stage 3) in new `geometry/quadtree.py`. Max depth configurable via Pydantic settings.
- **D-09:** SAT (Stage 4) operates purely in geometry/collision layer — NOT differentiable, no gradient interaction with Phase 5 renderer. Hard reject only during placement. Rotation values read from placement params, not from nn.Parameter.
- **D-10:** Bitmap collision (Stage 5) uses uint32 packed bitmask for pixel-exact overlap on final placement verification. Lives in `geometry/collision.py`.
- **D-11:** BVH LRU cache (GEO2-08) stores built-tree bytes using cachetools pattern from sdf_cache.py. blake3 key includes word count + AABB array hash.

### Multi-Centric Placement (GEO2-03)
- **D-12:** Multi-Centric is a pre-pass that partitions the word list into N sublists (one per MAT branch), then calls existing placement pipeline per branch on masked sub-SDFs. Reuses full `place_words` pipeline per branch.
- **D-13:** Word-to-branch assignment proportional to branch SDF volume (sum of SDF values in each branch's Voronoi cell). Deterministic: same input → same assignment.
- **D-14:** Falls back to single-origin placement if MAT produces only 1 branch (e.g., simple circle/square masks). Transparent to caller.
- **D-15:** Carries forward D-38 (per-word adaptive POI) and D-45 (determinism guarantee) from Phase 4. New determinism tests required for Multi-Centric path.

### Bezier Path Representation (GEO2-09)
- **D-16:** Bezier paths computed per-glyph from GlyphBBox.pixel_buffer (uint8 numpy array from Phase 4). OpenCV `cv2.findContours` + cubic spline fitting.
- **D-17:** New Pydantic model `BezierGlyph` alongside existing `GlyphBBox` (cannot subclass — GlyphBBox is frozen). Carries list of BezierCurve segments per glyph contour.
- **D-18:** opencv-python-headless (`>=4.10.0`) already declared in pyproject.toml geometry extras.
- **D-19:** Bezier is per-glyph NOT per-silhouette. Phase 12 export consumes glyph-level paths for SVG/PDF sub-millimeter precision.

### Renderer Dual-Mode Output (Phase 6 F-3 carry-forward)
- **D-20:** DifferentiableRenderer gets `forward(h, w, mode='alpha_over')` extended with `mode='both'` returning `(density, additive_density)` tuple. Resolves Phase 6 F-3 (double forward pass) and F-10 (private coupling).
- **D-21:** `compute_additive_density()` in loss.py deleted after renderer produces both outputs. InnerLoop.optimize() updated to consume tuple.

### Claude's Discretion
- Exact Quadtree max depth default
- BVH split heuristic choice (surface area heuristic vs longest axis)
- Bezier fitting tolerance parameter
- MAT ridge detection threshold
- Whether MAT cache is separate module or extends SDF cache
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Geometry-v1 (Phase 4 — foundation)
- `.planning/phases/04-geometry-v1/04-CONTEXT.md` — 51 locked decisions (D-01..D-51), coordinate dogma, SDF convention, cache pattern
- `wiki/decisions/2026-04-09-phase-4-sdf-sign-convention.md` — ADR-0004: SDF positive=inside UNCHANGEABLE
- `wiki/decisions/2026-04-09-phase-4-coordinate-system-yx.md` — ADR-0005: (y,x) canonical
- `wiki/knowledge/phase-4-known-limits.md` — place_words 24.85s performance, scipy.ndimage.minimum_filter bottleneck

### Renderer (Phase 5) + Inner Loop (Phase 6)
- `.planning/phases/05-renderer-v1/05-CONTEXT.md` — DifferentiableRenderer design, grid_sample architecture
- `.planning/phases/06-inner-loop-v1/06-CONTEXT.md` — Loss functions, InnerLoop contract
- `wiki/knowledge/phase-6-known-limits.md` — F-3 double forward, F-9 thread safety, F-10 coupling

### Source code to read
- `packages/engine/src/aerocloud/geometry/` — All v1 geometry modules (mask, sdf, sdf_cache, collision, glyph, placement)
- `packages/engine/src/aerocloud/renderer/_renderer.py` — DifferentiableRenderer.forward()
- `packages/engine/src/aerocloud/optimizer/loss.py` — compute_additive_density (to be deleted)
- `packages/engine/src/aerocloud/optimizer/inner_loop.py` — InnerLoop.optimize() (to be updated)

### Research
- `.planning/research/FEATURES.md` §5 — MAT maturity ("Research-grade, pruning is the major hurdle")
- `.planning/research/PITFALLS.md` — #5 MAT pruning instability
- `wiki/research/nightly/` — Nightly research on NP-Hard bin packing, 5-stage collision, seam carving
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `geometry/sdf.py` — Exact Meijster EDT (float32), ridge points = medial axis
- `geometry/sdf_cache.py` — LRU + blake3 + RLock pattern (template for BVH cache)
- `geometry/collision.py` — `aabb_overlap()`, `has_any_collision()` vectorized int32 AABB
- `geometry/placement.py` — `place_words()`, `_spiral_search()`, `select_origin()`, `archimedean_offsets()`, DropReason enum
- `geometry/glyph.py` — `GlyphBBox.pixel_buffer` (uint8 numpy) for Bezier contour extraction
- `opencv-python-headless>=4.10.0` already in pyproject.toml geometry extras

### Established Patterns
- Function-based public API, Pydantic at boundaries (D-02)
- (y,x) canonical internally (D-14)
- bytes-bounded cachetools LRU + blake3 key + RLock (D-17/D-22)
- structlog + OTel counters for observability (D-48/D-49)
- Hypothesis property tests + determinism + benchmark (Nyquist 8-dim)

### Integration Points
- `place_words()` — Multi-Centric wraps existing pipeline
- `collision.py` — New stages added alongside existing AABB
- `DifferentiableRenderer.forward()` — Dual-mode output for F-3 fix
- `InnerLoop.optimize()` — Consumes new renderer tuple
- `GlyphBBox.pixel_buffer` — Bezier path source
</code_context>

<specifics>
## Specific Ideas

- Phase 4 performance bottleneck (24.85s) should improve via Multi-Centric (parallel branch placement) and BVH (faster collision than brute-force AABB scan)
- EdWordle paper BVH is specifically a Two-Level Box hierarchy — research needed on original paper's split heuristic
- Bezier paths must be sub-millimeter precise for Phase 12 SVG/PDF export

</specifics>

<deferred>
## Deferred Ideas

- Persistent disk BVH cache — Phase 12 (same as SDF disk cache deferral)
- Adaptive MAT pruning based on word count — Phase 12 optimization
- GPU-accelerated collision (CUDA kernels for Stage 5 bitmap) — Phase 12 if needed
- Differentiable SAT for gradient-based collision avoidance — Future research, not v1

</deferred>

---

*Phase: 07-geometry-v2*
*Context gathered: 2026-04-15*

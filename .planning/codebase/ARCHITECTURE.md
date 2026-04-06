# Architecture

**Analysis Date:** 2026-04-06

## Pattern Overview

**Overall:** Dual-Loop Quality-Diversity Engine with Self-Maintaining Knowledge Base

**Key Characteristics:**
- **Inner Loop (GPU Exploitation):** PyTorch-based differentiable rendering with Adam optimizer for layout refinement
- **Outer Loop (Quality-Diversity Exploration):** MAP-Elites algorithm with CQD metrics for multi-objective optimization
- **Knowledge Layer:** Karpathy LLM Wiki pattern for self-maintaining technical documentation and domain knowledge
- **Modular Pipeline:** Clear separation of 5 core domains: NLP, Geometry, Renderer, Optimizer, Export

## Layers

**NLP Layer:**
- Purpose: Text analysis and semantic understanding - TF-IDF scoring, BERT embeddings, Zipf law normalization
- Location: `src/nlp/` (to be implemented)
- Contains: Keyword extraction, semantic similarity scoring, optimal transport (Sinkhorn-Knopp)
- Depends on: External NLP libraries (natural, compromise, sentence-transformers)
- Used by: Geometry layer for semantic-aware placement

**Geometry Layer (The Skeleton):**
- Purpose: Shape analysis, collision detection, medial axis transformation
- Location: `src/geometry/` (to be implemented)
- Contains: SDF (Signed Distance Fields), Medial Axis Transform, Quadtree spatial indexing, collision hierarchies
- Depends on: NLP layer outputs, mathematical primitives
- Used by: Renderer and Optimizer for layout constraints

**Renderer Layer (The Muscles):**
- Purpose: Differentiable soft-rasterization and layout rendering with per-word optimization
- Location: `src/renderer/` (to be implemented)
- Contains: Differentiable rendering pipeline, loss function computation, gradient propagation
- Depends on: Geometry layer for collision/constraint data, PyTorch for differentiable operations
- Used by: Optimizer's inner loop for layout refinement

**Optimizer Layer (The Brain):**
- Purpose: Meta-optimization combining inner loop (Adam) and outer loop (MAP-Elites) strategies
- Location: `src/optimizer/` (to be implemented)
- Contains: Adam optimizer for fine-grained layout, MAP-Elites archive, CQD metrics, BOP-Elites variant
- Depends on: Renderer for fitness evaluation, NLP for behavior dimensions
- Used by: Main entry point for orchestration

**Export Layer:**
- Purpose: Post-processing and vector export with quality preservation
- Location: `src/export/` (to be implemented)
- Contains: Seam carving for whitespace compression, Bezier curve math, SVG/PDF generation
- Depends on: Geometry layer for final shape data
- Used by: Final output generation

**Knowledge Base Layer (Self-Maintaining):**
- Purpose: Karpathy LLM Wiki - maintains evolving domain knowledge
- Location: `wiki/` (LLM-maintained), `raw/sources/` (immutable sources)
- Contains: Markdown pages organized by domain (Math, Semantics, Geometry, Inner/Outer Loop, Post-Processing)
- Depends on: Wiki tooling scripts in `scripts/`
- Used by: All development phases for reference and context preservation

## Data Flow

**Standard Word Cloud Generation Flow:**

1. **Text Input Phase** → NLP Layer
   - Input: Raw text + target silhouette shape
   - Process: Tokenization, stop-word removal, TF-IDF-AP scoring, log-normalization
   - Output: reference_weights tensor (frozen), semantic embeddings

2. **Semantic Projection** → NLP Layer → Geometry Layer
   - Process: BERT embeddings → t-SNE/UMAP dimensionality reduction
   - Process: Optimal Transport (Sinkhorn-Knopp) for initial placement
   - Output: Word positions on 2D canvas with semantic coherence

3. **Geometry Analysis** → Geometry Layer
   - Process: SDF generation for silhouette, Medial Axis Transform for structure
   - Process: 5-level collision hierarchy initialization
   - Output: Constraint manifold for optimization

4. **MAP-Elites Outer Loop** → Optimizer Layer
   - Per iteration: Sample behavior dimensions (Space-Similarity, Rotation Distribution, Symmetry)
   - Process: Initialize layout in behavior cell
   - Trigger: Inner Loop invocation for each candidate

5. **Differentiable Rendering Inner Loop** → Renderer + Optimizer
   - Per candidate: ~100 Adam optimizer epochs
   - Parameters: Position (x, y), Scale, Rotation (all with requires_grad=True)
   - Loss computation: Multi-objective (packing density, collision avoidance, readability, semantic coherence)
   - Output: Converged layout for archive storage

6. **MAP-Elites Archive Update** → Optimizer Layer
   - Evaluate fitness and behavior dimensions
   - Store in archive if improves cell quality or novelty
   - Continue outer loop iterations (typically 700 for BOP-Elites)

7. **Post-Processing** → Export Layer
   - Process: Seam carving to remove inactive whitespace
   - Process: Bezier curve extraction from rasterized word boundaries
   - Output: SVG/PDF vectors with full quality preservation

**State Management:**
- **Frozen reference_weights tensor:** Immutable after TF-IDF-AP normalization
- **MAP-Elites archive:** Persistent multi-objective solution set indexed by behavior dimensions
- **Per-layout parameters:** Word positions, scales, rotations maintained during optimization
- **Silhouette SDF:** Precomputed and cached for all iterations

## Key Abstractions

**Quality-Diversity Metrics:**
- Purpose: Multi-objective fitness evaluation beyond single-objective optimization
- Examples: `wiki/cqd-metric.md`, `wiki/quality-metrics.md`
- Pattern: Behavior descriptor space (continuous features) + fitness archive allowing diverse solutions

**5-Level Collision Hierarchy:**
- Purpose: Efficient collision detection with increasing precision
- Examples: `wiki/collision-detection.md`
- Pattern: AABB → Two-Level Box → Quadtree → SAT → Pixel-Perfect (progressive refinement)

**Differentiable Rendering:**
- Purpose: Enable gradient-based optimization of layout parameters
- Examples: `wiki/differentiable-rendering.md`
- Pattern: Soft-rasterization with differentiable loss, not hard pixel collision

**Signed Distance Fields (SDF):**
- Purpose: Continuous shape representation enabling gradient-based geometry operations
- Examples: `wiki/sdf-geometry.md`
- Pattern: Distance function with sign indicating inside/outside, gradient points to boundary

**Irregular Bin Packing:**
- Purpose: Formalize the core computational problem
- Examples: `wiki/np-hard-packing.md`
- Pattern: NP-hard problem requiring heuristic solutions via quality-diversity exploration

## Entry Points

**Main Application Entry Point:**
- Location: `src/index.ts`
- Triggers: CLI invocation via `npm run dev` or `npm run build`
- Responsibilities: Module exports and version logging; currently stubs for all 5 modules

**Wiki Ingestion Entry Point:**
- Location: `scripts/ingest.ts`
- Triggers: `npm run wiki:ingest raw/sources/<file>`
- Responsibilities: Parse source documents, auto-detect sections, create wiki pages with frontmatter, maintain index and log

**Wiki Query Entry Point:**
- Location: `scripts/query.ts`
- Triggers: `npm run wiki:query "<keywords>"`
- Responsibilities: Search wiki index by keyword relevance, synthesize knowledge for LLM context

**Wiki Maintenance Entry Point:**
- Location: `scripts/lint-wiki.ts`
- Triggers: `npm run wiki:lint`
- Responsibilities: Detect orphaned pages, broken links, inconsistencies, suggest corrections

## Error Handling

**Strategy:** Progressive validation from input to output with early failure

**Patterns:**
- **Input Validation:** Text normalization with explicit character bounds; silhouette polygon validation
- **Geometry Assertions:** SDF validity checks, collision detection thresholds, boundary crossings
- **Optimizer Convergence:** Loss monitoring, NaN detection, fallback to previous best state
- **Post-Processing Safety:** Bezier smoothing with smoothness bounds, export format validation
- **Graceful Degradation:** If inner loop fails to converge, use best-so-far; if collision resolution fails, skip word; if export fails, provide PNG fallback

## Cross-Cutting Concerns

**Logging:** Structured logging per layer with optimization step tracking (loss, gradients, collision count). Location: To be implemented in each module.

**Validation:** 
- Type validation via TypeScript strict mode
- Geometry constraints: All coordinates bounded to silhouette, no negative scales
- Numeric stability: NaN/Inf guards in optimizer, soft-clipping in renderer

**Authentication:** Not applicable (single-user rendering engine)

**Performance Considerations:**
- SDF computation parallelizable via GPU (deferred to PyTorch layer)
- Quadtree O(n log n) for n words
- Optimal Transport O(n²) but computed once during initialization
- Inner loop (~100 epochs × ~50 words) vectorized via PyTorch
- Outer loop (700 iterations) decoupled from inner loop, can run asynchronously

---

*Architecture analysis: 2026-04-06*

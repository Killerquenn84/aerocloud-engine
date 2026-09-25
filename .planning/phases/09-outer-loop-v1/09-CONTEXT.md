# Phase 9: Outer Loop-v1 - Context

**Gathered:** 2026-04-18 (assumptions mode)
**Status:** Ready for planning

<domain>
## Phase Boundary

MAP-Elites archive with quality metrics, novelty search, archive persistence. pyribs GridArchive as backend, InnerLoop.optimize() as fitness evaluator, semantic_warm_start() as initialization, PostgreSQL archive_v1 for persistence.

Requirements: OUTER-01 to OUTER-07.

</domain>

<decisions>
## Implementation Decisions

### pyribs Archive Configuration
- **D-01:** Use pyribs `GridArchive` (not CVTArchive) with 4 behavioral descriptor dimensions matching existing BehaviorDescriptor model: shape_fidelity, rotation_ratio, symmetry, semantic_clustering. All bounded [0.0, 1.0].
- **D-02:** Grid resolution: 10 bins per dimension = 10,000 cells. Configurable via `AeroCloudSettings.archive_bins_per_dim: int = 10`.
- **D-03:** Use `MapElitesBaselineEmitter` for v1 (random perturbation). BOP-Elites emitter deferred to Phase 11.

### Fitness Function
- **D-04:** Fitness is a composite of 5 quality metrics (OUTER-03), NOT raw InnerLoop loss. Each InnerLoop evaluation produces OptimizationResult → quality metrics computed post-hoc on final layout.
- **D-05:** Quality metric definitions:
  - LC (Layout Coverage): ratio of ink pixels inside silhouette to total silhouette area
  - LU (Layout Uniformity): 1 - normalized std dev of local density (subdivide into K×K grid)
  - SS (Space-Saving): 1 - (whitespace inside silhouette / silhouette area)
  - Compactness: 4π × area / perimeter² (isoperimetric quotient of placed word bounding hull)
  - Aspect Ratio: 1 - |actual_ratio - φ| / φ where φ = 1.618
- **D-06:** Semantic metrics (OUTER-04):
  - Realized Adjacencies: fraction of semantically-similar word pairs that are spatially adjacent
  - Distortion: mean ratio of spatial distance to embedding distance for all word pairs
- **D-07:** Combined fitness = weighted sum of all metrics. Default weights configurable via LossWeights-style Pydantic model.

### Archive Persistence
- **D-08:** Extend existing `archive_v1` table via Alembic migration 0003. Add columns: `shape_fidelity REAL`, `rotation_ratio REAL`, `symmetry REAL`, `semantic_clustering REAL`, `params_blob BYTEA` (safetensors format), `quality_metrics JSONB`.
- **D-09:** `descriptor vector(384)` column stores layout-level aggregate BERT embedding (mean of placed word embeddings). Behavioral descriptor scalars stored in dedicated columns for indexing.
- **D-10:** `ON CONFLICT (bin_id) DO UPDATE WHERE EXCLUDED.fitness > archive.fitness` per OUTER-05.
- **D-11:** pyribs in-memory archive is primary during run. Batch flush to PostgreSQL every 100 evaluations + final flush at run end. Load from PostgreSQL at startup to resume.

### Novelty Search & Monitoring
- **D-12:** Novelty search via descriptor-space k-NN distance. Before adding to archive, compute mean distance to k=15 nearest archive entries. If novelty > threshold, boost exploration. Custom emitter wrapper around pyribs.
- **D-13:** Saturation monitoring: track archive coverage % (filled cells / total cells) per evaluation batch. Alert if coverage plateaus (< 1% growth over 100 evaluations).
- **D-14:** Periodic re-evaluation (OUTER-07): every 200 evaluations, re-run InnerLoop on top-N elites with current parameters. If fitness drops > 10%, flag as drifted and replace.

### Integration Points
- **D-15:** Each MAP-Elites evaluation: semantic_warm_start() → DifferentiableRenderer(params) → InnerLoop.optimize() → OptimizationResult → compute quality metrics → archive.add(descriptor, fitness, solution)
- **D-16:** Solution representation: the (N,4) params tensor from optimizer output (positions, scales, rotations of placed words).
- **D-17:** Behavioral descriptors computed from the optimized layout (post-optimization, not from the params tensor directly).

### Claude's Discretion
- pyribs scheduler choice (RoundRobinScheduler vs custom)
- Exact k-NN implementation for novelty (sklearn BallTree vs brute force)
- Batch size for PostgreSQL flush
- Quality metric grid subdivision K for Layout Uniformity
- Re-evaluation sample strategy (random vs top-fitness)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### MAP-Elites & Quality Metrics
- `wiki/map-elites.md` — MAP-Elites archiving, BOP-Elites, behavioral descriptors
- `wiki/cqd-metric.md` — CQD score equation, theta-sweep, Pareto-Front (Phase 11 preview)
- `wiki/quality-metrics.md` — Geometric and semantic quality metrics definitions

### Existing Integration Points
- `packages/engine/src/aerocloud/optimizer/inner_loop.py` — `InnerLoop.optimize() → OptimizationResult`
- `packages/engine/src/aerocloud/semantic/warm_start.py` — `semantic_warm_start()` → (N,4) params
- `packages/engine/src/aerocloud/semantic/embeddings.py` — `encode_surfaces()` for descriptor embedding
- `packages/engine/src/aerocloud/renderer/_renderer.py` — `DifferentiableRenderer(params_n4, sprites, device)`
- `packages/engine/src/aerocloud/models/archive.py` — `MapElitesEntry`, `BehaviorDescriptor` Pydantic models

### Persistence
- `infra/alembic/versions/0001_baseline.py` — `archive_v1` table schema (bin_id, descriptor vector(384), fitness, metadata)
- `packages/engine/src/aerocloud/semantic/persistence.py` — asyncpg pattern for pgvector (reuse for archive)
- `packages/engine/src/aerocloud/config.py` — `AeroCloudSettings` (add archive config fields)

### Determinism & Cache
- `packages/engine/src/aerocloud/utils/determinism.py` — `set_seed()` for reproducibility
- `packages/engine/src/aerocloud/geometry/sdf_cache.py` — blake3 + LRU + RLock pattern

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `MapElitesEntry` + `BehaviorDescriptor` Pydantic models already defined in models/archive.py
- `archive_v1` table with HNSW index — ready for Phase 9 writes
- `asyncpg` persistence pattern from Phase 8 semantic/persistence.py
- `InnerLoop.optimize()` → `OptimizationResult` — fitness evaluator ready
- `semantic_warm_start()` → (N,4) params — initialization ready
- `encode_surfaces()` → (N,384) embeddings — for layout-level aggregate descriptor

### Established Patterns
- TDD Red→Green, Pydantic frozen+strict+forbid, (y,x) coordinates
- Config via Pydantic Settings, caches via blake3+LRU+RLock
- safetensors for tensor serialization (not pickle)

### Integration Points
- semantic_warm_start() → DifferentiableRenderer → InnerLoop → quality metrics → archive
- PostgreSQL archive_v1 table for persistence
- pyribs GridArchive for in-memory MAP-Elites

</code_context>

<specifics>
## Specific Ideas

- Success criterion 1: After 1000 evaluations, archive coverage > 30% of behavior grid
- Success criterion 2: Concurrent inserts to same bin keep best fitness (PostgreSQL-level)
- Success criterion 5: Archive export/import is deterministic (safetensors for params)
- Sinkhorn convergence comparison (SC5 from Phase 8) can now be measured here

</specifics>

<deferred>
## Deferred Ideas

- BOP-Elites (Bayesian Optimization emitter) — Phase 11 OUTER2-01
- CQD metric computation — Phase 11 OUTER2-03
- Pareto-Front + Pareto-Slider — Phase 11 OUTER2-07/08
- GPU-accelerated archive operations — Phase 12

</deferred>

---

*Phase: 09-outer-loop-v1*
*Context gathered: 2026-04-18*

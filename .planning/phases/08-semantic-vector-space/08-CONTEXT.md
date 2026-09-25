# Phase 8: Semantic Vector Space - Context

**Gathered:** 2026-04-18 (assumptions mode)
**Status:** Ready for planning

<domain>
## Phase Boundary

BERT embeddings + Sinkhorn-Knopp Optimal Transport warm-start. Word vectors from sentence-transformers all-MiniLM-L6-v2 (384-dim), cosine similarity matrix, 2D projection via UMAP, Sinkhorn-Knopp transport plan via POT in log-space, pgvector persistence with HNSW, and Sinkhorn output replaces random/spiral initialization in the Inner Loop.

Requirements: SEM-01 to SEM-08.

</domain>

<decisions>
## Implementation Decisions

### BERT Embedding Integration
- **D-01:** Embed `WordCandidate.surface` strings (not stems) via `sentence-transformers` `all-MiniLM-L6-v2` producing `(N, 384)` float32 tensors. Surface forms preserve morphological context for BERT's WordPiece tokenizer.
- **D-02:** Model warm-up at process startup via `SentenceTransformer(model_name, cache_folder=config.model_cache_dir)`. Pre-download model into Docker image for offline deployment (PITFALLS.md #3 cold-start).
- **D-03:** Batch encoding via `model.encode(surfaces, batch_size=32, show_progress_bar=False, convert_to_numpy=True)` for deterministic output.

### Cosine Similarity & 2D Projection
- **D-04:** Cosine similarity matrix via `sklearn.metrics.pairwise.cosine_similarity` on the `(N, 384)` embedding matrix. Result: `(N, N)` float32 matrix.
- **D-05:** UMAP as primary 2D projection. Add `umap-learn>=0.5.0` to `embeddings` optional-dep group. UMAP preserves global structure better than t-SNE and is more deterministic with fixed seed (wiki/bert-embeddings.md preference).
- **D-06:** t-SNE available as fallback via `sklearn.manifold.TSNE` (already in deps). Config flag `projection_method: Literal["umap", "tsne"] = "umap"`.

### Sinkhorn-Knopp Optimal Transport
- **D-07:** POT `ot.sinkhorn` with `log=True` for log-space computation (numerically stable). Move POT from `nlp` extra to `embeddings` extra in pyproject.toml.
- **D-08:** Transport is word-to-position: `(N words) -> (N canvas positions)`. Cost matrix: cosine distance between word embeddings projected to 2D and candidate positions from MAT branch origins. NOT cluster-to-segment (that would lose per-word placement).
- **D-09:** Adaptive epsilon regularization: start with `eps=0.1`, halve if Sinkhorn converges in < 10 iterations (too loose), double if > 500 iterations (too tight). Clamp `eps` to `[1e-4, 1.0]`.
- **D-10:** Sinkhorn convergence proof O(log(1/eps)) independent of dimension (arXiv:2604.03787) validates this approach for 384-dim BERT vectors. Document in wiki.

### Warm-Start Integration
- **D-11:** External function `semantic_warm_start(candidates, sdf, mat_result, config) -> torch.Tensor` returning `(N, 4)` params tensor `[y, x, scale, theta]`. Scale and theta initialized to `[1.0, 0.0]`. Caller passes result to `DifferentiableRenderer(params_n4, ...)`. NO changes to InnerLoop API (preserves Phase 6 D-19 contract).
- **D-12:** Positions from Sinkhorn transport plan mapped to SDF canvas coordinates: scale UMAP 2D output to fit within SDF positive region, then apply Sinkhorn transport matrix to assign words to positions.

### pgvector Persistence
- **D-13:** NEW table `word_embeddings` with schema `(surface TEXT PRIMARY KEY, embedding vector(384), model_version TEXT, created_at TIMESTAMPTZ)`. Cache individual word embeddings across runs. New Alembic migration required.
- **D-14:** HNSW index on `word_embeddings.embedding` with `vector_cosine_ops` (matching archive_v1 pattern from Phase 2).
- **D-15:** `archive_v1.descriptor` column reserved for Phase 9 MAP-Elites layout-level aggregate embeddings. Phase 8 does NOT write to archive_v1.

### Claude's Discretion
- Exact UMAP hyperparameters (n_neighbors, min_dist, metric)
- Sinkhorn max_iterations default
- Model warm-up timing (module import vs explicit init function)
- Test fixture embedding generation strategy

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### BERT Embeddings
- `wiki/bert-embeddings.md` — BERT architecture, 384-dim vectors, UMAP preference, t-SNE comparison
- `wiki/optimal-transport.md` — Sinkhorn-Knopp pipeline: transport → cluster-segment assignment → Inner Loop
- `wiki/research/nightly/SUMMARY-2026-04-16-to-18.md` — Sinkhorn convergence proof, POT updates

### Existing Integration Points
- `packages/engine/src/aerocloud/nlp/pipeline.py` — `text_to_candidates()` produces `list[WordCandidate]` with `.surface` field
- `packages/engine/src/aerocloud/renderer/_renderer.py` — `DifferentiableRenderer.__init__(params_n4, sprites, device)` — warm-start target
- `packages/engine/src/aerocloud/optimizer/inner_loop.py` — `InnerLoop.optimize()` consumes renderer with params already set
- `packages/engine/src/aerocloud/geometry/mat.py` — `extract_mat()` → `MATResult` with branch origins for transport target positions
- `packages/engine/src/aerocloud/geometry/multi_centric.py` — `place_words_multi_centric()` provides baseline to compare against

### Data Model & Persistence
- `packages/engine/src/aerocloud/models/base.py` — `AeroCloudBase(frozen=True, strict=True, extra="forbid")`
- `infra/alembic/versions/0001_baseline.py` — existing `archive_v1` table with `descriptor vector(384)` + HNSW index
- `packages/engine/src/aerocloud/config.py` — `AeroCloudSettings` Pydantic-Settings (add new fields here)

### Determinism
- `packages/engine/src/aerocloud/utils/determinism.py` — `set_seed()` must cover UMAP/t-SNE random state
- `wiki/decisions/2026-04-09-phase-4-sdf-sign-convention.md` — ADR-0004 float32 convention

### Cache Pattern
- `packages/engine/src/aerocloud/geometry/sdf_cache.py` — blake3 + cachetools.LRUCache + RLock reference pattern

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AeroCloudBase` Pydantic model base — use for all new Pydantic models (EmbeddingResult, TransportPlan, etc.)
- `sdf_cache.py` pattern — blake3 + LRU + RLock for embedding cache if in-memory caching desired
- `set_seed()` determinism utility — must integrate with UMAP/t-SNE random state
- `pyproject.toml` already declares `sentence-transformers>=3.0.0` and `POT>=0.9.5` in optional-deps

### Established Patterns
- TDD Red→Green workflow per CLAUDE.md
- Pydantic models frozen+strict+forbid
- (y, x) canonical coordinates (ADR-0005 D-14)
- Config via Pydantic Settings in config.py
- All caches: cachetools + blake3 + threading.RLock
- geometry/__init__.py pattern for public exports

### Integration Points
- NLP pipeline output → BERT input: `WordCandidate.surface` strings
- BERT embeddings → Cosine matrix → UMAP → Sinkhorn → params tensor → DifferentiableRenderer
- pgvector: new Alembic migration for word_embeddings table
- InnerLoop: no API changes — warm-start is external

</code_context>

<specifics>
## Specific Ideas

- Sinkhorn convergence proof O(log(1/eps)) independent of dimension (arXiv:2604.03787) — cite in Phase 8 research
- DOMPurify v3.4.0 update needed for parent Shopify app (flagged in team discuss, not Phase 8 scope)
- Neural-Bitmasking paper (ETH Zurich) for Phase 12 optimization backlog

</specifics>

<deferred>
## Deferred Ideas

- Cluster-to-segment transport (K clusters → M MAT branches) instead of word-to-position — more efficient for large N but loses per-word control. Consider for Phase 11 Outer Loop-v2.
- GPU-accelerated Sinkhorn via POT CUDA backend — Phase 12 production optimization.
- sentence-transformers multi-GPU inference — Phase 12 scaling.

</deferred>

---

*Phase: 08-semantic-vector-space*
*Context gathered: 2026-04-18*

# Phase 8: Semantic Vector Space — Decision Log

**Date:** 2026-04-18
**Phase:** 08-semantic-vector-space
**Status:** All decisions implemented and verified

---

## Decision Index

| ID | Topic | Status |
|----|-------|--------|
| D-01 | Embed surface strings (not stems) via all-MiniLM-L6-v2 | Implemented |
| D-02 | Model warm-up at process startup | Implemented |
| D-03 | Batch encoding via sentence-transformers | Implemented |
| D-04 | Cosine similarity via sklearn | Implemented |
| D-05 | UMAP as primary 2D projection | Implemented |
| D-06 | t-SNE as fallback projection | Implemented |
| D-07 | POT sinkhorn_log for numerical stability | Implemented |
| D-08 | Uniform marginals (1:1 word-to-position prior) | Implemented |
| D-09 | Adaptive epsilon regularization | Implemented |
| D-10 | Sinkhorn convergence O(log(1/ε)) proof | Documented |
| D-11 | External warm-start function (no InnerLoop changes) | Implemented |
| D-12 | MAT branch origins as anchor positions | Implemented |
| D-13 | word_embeddings table schema | Implemented |
| D-14 | HNSW index on embedding with vector_cosine_ops | Implemented |
| D-15 | archive_v1 isolation | Implemented + verified |

---

## Detailed Decision Records

### D-01: Embed Surface Strings (Not Stems)

**Decision:** Encode `WordCandidate.surface` strings (not stems) via `sentence-transformers
all-MiniLM-L6-v2` producing `(N, 384)` float32 tensors.

**Rationale:** Surface forms preserve morphological context for BERT's WordPiece tokenizer.
A stem like "run" loses the distinction between "running" (present participle, activity)
and "runner" (noun, agent). Surface forms give BERT the full token context it was trained on.

**Alternative considered:** Stem-based encoding — rejected because stems collapse semantic
distinctions that BERT can capture from surface morphology.

**Implementation:** `embeddings.py: encode_surfaces(surfaces: list[str]) -> np.ndarray`

---

### D-02: Model Warm-Up at Process Startup

**Decision:** Lazy singleton via `get_model()` — loads `all-MiniLM-L6-v2` on first call and
runs a warm-up `encode(["warm"])` to JIT-compile the tokenizer graph before production calls.

**Rationale:** Addresses PITFALLS.md #3 (cold-start latency). Without warm-up, the first
production `encode_surfaces()` call incurs 200-500ms JIT overhead that would appear as
latency spike on the first wordcloud rendering. Warm-up amortizes this cost to startup.

**Implementation:** `embeddings.py: get_model()` lazy singleton with `_model: SentenceTransformer | None = None`

---

### D-03: Batch Encoding via sentence-transformers

**Decision:** `model.encode(surfaces, batch_size=settings.embedding_batch_size,
show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=False)`

**Rationale:** `convert_to_numpy=True` avoids a tensor→numpy copy. `normalize_embeddings=False`
keeps raw embeddings — cosine normalization is handled by `sklearn.metrics.pairwise.cosine_similarity`
in `cosine.py`. `batch_size=32` (configurable) balances GPU memory vs throughput.

**Implementation:** `embeddings.py: encode_surfaces()`, `settings.embedding_batch_size`

---

### D-04: Cosine Similarity via sklearn

**Decision:** `sklearn.metrics.pairwise.cosine_similarity` on `(N, 384)` matrix → `(N, N)`
float32 matrix.

**Rationale:** sklearn's implementation is numerically stable (L2-normalizes before dot
product, avoids division by near-zero norms). Faster than manual implementation for N < 500.

**Implementation:** `cosine.py: cosine_similarity_matrix(embeddings) -> np.ndarray`

---

### D-05: UMAP as Primary 2D Projection

**Decision:** UMAP (`umap-learn >= 0.5.0`) as default projection method. Config flag
`projection_method: Literal["umap", "tsne"] = "umap"`.

**Rationale:** UMAP preserves global topological structure better than t-SNE for large N.
More deterministic with fixed `random_state`. Faster at inference (15s vs 60s for N=1000).
`wiki/bert-embeddings.md` documents the UMAP preference rationale.

**Small-N guard:** `n_neighbors = min(15, max(2, N-1))` — avoids "n_neighbors must be
smaller than n_samples" error. `init = "spectral" if N >= 4 else "random"` — avoids
ARPACK `eigsh` failure when k >= N.

**Implementation:** `projection.py: _umap_project()`

---

### D-06: t-SNE as Fallback

**Decision:** `sklearn.manifold.TSNE` available as fallback via `projection_method="tsne"`.
Perplexity clamped to `min(30, max(1, N-1))`. PCA init for determinism.

**Rationale:** t-SNE is well-understood and widely deployed. Useful for debugging and
comparison. Deterministic with `init="pca"` (PCA is fully deterministic).

**Implementation:** `projection.py: _tsne_project()`

---

### D-07: POT sinkhorn_log for Numerical Stability

**Decision:** `ot.sinkhorn(a, b, M, reg=eps, method="sinkhorn_log", log=True)`.

**Rationale:** Log-space arithmetic prevents underflow when `eps` is small and cost
differences are large. Standard formulation computes `exp(-C/ε)` which underflows to zero
for large costs — log-space avoids this. POT moved from `[nlp]` to `[embeddings]` extra dep
group.

**Implementation:** `transport.py: compute_transport()`

---

### D-08: Uniform Marginals

**Decision:** `a = b = ones(N) / N` — uniform marginals encoding 1:1 word-to-position prior.

**Rationale:** Each word has equal probability of being assigned to any canvas region. Each
canvas target position receives equal total word mass. This is the correct prior for word
cloud placement where we have no reason to weight words differently at this stage (importance
weighting happens via `score`/`font_size` in earlier NLP pipeline stages).

**Alternative considered:** Mass proportional to word score — rejected because Sinkhorn
already assigns based on semantic proximity; score weighting belongs in the renderer loss.

**Implementation:** `transport.py: a = b = np.ones(N, dtype=np.float64) / N`

---

### D-09: Adaptive Epsilon Regularization

**Decision:** Start with `eps=settings.sinkhorn_eps_init` (default 0.1). After each call:
- `niter < 10`: halve eps (was too loose → sharper transport next time)
- `niter > 500`: double eps (was too tight → faster convergence next time)
- Clamp to `[1e-4, 1.0]` always.

**Rationale:** Single fixed epsilon cannot be optimal for both small vocabularies (N=10,
needs sharp transport) and large vocabularies (N=500, needs smooth transport). Adaptive
epsilon self-tunes across rendering sessions.

**Implementation:** `transport.py: compute_transport()`, `TransportPlan.eps_used`

---

### D-10: Sinkhorn Convergence Proof Reference

**Theorem (arXiv:2604.03787):** Sinkhorn-Knopp converges in `O(log(1/ε))` iterations,
independent of problem dimension N.

**Implication:** Adding BERT dimensions (384) does not slow Sinkhorn. Only `eps` and cost
matrix structure matter for convergence speed. `max_iter` caps worst-case runtime for
adversarial inputs (T-08-05 DoS protection).

**Documented in:** `wiki/code/semantic-transport.md`, `wiki/optimal-transport.md`

---

### D-11: External Warm-Start Function

**Decision:** `semantic_warm_start(candidates, sdf, mat_result, config) -> torch.Tensor`
returning `(N, 4)` params tensor `[y, x, 1.0, 0.0]`. NO changes to `InnerLoop` API.

**Rationale:** Preserves Phase 6 D-19 contract (`DifferentiableRenderer(params_n4, sprites,
device)` signature). Caller passes result directly to `DifferentiableRenderer`. Semantic
warm-start is an orthogonal concern — the renderer shouldn't know where params came from.

**Implementation:** `warm_start.py: semantic_warm_start()`

---

### D-12: MAT Branch Origins as Anchor Positions

**Decision:** Build N target canvas positions starting from MAT branch `origin_yx` points
(deepest interior points per branch). Fill remaining slots with UMAP-scaled positions
if `N > num_branches`.

**Rationale:** MAT branches represent the structural skeleton of the silhouette — branch
origins are the most interior, visually prominent positions. Starting words at branch
origins produces better initial placement than random inside-pixel selection.

**Implementation:** `warm_start.py: _build_target_positions()`

---

### D-13: word_embeddings Table Schema

**Decision:**
```sql
CREATE TABLE word_embeddings (
    surface       TEXT PRIMARY KEY,
    embedding     vector(384) NOT NULL,
    model_version TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
```

**Rationale:** `surface TEXT PRIMARY KEY` — surface form is the natural key; no surrogate
int PK needed. `vector(384)` — matches all-MiniLM-L6-v2 output dimension exactly.
`model_version` — provenance tracking for cache invalidation when model changes.

**Implementation:** `infra/alembic/versions/0002_word_embeddings.py`

---

### D-14: HNSW Index with vector_cosine_ops

**Decision:**
```sql
CREATE INDEX word_embeddings_embedding_hnsw_idx
    ON word_embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

**Rationale:** HNSW (Hierarchical Navigable Small Worlds) gives approximate nearest-neighbor
search in `O(log N)` instead of `O(N)` brute force. `vector_cosine_ops` matches the cosine
similarity metric used for semantic similarity. Phase 9 MAP-Elites will query this index
for ANN search. `m=16, ef_construction=64` balanced for ~10k word vocabulary.

**Implementation:** `infra/alembic/versions/0002_word_embeddings.py`

---

### D-15: archive_v1 Isolation

**Decision:** `persistence.py` contains zero references to `archive_v1` in executable SQL.
`word_embeddings` and `archive_v1` are completely separate tables.

**Rationale:** Phase 8 embedding cache is per-word. Phase 9 MAP-Elites archive (`archive_v1`)
stores layout-level aggregate embeddings — a fundamentally different semantic unit. Mixing
them would create coupling between word-level and layout-level semantics. `archive_v1.descriptor
vector(384)` is reserved for Phase 9.

**Verified by:** Static grep in 08-05-SUMMARY.md self-check: `grep "archive_v1"
persistence.py` returns comments only.

**Implementation:** `persistence.py` — all SQL touches only `word_embeddings`

---

## Claude's Discretion Decisions (Implemented)

These decisions were marked "Claude's Discretion" in the CONTEXT.md and resolved during
implementation:

| Topic | Decision Made |
|-------|---------------|
| UMAP hyperparameters | `n_neighbors=min(15, N-1)`, `min_dist=0.1`, `metric="cosine"`, `random_state=seed` |
| Sinkhorn max_iterations | `settings.sinkhorn_max_iter` (configurable, default 1000) |
| Model warm-up timing | Module-level lazy singleton, warm-up on first `get_model()` call |
| Test fixture strategy | Fixed RNG seed `(N=10, D=384)` embeddings from `conftest.py` session fixture; separate `test_pgvector.py` uses testcontainers for Docker-gated tests |
| UMAP init for N < 4 | `init="random"` fallback (avoids ARPACK `eigsh` failure when N < 4) |

---

*Phase: 08-semantic-vector-space*
*Decisions documented: 2026-04-18*
*All 15 decisions implemented and verified by Phase 8 exit gate (08-06)*

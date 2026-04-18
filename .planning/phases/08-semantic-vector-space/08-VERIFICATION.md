---
phase: 08-semantic-vector-space
verified: 2026-04-16T12:00:00Z
status: human_needed
score: 14/16 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Run the full semantic test suite against a live BERT model"
    expected: "46 tests pass, 8 Docker-gated pgvector tests pass with Docker access"
    why_human: "Real model download required; pgvector integration tests need Docker socket access that the worktree environment lacks"
  - test: "Measure pgvector HNSW recall >= 98% on a representative query set"
    expected: "ANN search over word_embeddings table returns nearest neighbours with recall >= 98% vs exact cosine search"
    why_human: "No automated recall test exists. Requires a populated word_embeddings table, ANN queries via pgvector, and comparison against exact sklearn cosine_similarity results. SC4 of the roadmap is not covered by any test in the suite."
  - test: "Demonstrate Inner Loop convergence with Sinkhorn warm-start vs random init"
    expected: "InnerLoop.optimize() with DifferentiableRenderer initialised from semantic_warm_start() reaches convergence threshold faster (fewer epochs or lower final loss) than a randomly-initialised renderer"
    why_human: "SC5 of the roadmap ('Inner Loop with Sinkhorn warm-start converges faster than random init') is not tested anywhere. semantic_warm_start() produces the correct (N, 4) tensor interface but no test wires it into InnerLoop and measures convergence. Per D-11, the wiring is the caller's responsibility (Phase 9 Outer Loop), but the success criterion was written against Phase 8."
---

# Phase 8: Semantic Vector Space Verification Report

**Phase Goal:** BERT embeddings + Sinkhorn-Knopp Optimal Transport warm-start.
**Verified:** 2026-04-16T12:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

All must-haves are derived from plan frontmatter (6 plan files) merged with 5 ROADMAP success criteria.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | encode_surfaces(['hello', 'world']) returns (2, 384) float32 numpy array | VERIFIED | `def encode_surfaces` present in embeddings.py; returns `np.asarray(result, dtype=np.float32)`; 11 tests in test_embeddings.py including shape tests |
| 2 | get_model() returns cached SentenceTransformer singleton (same id on second call) | VERIFIED | Module-level `_model: SentenceTransformer \| None = None` with get/reset pattern confirmed in embeddings.py |
| 3 | Model warm-up runs a dummy encode on first call (SEM-02) | VERIFIED | `["warm"]` encode call present inside `get_model()` before return; documented as SEM-02 |
| 4 | EmbeddingResult Pydantic model validates (N, 384) shape | VERIFIED | `class EmbeddingResult` in models/semantic.py with model_post_init shape check |
| 5 | cosine_similarity_matrix on (N, 384) embeddings returns (N, N) float32 matrix | VERIFIED | `def cosine_similarity_matrix` in cosine.py; uses sklearn pairwise; 6 class-based tests in test_cosine.py |
| 6 | Diagonal of cosine similarity matrix is all 1.0 (self-similarity) | VERIFIED | test_cosine.py TestCosineProperties.test_diagonal_is_one confirmed; sklearn cosine_similarity returns 1.0 on diagonal |
| 7 | project_to_2d with method='umap' returns (N, 2) float32 array | VERIFIED | `def project_to_2d` in projection.py; UMAP branch confirmed with `reducer = umap.UMAP(...)` |
| 8 | project_to_2d with method='tsne' returns (N, 2) float32 array | VERIFIED | TSNE branch in projection.py; `elif effective_method == "tsne"` confirmed |
| 9 | Same seed produces identical 2D projections (determinism) | VERIFIED | test_projection.py TestProjectionDeterminism tests; UMAP random_state + seeded TSNE |
| 10 | compute_transport on (N, N) cost matrix returns doubly stochastic transport matrix via log-space Sinkhorn | VERIFIED | `def compute_transport` in transport.py; `method="sinkhorn_log"` confirmed; hypothesis property test for doubly stochastic invariant |
| 11 | Adaptive epsilon halves when < 10 iter, doubles when > 500 iter, clamped to [1e-4, 1.0] | VERIFIED | `_EPS_MIN=1e-4`, `eps / 2.0` (fast path), `eps * 2.0` (slow path), `np.clip(eps, 1e-4, 1.0)` all confirmed in transport.py |
| 12 | semantic_warm_start returns (N, 4) torch.Tensor [y, x, 1.0, 0.0] with requires_grad=False | VERIFIED | `def semantic_warm_start` in warm_start.py; `params[:, 2] = 1.0`, `torch.from_numpy(params)` (requires_grad=False by default); 10 integration + determinism tests |
| 13 | Alembic migration creates word_embeddings table with HNSW index (vector_cosine_ops) | VERIFIED | `0002_word_embeddings.py` exists; `CREATE TABLE word_embeddings` and `USING hnsw (embedding vector_cosine_ops)` confirmed via raw SQL op.execute() |
| 14 | store_embeddings upserts; load_cached_embeddings returns cached / empty on miss; no writes to archive_v1 (D-15) | VERIFIED | `ON CONFLICT (surface) DO UPDATE` in persistence.py; archive_v1 appears only in isolation comments, never in executable SQL |
| 15 | pgvector HNSW recall >= 98% on test query set (SC4) | UNCERTAIN | HNSW index is created and exists. No recall measurement test exists in the suite. Needs human verification with populated table. |
| 16 | Inner Loop with Sinkhorn warm-start converges faster than random init (SC5) | UNCERTAIN | `semantic_warm_start()` produces the correct (N, 4) interface. Per D-11, no InnerLoop API changes were made. No convergence comparison test exists. Wiring to InnerLoop is Phase 9's responsibility per plan design. |

**Score:** 14/16 truths verified (2 uncertain — require human testing)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `packages/engine/src/aerocloud/semantic/__init__.py` | Public exports for semantic package | VERIFIED | Exports: encode_surfaces, get_model, reset_model, cosine_similarity_matrix, project_to_2d, compute_transport, semantic_warm_start, store_embeddings, load_cached_embeddings, error classes |
| `packages/engine/src/aerocloud/semantic/embeddings.py` | BERT embedding encode + model singleton | VERIFIED | encode_surfaces, get_model, reset_model, SentenceTransformer singleton, DoS guards |
| `packages/engine/src/aerocloud/semantic/errors.py` | SemanticError hierarchy | VERIFIED | SemanticError, EmbeddingError, SinkhornNonConvergenceError, ProjectionError |
| `packages/engine/src/aerocloud/models/semantic.py` | EmbeddingResult and TransportPlan Pydantic models | VERIFIED | Both classes present with model_post_init shape validation |
| `packages/engine/tests/semantic/conftest.py` | Shared fixtures (stub embeddings, mock model) | VERIFIED | stub_embeddings_5x384, stub_embeddings_10x384, stub_embeddings_3x384, sample_surfaces |
| `packages/engine/src/aerocloud/semantic/cosine.py` | Cosine similarity matrix computation | VERIFIED | cosine_similarity_matrix using sklearn pairwise |
| `packages/engine/src/aerocloud/semantic/projection.py` | UMAP and t-SNE 2D projection | VERIFIED | project_to_2d with UMAP (primary, D-05) and t-SNE (fallback, D-06) |
| `packages/engine/src/aerocloud/semantic/transport.py` | Sinkhorn-Knopp with adaptive epsilon | VERIFIED | compute_transport, sinkhorn_log, adaptive eps, TransportPlan return |
| `packages/engine/tests/semantic/property/test_transport_hypothesis.py` | Property-based test: T is always doubly stochastic | VERIFIED | hypothesis @given with N in [2,20], 50 examples |
| `packages/engine/src/aerocloud/semantic/warm_start.py` | semantic_warm_start glue function | VERIFIED | Full pipeline: encode -> cosine -> project -> transport -> (N,4) tensor |
| `packages/engine/tests/semantic/integration/test_warm_start_pipeline.py` | Integration test: NLP candidates to valid params tensor | VERIFIED | 7 integration tests including SDF bounds, dtype, requires_grad |
| `packages/engine/tests/semantic/determinism/test_seed_stability.py` | Determinism test: same seed -> identical output | VERIFIED | 3 determinism tests using torch.equal |
| `infra/alembic/versions/0002_word_embeddings.py` | Alembic migration for word_embeddings table | VERIFIED | word_embeddings table + HNSW index via raw SQL op.execute() |
| `packages/engine/src/aerocloud/semantic/persistence.py` | pgvector store/load functions | VERIFIED | async store_embeddings + load_cached_embeddings with parameterised queries |
| `wiki/code/semantic-embeddings.md` | Documentation of embeddings module | VERIFIED | Contains encode_surfaces documentation |
| `wiki/code/semantic-transport.md` | Documentation of transport module | VERIFIED | Contains compute_transport documentation |
| `wiki/decisions/2026-04-18-phase-08-semantic-decisions.md` | Decision log for Phase 8 | VERIFIED | All D-01..D-15 with rationale and implementation status |
| `.planning/phases/08-semantic-vector-space/08-3ki-review/consensus.md` | 3-KI review consensus | VERIFIED | 8 APPROVED mentions across Claude/Codex-role/Gemini-role reviewers |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| embeddings.py | aerocloud.config.settings | settings.model_cache_dir | WIRED | `cache_dir=settings.model_cache_dir, cache_folder=settings.model_cache_dir` |
| embeddings.py | sentence_transformers.SentenceTransformer | import + singleton | WIRED | `from sentence_transformers import SentenceTransformer` confirmed |
| cosine.py | sklearn.metrics.pairwise.cosine_similarity | import | WIRED | `from sklearn.metrics.pairwise import cosine_similarity` + call confirmed |
| projection.py | umap.UMAP | import (lazy) | WIRED | `reducer = umap.UMAP(...)` inside `_umap_project` helper |
| transport.py | ot.sinkhorn | import ot | WIRED | `transport_mat, log_dict = ot.sinkhorn(..., method="sinkhorn_log")` confirmed |
| transport.py | aerocloud.models.semantic.TransportPlan | return TransportPlan | WIRED | `return TransportPlan(transport_matrix=..., eps_used=..., iterations=...)` |
| warm_start.py | aerocloud.semantic.embeddings.encode_surfaces | import | WIRED | `from aerocloud.semantic.embeddings import encode_surfaces` + call confirmed |
| warm_start.py | aerocloud.semantic.transport.compute_transport | import | WIRED | `from aerocloud.semantic.transport import compute_transport` + call confirmed |
| warm_start.py | aerocloud.geometry.mat.MATResult | import | WIRED | `from aerocloud.geometry.mat import MATResult` confirmed |
| persistence.py | settings.database_url | asyncpg.connect | WIRED | `asyncpg.connect(settings.database_url)` confirmed |
| wiki/code/semantic-warm-start.md | warm_start.py | documentation | WIRED | `semantic_warm_start` appears in wiki doc |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| embeddings.py | result (ndarray) | SentenceTransformer.encode() on real BERT model | Yes — real model inference | FLOWING |
| cosine.py | sim (ndarray) | sklearn cosine_similarity on input embeddings | Yes — computed pairwise | FLOWING |
| projection.py | coords (ndarray) | umap.UMAP.fit_transform or TSNE.fit_transform | Yes — computed projections | FLOWING |
| transport.py | transport_mat | ot.sinkhorn log-space computation | Yes — real OT solve | FLOWING |
| warm_start.py | params (ndarray -> tensor) | Full pipeline: encode -> cosine -> project -> transport -> MAT anchors | Yes — all real computations | FLOWING |
| persistence.py | result (dict) | asyncpg fetch from word_embeddings table | Yes — real DB query; skipped in CI without Docker | FLOWING (conditional) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| encode_surfaces exports exist | `grep "encode_surfaces" packages/engine/src/aerocloud/semantic/__init__.py` | MATCHED | PASS |
| cosine_similarity_matrix exports exist | `grep "cosine_similarity_matrix" packages/engine/src/aerocloud/semantic/__init__.py` | MATCHED | PASS |
| Sinkhorn adaptive eps clamped | `grep "_EPS_MIN\|1e-4" packages/engine/src/aerocloud/semantic/transport.py` | MATCHED | PASS |
| Migration HNSW index | `grep "vector_cosine_ops" infra/alembic/versions/0002_word_embeddings.py` | MATCHED (2 lines) | PASS |
| All 10 Phase 8 commits valid | `git cat-file -t {hash}` x10 | All return "commit" | PASS |
| Full test suite (live model) | `uv run pytest packages/engine/tests/semantic/` | NOT RUN (requires model download + Docker) | SKIP |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SEM-01 | 08-01 | BERT inference via sentence-transformers all-MiniLM-L6-v2 | SATISFIED | `SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")` in embeddings.py |
| SEM-02 | 08-01 | Model warm-up at process startup | SATISFIED | `["warm"]` encode in get_model() singleton |
| SEM-03 | 08-02 | Cosine similarity matrix for word pairs | SATISFIED | cosine_similarity_matrix() via sklearn pairwise |
| SEM-04 | 08-02 | t-SNE or UMAP projection to 2D for warm-start initialization | SATISFIED | project_to_2d() supports both UMAP (primary) and t-SNE (fallback) |
| SEM-05 | 08-03 | Sinkhorn-Knopp OT via POT 0.9.x, computed in log-space | SATISFIED | `ot.sinkhorn(..., method="sinkhorn_log")` in transport.py |
| SEM-06 | 08-03 | Adaptive epsilon regularization | SATISFIED | halve < 10 iter / double > 500 iter / clamp [1e-4, 1.0] all verified |
| SEM-07 | 08-05 | BERT embeddings persisted in pgvector with HNSW index | SATISFIED | Migration 0002 + persistence.py; HNSW index with vector_cosine_ops confirmed |
| SEM-08 | 08-04 | Sinkhorn output replaces Force-Directed initialization in the Inner Loop | PARTIAL | semantic_warm_start() exists, produces correct (N, 4) interface per D-11. No InnerLoop is currently wired to call it (per D-11 design decision: "Caller passes result to DifferentiableRenderer. NO changes to InnerLoop API"). Full wiring is Phase 9's job. The function is the public API ready for Phase 9 to consume. |

**SEM-08 note:** The REQUIREMENTS.md says "Sinkhorn output replaces Force-Directed initialization in the Inner Loop." The Phase 8 design decision D-11 explicitly chose NOT to change the InnerLoop API, instead providing `semantic_warm_start()` as an external function for Phase 9 (Outer Loop) and production callers to pass as params to DifferentiableRenderer. The 3-KI review accepted this interpretation as satisfying SEM-08. The requirement is met at the interface level; end-to-end wiring will be demonstrated in Phase 9.

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| warm_start.py | cosine_similarity_matrix() called but result discarded (shape validation only — known) | Info | Noted in 3-KI review FINDING-C01; accepted: shape validation is the intent before UMAP call |
| persistence.py (integration tests) | 8 tests skip when Docker unavailable | Info | By design — testcontainers pattern; tests are structurally complete for CI environments with Docker |

No blocker anti-patterns found. No TODO/FIXME/placeholder comments in any semantic source file. All implementations are substantive.

### Human Verification Required

#### 1. Full Semantic Test Suite with Live Model

**Test:** Run `uv run pytest packages/engine/tests/semantic/ -q --tb=short` with full BERT model access and Docker available for pgvector tests.
**Expected:** 46 tests pass (as reported by 08-06 exit gate), 8 Docker-gated tests pass.
**Why human:** The BERT model (all-MiniLM-L6-v2) requires download and inference. The pgvector integration tests require Docker socket access. Neither is available in this worktree environment.

#### 2. pgvector HNSW Recall Measurement (SC4)

**Test:** Populate word_embeddings with a representative vocabulary (~1000 words). Run ANN queries via `SELECT embedding <=> $1 FROM word_embeddings ORDER BY embedding <=> $1 LIMIT 10`. Compare top-10 ANN results against exact top-10 from `cosine_similarity_matrix`. Compute recall at K=10.
**Expected:** Recall >= 98% (ROADMAP success criterion 4).
**Why human:** No automated recall test exists in the test suite. The HNSW index is created with m=16, ef_construction=64, but recall has never been measured. This is a gap in test coverage against the roadmap success criterion.

#### 3. Sinkhorn Warm-Start Convergence Comparison (SC5)

**Test:** Run InnerLoop.optimize() twice on the same input — once with DifferentiableRenderer initialized from `semantic_warm_start(candidates, sdf, mat_result)`, once with a randomly initialized (N, 4) params tensor. Compare epoch count to convergence threshold and final L_total.
**Expected:** Semantic warm-start reaches convergence threshold in fewer epochs or lower final loss (ROADMAP success criterion 5).
**Why human:** No automated convergence comparison test exists. Per D-11, Phase 8 does not wire semantic_warm_start into InnerLoop — that is Phase 9's responsibility. The success criterion in the roadmap was written optimistically; the Phase 8 contract (as agreed in 3-KI review) is to provide the correct interface, not to demonstrate runtime convergence improvement.

### Gaps Summary

No hard blocking gaps were found. All 8 requirements (SEM-01 to SEM-08) have implementation evidence. Two roadmap success criteria (SC4: HNSW recall, SC5: convergence comparison) are not covered by automated tests and require human verification before Phase 8 can be considered fully gate-closed against the roadmap contract.

The SEM-08 partial status reflects that the public API is complete and correct, but end-to-end demonstration (wiring into InnerLoop + convergence benchmark) is a Phase 9 deliverable by design decision D-11.

---

_Verified: 2026-04-16T12:00:00Z_
_Verifier: Claude (gsd-verifier)_

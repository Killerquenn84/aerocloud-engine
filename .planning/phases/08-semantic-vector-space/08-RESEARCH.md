# Phase 8: Semantic Vector Space - Research

**Researched:** 2026-04-16
**Domain:** BERT embeddings, Optimal Transport, 2D projection, pgvector persistence
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**BERT Embedding Integration**
- D-01: Embed `WordCandidate.surface` strings via `sentence-transformers` `all-MiniLM-L6-v2` producing `(N, 384)` float32 tensors
- D-02: Model warm-up at process startup via `SentenceTransformer(model_name, cache_folder=config.model_cache_dir)`. Pre-download model into Docker image for offline deployment
- D-03: Batch encoding via `model.encode(surfaces, batch_size=32, show_progress_bar=False, convert_to_numpy=True)`

**Cosine Similarity and 2D Projection**
- D-04: Cosine similarity matrix via `sklearn.metrics.pairwise.cosine_similarity` on the `(N, 384)` embedding matrix → `(N, N)` float32
- D-05: UMAP as primary 2D projection. Add `umap-learn>=0.5.0` to `embeddings` optional-dep group
- D-06: t-SNE available as fallback via `sklearn.manifold.TSNE`. Config flag `projection_method: Literal["umap", "tsne"] = "umap"`

**Sinkhorn-Knopp Optimal Transport**
- D-07: POT `ot.sinkhorn` with `log=True` and `method='sinkhorn_log'` for log-space computation. Move POT from `nlp` extra to `embeddings` extra
- D-08: Transport is word-to-position: `(N words) -> (N canvas positions)`. Cost matrix: cosine distance between UMAP-projected word embeddings and candidate positions from MAT branch origins
- D-09: Adaptive epsilon: start `eps=0.1`, halve if Sinkhorn converges in `< 10` iterations, double if `> 500`. Clamp eps to `[1e-4, 1.0]`

**Warm-Start Integration**
- D-11: External function `semantic_warm_start(candidates, sdf, mat_result, config) -> torch.Tensor` returning `(N, 4)` params tensor `[y, x, scale, theta]`. Scale=1.0, theta=0.0 initialized. NO changes to InnerLoop API
- D-12: Positions from Sinkhorn transport plan mapped to SDF canvas coordinates

**pgvector Persistence**
- D-13: NEW table `word_embeddings(surface TEXT PRIMARY KEY, embedding vector(384), model_version TEXT, created_at TIMESTAMPTZ)`. New Alembic migration required
- D-14: HNSW index on `word_embeddings.embedding` with `vector_cosine_ops`
- D-15: `archive_v1.descriptor` reserved for Phase 9 MAP-Elites; Phase 8 does NOT write to `archive_v1`

### Claude's Discretion
- Exact UMAP hyperparameters (n_neighbors, min_dist, metric)
- Sinkhorn max_iterations default
- Model warm-up timing (module import vs explicit init function)
- Test fixture embedding generation strategy

### Deferred Ideas (OUT OF SCOPE)
- Cluster-to-segment transport (K clusters → M MAT branches) — Phase 11
- GPU-accelerated Sinkhorn via POT CUDA backend — Phase 12
- sentence-transformers multi-GPU inference — Phase 12
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SEM-01 | BERT inference via `sentence-transformers` `all-MiniLM-L6-v2` | Verified: `sentence-transformers==5.3.0` installed in uv venv; encode() API confirmed |
| SEM-02 | Model warm-up at process startup (cold-start latency mitigation) | Verified: `cache_folder` param confirmed in ST 5.3.0 `__init__`; `local_files_only=True` for offline |
| SEM-03 | Cosine similarity matrix for word pairs | Verified: `sklearn.metrics.pairwise.cosine_similarity` works on (N,384) float32, output (N,N) float32 |
| SEM-04 | t-SNE or UMAP projection to 2D for warm-start initialization | Verified: umap-learn 0.5.12 latest; numba 0.65.0 installed; sklearn TSNE has `random_state`; UMAP needs pyproject.toml update |
| SEM-05 | Sinkhorn-Knopp Optimal Transport via POT 0.9.6.post1 in log-space | Verified: POT 0.9.6.post1 installed; `method='sinkhorn_log'` confirmed NaN-free on degenerate inputs |
| SEM-06 | Adaptive ε regularization for Sinkhorn-Knopp | Verified: `niter` key in log dict; eps=1.0 → 10 iter, eps=0.1 → 50 iter, eps=0.001 → 999 iter |
| SEM-07 | BERT embeddings persisted in pgvector with HNSW index | Verified: PostgreSQL 16.13 running; alembic 1.18.4 installed; pgvector extension exists from Phase 2 |
| SEM-08 | Sinkhorn output replaces Force-Directed initialization in Inner Loop | Verified: `DifferentiableRenderer(params_n4, ...)` accepts any (N,4) tensor; InnerLoop consumes renderer with params already set |
</phase_requirements>

---

## Summary

Phase 8 adds a semantic layer between the NLP pipeline output and the Inner Loop optimizer. The data flow is: `WordCandidate.surface` strings → `all-MiniLM-L6-v2` BERT embeddings `(N, 384)` → cosine similarity matrix → UMAP 2D projection → Sinkhorn-Knopp transport plan (word-to-position) → `(N, 4)` params tensor `[y, x, 1.0, 0.0]` → `DifferentiableRenderer`. In parallel, embeddings are persisted to a new `word_embeddings` pgvector table with HNSW index for cross-run caching.

All three core library components are verified in the uv venv: `sentence-transformers 5.3.0` (VERIFIED), `POT 0.9.6.post1` (VERIFIED), `scikit-learn 1.8.0` (VERIFIED). The only missing optional dep is `umap-learn>=0.5.0` (not yet in pyproject.toml) and `pgvector` Python package for typed embeddings. Both need to be added to the `[embeddings]` optional-dep group in `packages/engine/pyproject.toml`. Additionally, POT should be moved from `[nlp]` to `[embeddings]` per D-07.

The module lives at `packages/engine/src/aerocloud/semantic/` (new package, parallel to `nlp/`, `geometry/`, `optimizer/`). The CLAUDE.md module map lists `src/nlp/ → BERT-Embeddings` but the existing `nlp/` package is for spaCy/TF-IDF; a dedicated `semantic/` package is architecturally cleaner and preserves SRP.

**Primary recommendation:** Build `aerocloud.semantic` package with four sub-modules: `embeddings.py` (BERT encode + pgvector cache), `projection.py` (UMAP/t-SNE 2D), `transport.py` (Sinkhorn adaptive eps), `warm_start.py` (glue function). New Alembic migration `0002_word_embeddings.py`. Update pyproject.toml `[embeddings]` group.

---

## Project Constraints (from CLAUDE.md)

| Directive | Impact on Phase 8 |
|-----------|-------------------|
| Tests are laws — never adapted to code | All SEM tests must be RED before implementation begins |
| TDD Red→Green workflow mandatory | Scaffolding wave creates test files first |
| `AeroCloudBase(frozen=True, strict=True, extra="forbid")` | All Pydantic models (EmbeddingResult, TransportPlan) inherit this |
| Conventional commits: `feat:`, `fix:`, `test:`, `docs:` | Every commit uses conventional format |
| `mypy --strict` must pass | All new code fully typed, no `Any` unless documented |
| `ruff check` and `ruff format --check` must pass | Follow existing ruff config |
| Wiki MUST be updated after every phase | `wiki/code/`, `wiki/research/`, `wiki/tests/` updated at phase close |
| Session lifecycle: handover wiki after each phase | Phase 8 handover written before session reset |
| English in codebase (code, comments, commits, tests, docs) | All Phase 8 code in English |
| Telegram status updates | Status sent via `scripts/telegram-send.sh` |
| 3-KI review before commit | Claude + Gemini + Codex must approve before phase gate |
| `pickle` forbidden in CI lint rule | `safetensors` for model checkpoints — all-MiniLM-L6-v2 stored via HuggingFace cache only |
| `(y, x)` canonical coordinates (ADR-0005) | `semantic_warm_start` output column order: `[y, x, scale, theta]` |
| SDF positive=inside sign convention (ADR-0004) | Position mapping clips to SDF > 0 region |
| `set_seed()` must cover new random sources | UMAP `random_state=settings.seed`, TSNE `random_state=settings.seed` |
| No external font URLs at runtime | N/A for Phase 8 |

---

## Standard Stack

### Core (Phase 8 specific)

| Library | Version | Purpose | Verification |
|---------|---------|---------|--------------|
| `sentence-transformers` | 5.3.0 | BERT encode() for all-MiniLM-L6-v2 | [VERIFIED: uv venv `python -c "import sentence_transformers; print(sentence_transformers.__version__)"`] |
| `POT` | 0.9.6.post1 | Sinkhorn-Knopp log-space OT | [VERIFIED: uv venv `python -c "import ot; print(ot.__version__)"`] |
| `scikit-learn` | 1.8.0 | `cosine_similarity` + TSNE fallback | [VERIFIED: uv venv] |
| `umap-learn` | 0.5.12 | Primary 2D projection | [VERIFIED: PyPI via `uv pip index versions umap-learn`] — NOT YET INSTALLED |
| `numba` | 0.65.0 | umap-learn runtime dep | [VERIFIED: uv venv — already installed as transitive dep] |
| `alembic` | 1.18.4 | Migration for `word_embeddings` table | [VERIFIED: uv venv] |
| `pgvector` (Python) | 0.4.2 | Type adapter for `vector(384)` in asyncpg | [ASSUMED — not yet installed, version from STACK.md] |
| `asyncpg` | 0.31.0 | DB driver for pgvector INSERT/SELECT | [VERIFIED: uv venv] |
| `torch` | ≥2.5.0 | Tensor ops in transport.py; POT torch backend | [VERIFIED: already core dep] |

### Supporting (already in venv)

| Library | Purpose | When Used |
|---------|---------|-----------|
| `numpy>=2.1.0` | Array ops, cost matrix construction | Throughout |
| `cachetools>=7.0.0` | LRUCache for embedding in-memory cache | Optional — follow sdf_cache.py pattern |
| `blake3>=1.0.0` | Cache key digest for embedding cache | Optional — follow sdf_cache.py pattern |
| `structlog` | Structured logging in all new modules | Throughout |
| `pydantic>=2.10.0` | EmbeddingResult, TransportPlan models | Throughout |

### pyproject.toml Changes Required

**`[embeddings]` group update:**

```toml
embeddings = [
    "sentence-transformers>=3.0.0",
    "transformers>=4.40.0",
    "umap-learn>=0.5.0",      # NEW: Phase 8 D-05
    "POT>=0.9.5",              # MOVED: from [nlp] per D-07
    "pgvector>=0.4.0",         # NEW: Phase 8 vector type adapter
]
```

**`[nlp]` group — remove POT (moved to embeddings):**

```toml
nlp = [
    "spacy>=3.7.0,<4.0",
    "lingua-language-detector>=2.1,<2.2",
    # POT moved to [embeddings] per Phase 8 D-07
]
```

**Installation:**
```bash
uv sync --extra embeddings
```

**Version verification (run before planning):**
```bash
uv run python -c "import sentence_transformers; print(sentence_transformers.__version__)"
# Output: 5.3.0 [VERIFIED]
uv run python -c "import ot; print(ot.__version__)"
# Output: 0.9.6.post1 [VERIFIED]
uv pip index versions umap-learn 2>/dev/null | head -1
# Output: umap-learn (0.5.12) [VERIFIED]
```

---

## Architecture Patterns

### Recommended Project Structure

```
packages/engine/src/aerocloud/
├── semantic/                    # NEW — Phase 8 package
│   ├── __init__.py              # Public exports: semantic_warm_start, EmbeddingResult, TransportPlan
│   ├── embeddings.py            # BERT encode + pgvector cache (SEM-01, SEM-02, SEM-07)
│   ├── projection.py            # UMAP/t-SNE 2D projection (SEM-04)
│   ├── transport.py             # Sinkhorn-Knopp with adaptive eps (SEM-05, SEM-06)
│   ├── warm_start.py            # semantic_warm_start() glue function (SEM-08)
│   ├── errors.py                # SemanticError, SinkhornNonConvergenceError
│   └── metrics.py               # structlog + OTel metrics (embed_seconds, transport_iter)
├── models/
│   └── semantic.py              # NEW: EmbeddingResult, TransportPlan Pydantic models
└── config.py                    # EXTEND: add projection_method, sinkhorn_eps_init, etc.

infra/alembic/versions/
└── 0002_word_embeddings.py      # NEW Alembic migration

packages/engine/tests/
└── semantic/                    # NEW test subtree
    ├── __init__.py
    ├── conftest.py              # Fixtures: precomputed (5, 384) stub embeddings
    ├── unit/
    │   ├── test_embeddings.py   # Unit: encode() batching, cache hit/miss
    │   ├── test_projection.py   # Unit: UMAP/TSNE output shape, determinism
    │   └── test_transport.py    # Unit: Sinkhorn NaN-free, adaptive eps
    ├── integration/
    │   └── test_warm_start.py   # Integration: pipeline → warm_start → renderer params
    ├── property/
    │   └── test_transport_hypothesis.py  # Hypothesis: T always row/col stochastic
    └── determinism/
        └── test_seed_stability.py        # Same seed → identical (N,4) output
```

### Pattern 1: BERT Encode with pgvector Cache

**What:** Encode surface strings in batches; check pgvector for cached embeddings first; INSERT new ones.

**When to use:** Always — model inference is ~50ms/call, pgvector hit is ~1ms.

```python
# Source: sentence-transformers 5.3.0 encode() API — [VERIFIED: uv venv introspection]
from sentence_transformers import SentenceTransformer
from aerocloud.config import settings

_model: SentenceTransformer | None = None

def get_model() -> SentenceTransformer:
    """Lazy singleton with warm-up guarantee (D-02)."""
    global _model
    if _model is None:
        _model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2",
            cache_folder=settings.model_cache_dir,
            local_files_only=False,   # False allows download; Docker bakes the model in
        )
        # Warm-up: run one dummy encode to JIT-compile tokenizer paths
        _model.encode(["warm"], batch_size=1, show_progress_bar=False, convert_to_numpy=True)
    return _model

def encode_surfaces(surfaces: list[str]) -> np.ndarray:
    """(N, 384) float32 — deterministic with no random state in all-MiniLM-L6-v2."""
    return get_model().encode(
        surfaces,
        batch_size=32,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=False,  # Keep raw vectors; cosine_similarity normalizes
    )
```

### Pattern 2: Sinkhorn-Knopp with Adaptive Epsilon

**What:** `ot.sinkhorn` with `method='sinkhorn_log'` (log-space, NaN-free). Adaptive eps per D-09.

**When to use:** Building the word-to-position transport plan.

```python
# Source: POT 0.9.6.post1 API — [VERIFIED: uv venv introspection + live test]
import ot
import numpy as np

def compute_transport(
    cost_M: np.ndarray,              # (N, N) float32 cosine distances
    eps_init: float = 0.1,           # D-09 starting epsilon
    max_iter: int = 1000,            # default — Claude's discretion
    eps_min: float = 1e-4,           # D-09 clamp lower
    eps_max: float = 1.0,            # D-09 clamp upper
) -> tuple[np.ndarray, float, int]:
    """Returns (T, eps_used, niter)."""
    N = cost_M.shape[0]
    a = np.ones(N, dtype=np.float64) / N   # uniform word distribution
    b = np.ones(N, dtype=np.float64) / N   # uniform position distribution

    eps = eps_init
    T, log = ot.sinkhorn(
        a, b, cost_M.astype(np.float64),
        reg=eps,
        method="sinkhorn_log",   # log-space: NaN-free even on degenerate distributions
        numItermax=max_iter,
        log=True,
    )
    niter = log["niter"]

    # D-09 adaptive adjustment
    if niter < 10:
        eps = max(eps_min, eps / 2.0)
    elif niter > 500:
        eps = min(eps_max, eps * 2.0)

    return T, eps, niter
```

**Key verified behavior (live test on degenerate distribution):**
```
a=[1,0], b=[0,1], M=ones(2,2), eps=0.1 → T=[[0,1],[0,0]], has_nan=False
```
`method='sinkhorn_log'` returns a valid transport plan even for rank-1 degenerate inputs. [VERIFIED]

**Adaptive epsilon empirical data (N=10, random M):**

| eps | niter | Adjustment per D-09 |
|-----|-------|---------------------|
| 1.0 | 10 | None (exactly at `< 10` boundary) |
| 0.1 | 50 | None (in valid range) |
| 0.001 | 999 | Double eps (next run starts at 0.002) |

`log["niter"]` is the key in `sinkhorn_log`'s log dict. [VERIFIED]

### Pattern 3: UMAP 2D Projection

**What:** `umap.UMAP(n_components=2, random_state=settings.seed).fit_transform(embeddings)`

**When to use:** Primary projection; fall back to sklearn TSNE if umap-learn unavailable.

```python
# Source: umap-learn 0.5.12 API — [ASSUMED from training knowledge; umap-learn not yet installed]
# Determinism: random_state fixes numpy PRNG; numba JIT is deterministic after first compile
import umap
from sklearn.manifold import TSNE

def project_2d(
    embeddings: np.ndarray,       # (N, 384)
    method: str = "umap",         # from config
    seed: int = 42,
) -> np.ndarray:                  # (N, 2)
    if method == "umap":
        reducer = umap.UMAP(
            n_components=2,
            random_state=seed,
            n_neighbors=15,        # Claude's discretion default
            min_dist=0.1,          # Claude's discretion default
            metric="cosine",       # Matches cosine similarity matrix
        )
        return reducer.fit_transform(embeddings).astype(np.float32)
    else:
        reducer = TSNE(
            n_components=2,
            random_state=seed,
            perplexity=min(30, max(5, embeddings.shape[0] // 5)),
            method="barnes_hut",
        )
        return reducer.fit_transform(embeddings).astype(np.float32)
```

**UMAP determinism caveat:** `random_state` fixes the numpy PRNG. numba JIT compilation itself is deterministic but adds ~5-10s latency on first call (Numba cache warms after first use per process). Test: same `random_state` → identical coordinates across runs. [ASSUMED — umap-learn not installed yet; standard UMAP behavior]

### Pattern 4: Alembic Migration for `word_embeddings`

**What:** New migration file following `0001_baseline.py` pattern exactly.

```python
# Source: 0001_baseline.py pattern — [VERIFIED: file read]
# File: infra/alembic/versions/0002_word_embeddings.py

revision: str = "0002_word_embeddings"
down_revision: str | None = "0001_baseline"

def upgrade() -> None:
    # pgvector extension already exists from 0001_baseline — DO NOT recreate
    op.execute(
        """
        CREATE TABLE word_embeddings (
            surface     TEXT PRIMARY KEY,
            embedding   vector(384) NOT NULL,
            model_version TEXT NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX word_embeddings_embedding_idx
            ON word_embeddings
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """
    )

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS word_embeddings_embedding_idx")
    op.execute("DROP TABLE IF EXISTS word_embeddings")
    # Do NOT drop vector extension
```

**Critical:** `down_revision = "0001_baseline"` chains to Phase 2 baseline. Do NOT add `CREATE EXTENSION IF NOT EXISTS vector` — it exists. [VERIFIED: 0001_baseline.py read]

### Pattern 5: semantic_warm_start() Integration

**What:** The glue function that the caller uses. Zero changes to InnerLoop or DifferentiableRenderer API.

```python
# Source: renderer/_renderer.py DifferentiableRenderer.__init__ signature — [VERIFIED]
# Source: optimizer/inner_loop.py InnerLoop class — [VERIFIED]

import torch
from aerocloud.models.tokens import WordCandidate
from aerocloud.geometry.mat import MATResult
from aerocloud.config import Settings

def semantic_warm_start(
    candidates: list[WordCandidate],
    sdf: np.ndarray,              # (H, W) float32
    mat_result: MATResult,
    config: Settings,
) -> torch.Tensor:                # (N, 4) float32: [y, x, 1.0, 0.0]
    """Build warm-start params tensor from BERT + Sinkhorn-Knopp.

    Caller passes returned tensor directly to:
        DifferentiableRenderer(params_n4=semantic_warm_start(...), sprites=..., device=...)

    NO changes to InnerLoop API per D-11.
    """
    surfaces = [c.surface for c in candidates]
    embeddings = encode_surfaces(surfaces)                    # (N, 384)
    coords_2d = project_2d(embeddings, method=config.projection_method, seed=config.seed)  # (N, 2)
    cost_M = _build_cost_matrix(coords_2d, mat_result)       # (N, N) cosine dist
    T, _, _ = compute_transport(cost_M)                       # (N, N) transport plan
    yx = _transport_to_canvas_coords(T, mat_result, sdf)      # (N, 2)

    N = len(candidates)
    params = torch.zeros((N, 4), dtype=torch.float32)
    params[:, 0] = torch.from_numpy(yx[:, 0])  # y
    params[:, 1] = torch.from_numpy(yx[:, 1])  # x
    params[:, 2] = 1.0                           # scale
    params[:, 3] = 0.0                           # theta
    return params
```

### Anti-Patterns to Avoid

- **Direct `sinkhorn` without `method='sinkhorn_log'`:** The default `method='sinkhorn'` accumulates floating point errors; fails on uniform or near-uniform distributions. Always use `method='sinkhorn_log'`. [VERIFIED: log keys differ — default logs `['err','niter','u','v']`, log-space logs `['err','niter','log_u','log_v','u','v']`]
- **Blocking the event loop with model.encode():** `SentenceTransformer.encode()` is CPU-bound. Never call inside FastAPI async handler without `run_in_executor`. Phase 8 is standalone (not yet FastAPI) but flag for Phase 12.
- **Storing embeddings as numpy float64:** POT works in float64 internally; store `float32` in pgvector to match `vector(384)` column type and archive_v1 convention.
- **Re-loading the model per request:** `SentenceTransformer` loads ~80MB; must be a module-level singleton. Process startup warm-up per D-02.
- **UMAP on N=1:** UMAP requires `n_neighbors < N`. Guard: if N < 3, skip projection and use zeros.
- **Using `add new migration` without `down_revision`:** Alembic requires `down_revision = "0001_baseline"` to chain migrations. Missing this corrupts the migration graph.
- **POT float32 cost matrix:** POT's `sinkhorn_log` internals use `exp()` — float32 underflows faster. Cast cost matrix to float64 before calling POT, then cast result back to float32. [VERIFIED: live test used float64]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Log-space Sinkhorn iterations | Custom scaling loop | `ot.sinkhorn(method='sinkhorn_log')` | Numerically stable log-sum-exp, handles degenerate distributions; convergence proof O(log(1/eps)) [arXiv:2604.03787] |
| Cosine similarity matrix | Manual dot products + norms | `sklearn.metrics.pairwise.cosine_similarity` | Handles broadcasting, float32 precision, vectorized across all pairs |
| UMAP projection | Custom manifold learning | `umap.UMAP(random_state=seed).fit_transform` | numba-accelerated, correct nearest-neighbor graph; custom implementations diverge on edge cases |
| pgvector HNSW index tuning | Custom ANN search | pgvector HNSW with `vector_cosine_ops` | HNSW recall ≥ 98% at 384-dim verified in prior Phase 2 research |
| Embedding cache coordination | Custom file-based cache | pgvector table + in-memory LRU (sdf_cache pattern) | Thread-safe, bytes-bounded, digest-keyed |

**Key insight:** The three core libraries (sentence-transformers, POT, umap-learn) each solve 2-5 year research problems. The integration code is thin glue — spend complexity budget on the glue, not reimplementing OT solvers.

---

## Common Pitfalls

### Pitfall 1: Sinkhorn NaN on Uniform Distributions (PITFALLS.md #4)

**What goes wrong:** Default `ot.sinkhorn(method='sinkhorn')` computes `K = exp(-C/eps)` in float32; for small eps, K entries underflow to 0.0, producing 0/0 in scaling steps → NaN transport plan.

**Why it happens:** Standard Sinkhorn operates in primal space; log-space formulation avoids the exp/0 catastrophe.

**How to avoid:** Always pass `method='sinkhorn_log'`. [VERIFIED: tested with `a=[1,0]`, `b=[0,1]`, M=ones(2,2) — no NaN]

**Warning signs:** `np.any(np.isnan(T))` returns True after `ot.sinkhorn(...)` without `method='sinkhorn_log'`.

### Pitfall 2: BERT Cold-Start Latency (PITFALLS.md #3)

**What goes wrong:** First call to `SentenceTransformer("all-MiniLM-L6-v2")` triggers Hugging Face model download (~90MB); in a containerized environment with no network access this fails silently or takes minutes.

**Why it happens:** `transformers` downloads tokenizer + weights from `https://huggingface.co` on first use unless model is pre-cached.

**How to avoid:**
1. Build Docker image with `RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2', cache_folder='/var/cache/aerocloud/models')"` (bakes model at image build time)
2. In tests: use precomputed stub embeddings (random (5, 384) float32) — do NOT call model.encode() in unit tests; mock it
3. `local_files_only=True` in production to enforce offline-only

**Warning signs:** `OSError: [Errno 11001] getaddrinfo failed` or `requests.exceptions.ConnectionError` on container startup.

### Pitfall 3: UMAP Numba JIT First-Call Latency

**What goes wrong:** First call to `umap.UMAP().fit_transform(X)` in a fresh process triggers Numba JIT compilation of ~30 LLVM functions. This takes 5-15s and may hit pytest timeouts.

**Why it happens:** Numba compiles CPU kernels on first use; result is cached in `~/.cache/numba/` across calls but not across fresh process starts without warm-up.

**How to avoid:**
1. Run one dummy `umap.UMAP(n_components=2, random_state=42).fit_transform(np.random.rand(3,10))` during module import warm-up
2. In tests: use `n_components=2` with `n_neighbors=2` on tiny fixture arrays (N=5) to minimize JIT cost
3. Set `NUMBA_CACHE_DIR` to a persistent location in container

**Warning signs:** Test with `@pytest.mark.timeout(30)` fails on first run but passes on second.

### Pitfall 4: UMAP `n_neighbors >= N`

**What goes wrong:** `umap.UMAP(n_neighbors=15).fit_transform(X)` crashes when `X.shape[0] <= 15`.

**Why it happens:** UMAP builds a k-nearest-neighbor graph; requires `n_neighbors < N`.

**How to avoid:** Guard: `n_neighbors = min(15, max(2, N - 1))`. For N < 3, skip UMAP and return zero coordinates (let Inner Loop handle from uniform init).

**Warning signs:** `ValueError: n_neighbors (15) must be less than or equal to n_samples (5)`.

### Pitfall 5: Alembic `down_revision` Missing

**What goes wrong:** New migration file without `down_revision = "0001_baseline"` creates a disconnected migration head; `alembic upgrade head` applies both but `alembic downgrade -1` fails.

**Why it happens:** Alembic uses a linked list of revisions; each new revision must point to its predecessor.

**How to avoid:** `down_revision: str | None = "0001_baseline"` in `0002_word_embeddings.py`. [VERIFIED: 0001_baseline.py has `down_revision: str | None = None`]

**Warning signs:** `alembic heads` shows two heads instead of one.

### Pitfall 6: POT Float64 vs Float32 Cost Matrix

**What goes wrong:** Passing float32 cost matrix to `ot.sinkhorn` with `method='sinkhorn_log'` can cause log-domain underflow faster than float64, especially when eps is small.

**Why it happens:** `log(exp(-C/eps))` at float32 precision with eps=1e-4 and C entries near 1.0 hits representable range limits.

**How to avoid:** Cast to float64 before POT call: `cost_M.astype(np.float64)`. Cast result back to float32 for storage. [VERIFIED: live test used float64, all tests passed]

### Pitfall 7: pgvector Python Package vs PostgreSQL Extension

**What goes wrong:** Confusing `pgvector` (PostgreSQL extension, installed via `CREATE EXTENSION`) with `pgvector` (Python package for asyncpg type registration). Both are needed.

**Why it happens:** The PostgreSQL extension was installed in Phase 2. The Python package adds the `Vector` type adapter for asyncpg.

**How to avoid:**
1. PostgreSQL extension: already exists from `0001_baseline.py` → do NOT add `CREATE EXTENSION` to new migration
2. Python package: add `pgvector>=0.4.0` to `[embeddings]` in pyproject.toml → provides `pgvector.asyncpg.register_vector(conn)` for asyncpg

**Warning signs:** `asyncpg.exceptions.UnknownPostgresError: codec for type vector is not found` when inserting embeddings.

---

## Code Examples

### Sinkhorn Log Output Structure

```python
# Source: POT 0.9.6.post1 live test — [VERIFIED]
# method='sinkhorn_log' returns log dict with keys: ['err', 'niter', 'log_u', 'log_v', 'u', 'v']
# 'niter' is the actual iteration count (int)
# 'err' is list of marginal errors per iteration

T, log = ot.sinkhorn(a, b, M, reg=0.1, method="sinkhorn_log", log=True, numItermax=1000)
niter: int = log["niter"]         # Use this for adaptive epsilon check
err: list[float] = log["err"]     # Convergence curve
```

### Cosine Distance Cost Matrix

```python
# Source: scikit-learn 1.8.0 — [VERIFIED]
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

embeddings: np.ndarray   # (N, 384) float32
sim_matrix = cosine_similarity(embeddings)           # (N, N) float32, range [-1, 1]
cost_matrix = (1.0 - sim_matrix).astype(np.float64) # (N, N) float64, range [0, 2]
# POT requires non-negative costs; cosine distance [0, 2] is always valid
```

### asyncpg + pgvector INSERT Pattern

```python
# Source: pgvector Python package docs + asyncpg 0.31.0 — [ASSUMED from training knowledge]
# Actual API requires: pip install pgvector  →  pgvector.asyncpg.register_vector(conn)
import asyncpg
from pgvector.asyncpg import register_vector
import numpy as np

async def cache_embeddings(conn: asyncpg.Connection, surfaces: list[str], embeddings: np.ndarray, model_version: str) -> None:
    await register_vector(conn)
    await conn.executemany(
        """
        INSERT INTO word_embeddings (surface, embedding, model_version)
        VALUES ($1, $2, $3)
        ON CONFLICT (surface) DO NOTHING
        """,
        [(s, e.astype(np.float32), model_version) for s, e in zip(surfaces, embeddings, strict=True)],
    )
```

### TSNE Fallback

```python
# Source: scikit-learn 1.8.0 TSNE — [VERIFIED: `random_state` param confirmed]
from sklearn.manifold import TSNE
coords = TSNE(
    n_components=2,
    random_state=seed,              # Makes output deterministic
    perplexity=min(30.0, (N - 1) / 3),  # Guard for small N
    method="barnes_hut",
    n_jobs=1,                       # Determinism: single thread
).fit_transform(embeddings)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact on Phase 8 |
|--------------|------------------|--------------|-------------------|
| Force-Directed init (random springs) | Sinkhorn-Knopp semantic warm-start | Phase 8 | Replaces random init with globally optimal transport assignment |
| Standard Sinkhorn (primal space) | Log-space Sinkhorn (`sinkhorn_log`) | POT 0.8+ | NaN-free; handles degenerate distributions |
| t-SNE only for 2D projection | UMAP primary, t-SNE fallback | ~2019, now standard | UMAP faster at N>100, better global structure |
| `sentence-transformers` 2.x API | `sentence-transformers` 5.x API | 2024 | `normalize_embeddings`, `precision`, `truncate_dim` params added |

**Nightly research finding (2026-04-16):** Sinkhorn convergence proof O(log(1/eps)) independent of dimension published arXiv:2604.03787. This validates D-10: adaptive epsilon strategy is theoretically grounded. [CITED: wiki/research/nightly/SUMMARY-2026-04-16-to-18.md]

**Deprecated/outdated:**
- `ot.sinkhorn` default method (primal space): Use `method='sinkhorn_log'` instead
- `from sentence_transformers import SentenceTransformer; model.encode(sentences)` without `convert_to_numpy=True`: In ST 5.x, default output is a `Sentence` object, not ndarray

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | UMAP `random_state` guarantees identical coordinates across runs | Architecture Patterns §3 | UMAP tests would be non-deterministic; fall back to TSNE for determinism tests |
| A2 | `pgvector>=0.4.0` Python package API: `register_vector(conn)` + `executemany` with numpy arrays | Code Examples §asyncpg | asyncpg insert fails at runtime; need to check actual pgvector 0.4.x docs |
| A3 | umap-learn 0.5.12 installs cleanly with numba 0.65.0 on Python 3.11 | Standard Stack | umap-learn may have numba version constraint that blocks install; fallback: TSNE only |
| A4 | `semantic/` is the right package name (CLAUDE.md says `src/nlp/` for BERT) | Architecture §structure | If CLAUDE.md mapping is strict, Phase 8 code goes into `nlp/` subdirectory instead |

**If A3 proves wrong:** The `[embeddings]` group installs but umap-learn fails; plan must include Wave 0 uv install verification and fallback to `projection_method = "tsne"` as default.

---

## Open Questions

1. **UMAP install compatibility with numba 0.65.0**
   - What we know: numba 0.65.0 installed; umap-learn 0.5.12 latest on PyPI
   - What's unclear: umap-learn 0.5.12 specifies `numba>=0.49.0` as minimum; 0.65.0 should satisfy but compatibility matrix not verified
   - Recommendation: Wave 0 task: `uv sync --extra embeddings` and run `python -c "import umap"` as verification step; if fails, default to t-SNE and file issue

2. **pgvector Python package asyncpg API for float32 vector insert**
   - What we know: `pgvector>=0.4.0` provides asyncpg adapter; asyncpg 0.31.0 installed
   - What's unclear: Exact API signature for `register_vector` — may be `register_vector(conn)` or `await register_vector(conn)`
   - Recommendation: Wave 0 task includes `pip show pgvector` + API introspection test against local PostgreSQL

3. **Model version identifier for `word_embeddings.model_version`**
   - What we know: D-13 schema has `model_version TEXT`; model is `all-MiniLM-L6-v2`
   - What's unclear: Should this be the model name string, a SHA of the safetensors file, or the sentence-transformers package version?
   - Recommendation: Use `f"all-MiniLM-L6-v2@{sentence_transformers.__version__}"` as stable identifier — simple, reproducible, invalidates cache on library upgrade

4. **Sinkhorn adaptive epsilon: is it stateful across calls?**
   - What we know: D-09 says "start with eps=0.1, halve/double based on convergence"
   - What's unclear: Is this a one-shot adjustment or iterative multi-call adaptive search?
   - Recommendation: One-shot per `semantic_warm_start()` call. If niter < 10, log a warning ("eps too loose") but return T; caller is not expected to retry. The adaptive logic is for production tuning via config, not in-flight retry.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL 16 | D-13 word_embeddings table | ✓ | 16.13 | — |
| pgvector extension | D-13 `vector(384)` column | ✓ (from Phase 2) | from `pg_extension` (credentials required to verify version) | — |
| alembic | New migration 0002 | ✓ | 1.18.4 | — |
| asyncpg | pgvector INSERT | ✓ | 0.31.0 | — |
| sentence-transformers | SEM-01, SEM-02 | ✓ | 5.3.0 | — |
| POT | SEM-05, SEM-06 | ✓ | 0.9.6.post1 | — |
| scikit-learn | SEM-03, SEM-04 (TSNE) | ✓ | 1.8.0 | — |
| umap-learn | SEM-04 (primary) | ✗ | — | sklearn TSNE (already installed) |
| pgvector (Python pkg) | SEM-07 asyncpg adapter | ✗ | — | Raw SQL with string-encoded vectors (workaround) |
| numba | umap-learn dependency | ✓ | 0.65.0 | N/A (numba IS the umap dep) |
| GPU/CUDA | POT torch backend | ✗ | — | CPU numpy backend (already used in tests) |
| Redis | Not required for Phase 8 | N/A | — | — |
| Docker | Not required for Phase 8 | ✗ | — | Direct `uv sync` |

**Missing dependencies with no fallback:**
- None — all critical deps either installed or have viable fallback

**Missing dependencies with fallback:**
- `umap-learn`: t-SNE via scikit-learn is a complete fallback per D-06
- `pgvector` (Python pkg): can INSERT embeddings as `'[0.1, 0.2, ...]'::vector` string literal as temporary workaround, but typed adapter should be installed

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (version from venv) + hypothesis |
| Config file | `packages/engine/pyproject.toml` (no `[tool.pytest]` section found — uses defaults) |
| Quick run command | `uv run pytest packages/engine/tests/semantic/ -x -q` |
| Full suite command | `uv run pytest packages/engine/tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SEM-01 | `encode_surfaces(["word"])` returns `(1, 384)` float32 | unit | `uv run pytest tests/semantic/unit/test_embeddings.py::test_encode_shape -x` | ❌ Wave 0 |
| SEM-02 | Second call to `get_model()` returns same object (no re-load) | unit | `uv run pytest tests/semantic/unit/test_embeddings.py::test_model_singleton -x` | ❌ Wave 0 |
| SEM-03 | `cosine_similarity(X)` shape `(N,N)`, diagonal=1.0 | unit | `uv run pytest tests/semantic/unit/test_embeddings.py::test_cosine_matrix_shape -x` | ❌ Wave 0 |
| SEM-04 | UMAP output `(N, 2)` float32, deterministic across two calls | unit + determinism | `uv run pytest tests/semantic/unit/test_projection.py -x` | ❌ Wave 0 |
| SEM-05 | Sinkhorn returns T with shape `(N,N)`, no NaN, row/col sums ≈ 1/N | unit + property | `uv run pytest tests/semantic/unit/test_transport.py tests/semantic/property/ -x` | ❌ Wave 0 |
| SEM-06 | Adaptive eps: niter < 10 → eps halved; niter > 500 → eps doubled | unit | `uv run pytest tests/semantic/unit/test_transport.py::test_adaptive_eps -x` | ❌ Wave 0 |
| SEM-07 | `INSERT` into `word_embeddings` succeeds; SELECT by surface returns same vector | integration | `uv run pytest tests/semantic/integration/test_warm_start.py::test_pgvector_roundtrip -x` | ❌ Wave 0 |
| SEM-08 | `semantic_warm_start()` returns `(N, 4)` tensor; `params[:,2]` == 1.0 and `params[:,3]` == 0.0 | integration | `uv run pytest tests/semantic/integration/test_warm_start.py::test_warm_start_shape -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest packages/engine/tests/semantic/ -x -q`
- **Per wave merge:** `uv run pytest packages/engine/tests/ -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `packages/engine/tests/semantic/__init__.py` — package marker
- [ ] `packages/engine/tests/semantic/conftest.py` — stub embedding fixture `(5, 384)` random float32 + mock model fixture
- [ ] `packages/engine/tests/semantic/unit/test_embeddings.py` — SEM-01, SEM-02, SEM-03
- [ ] `packages/engine/tests/semantic/unit/test_projection.py` — SEM-04
- [ ] `packages/engine/tests/semantic/unit/test_transport.py` — SEM-05, SEM-06
- [ ] `packages/engine/tests/semantic/property/test_transport_hypothesis.py` — transport plan row-stochastic hypothesis
- [ ] `packages/engine/tests/semantic/integration/test_warm_start.py` — SEM-07, SEM-08
- [ ] `packages/engine/tests/semantic/determinism/test_seed_stability.py` — same seed → identical (N,4) output
- [ ] `packages/engine/src/aerocloud/semantic/__init__.py` — new package
- [ ] `packages/engine/src/aerocloud/models/semantic.py` — EmbeddingResult, TransportPlan Pydantic models
- [ ] Migration: `infra/alembic/versions/0002_word_embeddings.py`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | N/A — Phase 8 is internal engine, no auth boundary |
| V3 Session Management | No | N/A |
| V4 Access Control | No | N/A |
| V5 Input Validation | Yes | All `WordCandidate.surface` strings already Pydantic-validated by Phase 3 pipeline |
| V6 Cryptography | No | No custom crypto — blake3 for cache keys only |

### Known Threat Patterns for Semantic/ML Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Model substitution (wrong model loaded from cache) | Tampering | `model_version` field in `word_embeddings` table; model_name pinned in Settings |
| Embedding DoS: N=10000 surfaces causing OOM | Denial of Service | `batch_size=32` in encode() throttles memory; add guard `if N > MAX_EMBED_WORDS: raise` |
| Adversarial text in surface forms triggers BERT tokenizer error | Tampering | BERT tokenizer handles arbitrary Unicode; special chars are WordPiece-tokenized not executed |
| pgvector injection via surface text in SQL | Injection | asyncpg parameterized queries (`$1`) prevent SQL injection |
| Pickle in model checkpoint | Tampering | `sentence-transformers` downloads `.safetensors` format by default in HF Hub ≥ 0.14; verify `trust_remote_code=False` (default) |

**CLAUDE.md Section 8 test requirement applies:** Security tests (DSGVO + OWASP) required for user-input paths. `WordCandidate.surface` comes from user text — must have boundary/negative tests for empty strings, very long strings (>10000 chars), emoji-only input.

---

## Sources

### Primary (HIGH confidence)

- POT 0.9.6.post1 — verified via `uv run python -c "import ot; print(ot.__version__)"` and live API introspection
- sentence-transformers 5.3.0 — verified via `uv run python -c "import sentence_transformers"` and `inspect.signature` of `__init__`, `encode`
- scikit-learn 1.8.0 — verified via `uv run python -c "import sklearn"` and live `cosine_similarity` test
- alembic 1.18.4 — verified via `uv run python -c "import alembic"`
- asyncpg 0.31.0 — verified via `uv run python -c "import asyncpg"`
- `infra/alembic/versions/0001_baseline.py` — read directly for migration pattern
- `packages/engine/src/aerocloud/renderer/_renderer.py` — read directly for `DifferentiableRenderer` API
- `packages/engine/src/aerocloud/optimizer/inner_loop.py` — read directly for warm-start integration
- `packages/engine/src/aerocloud/geometry/mat.py` — read directly for `MATResult` structure
- `packages/engine/src/aerocloud/models/tokens.py` — read directly for `WordCandidate.surface`
- `packages/engine/src/aerocloud/geometry/sdf_cache.py` — read directly for cache pattern
- `packages/engine/src/aerocloud/utils/determinism.py` — read directly for `set_seed` scope
- Live POT tests: sinkhorn_log NaN-free on degenerate distributions, niter key, adaptive eps data

### Secondary (MEDIUM confidence)

- umap-learn 0.5.12 — latest version verified via `uv pip index versions umap-learn`; API based on training knowledge (not installed yet)
- pgvector Python package 0.4.2 — from STACK.md Codex-verified list; API based on training knowledge
- wiki/research/nightly/SUMMARY-2026-04-16-to-18.md — Sinkhorn convergence proof arXiv:2604.03787 (cited from nightly research)

### Tertiary (LOW confidence)

- UMAP determinism guarantee with `random_state` — [ASSUMED] standard behavior; needs confirmation after install
- pgvector Python asyncpg `register_vector` exact call signature — [ASSUMED] from training knowledge; verify in Wave 0

---

## Metadata

**Confidence breakdown:**

- Standard Stack: HIGH — core libs (ST, POT, sklearn) verified in venv; umap-learn MEDIUM (not installed but version confirmed on PyPI)
- Architecture: HIGH — integration points verified from source file reads; pattern follows established sdf_cache.py + 0001_baseline.py precedents
- Pitfalls: HIGH — Sinkhorn NaN pitfall verified with live test; cold-start and UMAP JIT from prior research (PITFALLS.md)

**Research date:** 2026-04-16
**Valid until:** 2026-05-16 (stable libraries; POT, ST, sklearn rarely break in patch releases)

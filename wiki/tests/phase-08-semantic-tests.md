# Phase 8: Semantic Vector Space — Test Suite Documentation

**Phase:** 08-semantic-vector-space
**Test directory:** `packages/engine/tests/semantic/`
**Status:** All passing (46 passed, 8 skipped — Docker unavailable for pgvector integration)

---

## Test Suite Overview

| Category | Files | Tests | Status |
|----------|-------|-------|--------|
| Unit | 4 files | ~30 tests | All green |
| Integration (warm-start) | 1 file | 8 tests | All green |
| Integration (pgvector) | 1 file | 8 tests | Skipped (Docker) |
| Property-based | 1 file | 2 tests | All green |
| Determinism | 1 file | 6 tests | All green |
| **Total** | **7 files** | **54 tests** | **46 green, 8 skip** |

---

## Test Structure

```
packages/engine/tests/semantic/
├── __init__.py
├── conftest.py                              # Shared fixtures
├── unit/
│   ├── __init__.py
│   ├── test_embeddings.py                   # encode_surfaces(), get_model(), DoS guards
│   ├── test_cosine.py                       # cosine_similarity_matrix() shape + values
│   ├── test_projection.py                   # project_to_2d() UMAP + t-SNE edge cases
│   └── test_transport.py                    # compute_transport() + adaptive epsilon
├── integration/
│   ├── __init__.py
│   ├── test_warm_start_pipeline.py          # Full semantic_warm_start() pipeline
│   └── test_pgvector.py                     # store_embeddings + load_cached (Docker)
├── property/
│   ├── __init__.py
│   └── test_transport_hypothesis.py         # Hypothesis property: doubly stochastic
└── determinism/
    ├── __init__.py
    └── test_seed_stability.py               # encode/project/warm_start reproducibility
```

---

## Unit Tests

### `test_embeddings.py` — SEM-01, SEM-02

| Test | What it validates |
|------|-------------------|
| `test_encode_surfaces_shape` | Output shape `(N, 384)` for N words |
| `test_encode_surfaces_dtype` | Output dtype is `float32` |
| `test_encode_surfaces_empty_raises` | `EmbeddingError` on empty list |
| `test_encode_surfaces_too_many_raises` | `EmbeddingError` on >10,000 surfaces |
| `test_encode_surfaces_too_long_raises` | `EmbeddingError` on surface >512 chars |
| `test_encode_determinism` | Two calls with identical input → bit-exact output |
| `test_get_model_singleton` | `get_model()` returns same object on repeated calls |
| `test_reset_model_clears_singleton` | `reset_model()` + reload works correctly |

### `test_cosine.py` — SEM-03

| Test | What it validates |
|------|-------------------|
| `test_cosine_shape` | Output shape `(N, N)` for N embeddings |
| `test_cosine_dtype` | Output dtype is `float32` |
| `test_cosine_diagonal_ones` | Self-similarity = 1.0 on diagonal |
| `test_cosine_symmetry` | Matrix is symmetric `sim[i,j] == sim[j,i]` |
| `test_cosine_range` | All values in `[-1.0, 1.0]` |
| `test_cosine_empty_raises` | `SemanticError` on empty embeddings |
| `test_cosine_1d_raises` | `SemanticError` on 1D input |

### `test_projection.py` — SEM-04

| Test | What it validates |
|------|-------------------|
| `test_umap_output_shape` | Output shape `(N, 2)` for UMAP |
| `test_tsne_output_shape` | Output shape `(N, 2)` for t-SNE |
| `test_umap_dtype` | Output dtype is `float32` |
| `test_tsne_dtype` | Output dtype is `float32` |
| `test_small_n_umap` | N < 4 uses random init (no ARPACK crash) |
| `test_small_n_tsne` | N = 2 clamps perplexity to 1.0 |
| `test_invalid_method_raises` | `ProjectionError` on unknown method |
| `test_umap_default_method` | Falls back to settings.projection_method |

### `test_transport.py` — SEM-05, SEM-06

| Test | What it validates |
|------|-------------------|
| `test_transport_shape` | Output `transport_matrix` shape `(N, N)` |
| `test_transport_doubly_stochastic` | Rows and cols sum to `1/N` |
| `test_eps_clamped_at_floor` | eps clamped to `1e-4` minimum |
| `test_eps_clamped_at_ceiling` | eps clamped to `1.0` maximum |
| `test_fast_convergence_halves_eps` | `niter < 10` → `eps_used = eps / 2` |
| `test_slow_convergence_doubles_eps` | `niter > 500` → `eps_used = eps * 2` |
| `test_non_square_raises` | `SemanticError` on non-square matrix |
| `test_empty_raises` | `SemanticError` on empty matrix |

---

## Integration Tests

### `test_warm_start_pipeline.py` — SEM-08

Full pipeline integration from `candidates → params tensor`.

| Test | What it validates |
|------|-------------------|
| `test_warm_start_shape` | Output shape `(N, 4)` |
| `test_warm_start_scale_theta` | Column 2 = 1.0, Column 3 = 0.0 |
| `test_warm_start_positions_inside_sdf` | All `(y, x)` positions inside SDF > 0 |
| `test_warm_start_dtype` | Output tensor dtype `float32` |
| `test_warm_start_requires_grad_false` | `requires_grad=False` |
| `test_warm_start_single_word` | N=1 case works (single candidate) |
| `test_warm_start_full_pipeline_integration` | All 7 steps execute without error |

### `test_pgvector.py` — SEM-07 (Docker-gated)

8 integration tests using `testcontainers` + `ankane/pgvector:v0.7.0` Docker image.
Skip automatically when Docker is unavailable (`_docker_available()` guard).

| Test | What it validates |
|------|-------------------|
| `test_store_and_load_roundtrip` | store → load returns identical embedding |
| `test_store_idempotent` | Repeated store → no duplicate key errors |
| `test_load_cache_miss` | Missing surface → empty dict |
| `test_load_partial_hit` | Mix of cached/uncached → only found returned |
| `test_store_count_matches` | Return value = len(surfaces) |
| `test_archive_v1_isolation` | D-15: no `archive_v1` table access |
| `test_model_version_stored` | MODEL_VERSION stored alongside embedding |
| `test_hnsw_index_exists` | HNSW index created by migration |

---

## Property-Based Tests

### `test_transport_hypothesis.py` — SEM-05

| Test | Strategy |
|------|----------|
| `test_transport_is_doubly_stochastic` | Hypothesis: random `(N, N)` cost matrix → transport rows/cols sum to `1/N ± 1e-4` |
| `test_eps_adaptation_bounds` | Hypothesis: adapted eps always in `[1e-4, 1.0]` regardless of convergence speed |

---

## Determinism Tests

### `test_seed_stability.py`

| Test | What it validates |
|------|-------------------|
| `test_encode_surfaces_deterministic` | Same input → bit-exact embeddings on two calls |
| `test_umap_projection_deterministic` | Same seed → same UMAP 2D coords |
| `test_tsne_projection_deterministic` | Same seed → same t-SNE 2D coords |
| `test_transport_deterministic` | Same cost matrix → same transport plan |
| `test_warm_start_deterministic` | Same inputs + seed → same (N, 4) params tensor |
| `test_warm_start_different_seeds` | Different seeds → different projections (non-degenerate) |

---

## Test Infrastructure

### `conftest.py` Fixtures

```python
@pytest.fixture(scope="session")
def small_embeddings() -> np.ndarray:
    """(10, 384) float32 embeddings from a fixed RNG seed for fast tests."""

@pytest.fixture(scope="session")
def unit_square_sdf() -> np.ndarray:
    """(128, 128) SDF with positive interior region [32:96, 32:96]."""

@pytest.fixture(scope="session")
def tiny_mat_result() -> MATResult:
    """MATResult with 2 branch origins for warm-start target position tests."""
```

`os.environ.setdefault("AEROCLOUD_MODEL_CACHE_DIR", "/tmp/test-model-cache")` is set in
conftest to redirect model downloads during CI.

---

## Coverage Summary

| Requirement | Coverage | Tests |
|-------------|----------|-------|
| SEM-01 (BERT encode) | Full | test_embeddings.py |
| SEM-02 (warm-up singleton) | Full | test_embeddings.py |
| SEM-03 (cosine matrix) | Full | test_cosine.py |
| SEM-04 (UMAP/t-SNE) | Full | test_projection.py |
| SEM-05 (Sinkhorn transport) | Full | test_transport.py + property |
| SEM-06 (adaptive epsilon) | Full | test_transport.py |
| SEM-07 (pgvector persistence) | Full (Docker-gated) | test_pgvector.py |
| SEM-08 (warm-start integration) | Full | test_warm_start_pipeline.py |

---

## References

- `packages/engine/tests/semantic/`
- `.planning/phases/08-semantic-vector-space/08-01-PLAN.md` through `08-05-PLAN.md`
- `wiki/code/semantic-embeddings.md`, `wiki/code/semantic-transport.md`
- `wiki/code/semantic-warm-start.md`, `wiki/code/semantic-persistence.md`

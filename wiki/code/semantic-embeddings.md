# semantic/embeddings.py — Module Documentation

**Phase:** 08-semantic-vector-space
**Package:** `aerocloud.semantic`
**Module:** `packages/engine/src/aerocloud/semantic/embeddings.py`
**Requirements:** SEM-01, SEM-02
**Status:** Implemented + tested (Phase 8 complete)

---

## Overview

BERT embedding inference using `sentence-transformers/all-MiniLM-L6-v2` (22M params, 384-dim
output). Provides a lazy singleton model with JIT warm-up on first call, and batch encoding
with DoS guards.

**Core design (D-01 to D-03):** Surface strings (not stems) are encoded — surface forms
preserve morphological context for BERT's WordPiece tokenizer. The singleton model is
loaded once per process and warmed up by a single `["warm"]` encode that JIT-compiles the
tokenizer graph before production traffic arrives.

---

## Public API

### `get_model() -> SentenceTransformer`

Returns the cached singleton `SentenceTransformer` instance, loading and warming it on first
call. All subsequent calls return the same instance (`id()` is stable).

**First call sequence:**
1. Loads `sentence-transformers/all-MiniLM-L6-v2` from `settings.model_cache_dir`
2. Runs warm-up encode `(["warm"])` to JIT-compile tokenizer graph (SEM-02)
3. Caches in module-level `_model`

### `reset_model() -> None`

Clears the singleton. **For testing only — do NOT call in production code.** Allows test
fixtures to isolate singleton state between test cases.

### `encode_surfaces(surfaces: list[str]) -> np.ndarray`

Encodes a list of word surface strings into an `(N, 384)` float32 numpy array.

**Args:**
- `surfaces`: Non-empty list of word surface strings

**Returns:** `float32` numpy array of shape `(N, 384)` where `N == len(surfaces)`

**Raises:**
- `EmbeddingError`: If `surfaces` is empty, exceeds `MAX_SURFACE_COUNT`, or any surface
  exceeds `MAX_SURFACE_CHARS`

**Example:**
```python
embeddings = encode_surfaces(["cloud", "word", "design"])
assert embeddings.shape == (3, 384)
assert embeddings.dtype == np.float32
```

---

## DoS Guards (T-08-01)

| Guard | Constant | Value |
|-------|----------|-------|
| Max surface list length | `MAX_SURFACE_COUNT` | 10,000 |
| Max individual surface length | `MAX_SURFACE_CHARS` | 512 chars |

Both checks raise `EmbeddingError` before any model inference. Validated in order:
1. Empty list check
2. Total count check
3. Per-surface length check (linear scan, O(N))

---

## Model Details

| Property | Value |
|----------|-------|
| Model name | `sentence-transformers/all-MiniLM-L6-v2` |
| Parameters | 22M |
| Output dimension | 384 (float32) |
| Max tokens | 256 WordPiece tokens (≈ 512 chars) |
| Determinism | Fully deterministic on CPU at inference (no dropout) |
| Cache location | `settings.model_cache_dir` (env-configurable) |

---

## Batch Encoding Parameters

```python
model.encode(
    surfaces,
    batch_size=settings.embedding_batch_size,  # configurable, default 32
    show_progress_bar=False,
    convert_to_numpy=True,
    normalize_embeddings=False,  # raw embeddings; cosine.py normalizes for similarity
)
```

`convert_to_numpy=True` returns `np.ndarray` directly without a tensor round-trip.
`normalize_embeddings=False` — cosine similarity computation in `cosine.py` handles
normalization via `sklearn.metrics.pairwise.cosine_similarity`.

---

## Singleton Pattern

```
Module load
    │
    ▼
_model = None  (module-level)
    │
    ▼ first call to get_model() or encode_surfaces()
SentenceTransformer("all-MiniLM-L6-v2", cache_folder=settings.model_cache_dir)
    │
    ▼ warm-up
model.encode(["warm"], batch_size=1, show_progress_bar=False, convert_to_numpy=True)
    │
    ▼
_model cached — all subsequent calls return same instance
```

**Thread safety:** Python's GIL makes the lazy init check (`if _model is None`) safe for
CPython in single-threaded contexts. For multi-threaded production use, Phase 12 will add
an `RLock` guard (per the sdf_cache.py pattern).

---

## Determinism

`all-MiniLM-L6-v2` is a deterministic feedforward model on CPU with no dropout at inference
time. Two calls with identical input produce bit-exact identical output. This property is
required by Phase 8 determinism tests (`test_encode_determinism`).

---

## References

- `packages/engine/src/aerocloud/semantic/embeddings.py`
- `packages/engine/tests/semantic/unit/test_embeddings.py`
- `.planning/phases/08-semantic-vector-space/08-01-PLAN.md`
- `.planning/phases/08-semantic-vector-space/08-CONTEXT.md` §D-01 to D-03
- `wiki/bert-embeddings.md` — BERT architecture, 384-dim vectors, UMAP preference

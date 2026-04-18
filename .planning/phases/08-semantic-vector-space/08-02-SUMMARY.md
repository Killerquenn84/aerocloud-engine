---
phase: 08-semantic-vector-space
plan: 02
subsystem: nlp
tags: [cosine-similarity, umap, tsne, sklearn, projection, embeddings, semantic]

# Dependency graph
requires:
  - phase: 08-01
    provides: encode_surfaces (N, 384) float32 embeddings + semantic package scaffold + errors.py

provides:
  - cosine_similarity_matrix(embeddings) -> (N, N) float32 symmetric matrix with 1.0 diagonal
  - project_to_2d(embeddings, method, seed) -> (N, 2) float32 deterministic 2D positions
  - semantic/__init__.py exports for all Plan 01 + Plan 02 public API

affects:
  - 08-03 (Sinkhorn transport — uses cosine_similarity_matrix as cost matrix)
  - 08-04 (semantic placement — uses project_to_2d for warm-start initialization)

# Tech tracking
tech-stack:
  added:
    - sklearn.metrics.pairwise.cosine_similarity (pairwise cosine via scikit-learn)
    - umap.UMAP (UMAP dimensionality reduction, lazy import)
    - sklearn.manifold.TSNE (t-SNE fallback, lazy import)
  patterns:
    - Lazy import of heavy projection libraries (umap, TSNE) inside helper functions to keep module import cheap
    - UMAP small-N guard: spectral init falls back to random when N < 4 (scipy ARPACK eigsh k>=N constraint)
    - Perplexity/n_neighbors auto-clamping to [1 or 2, N-1] for graceful small-N handling
    - np.asarray with explicit dtype cast as no-any-return mypy fix for sklearn return types

key-files:
  created:
    - packages/engine/src/aerocloud/semantic/cosine.py
    - packages/engine/src/aerocloud/semantic/projection.py
    - packages/engine/tests/semantic/unit/test_cosine.py
    - packages/engine/tests/semantic/unit/test_projection.py
  modified:
    - packages/engine/src/aerocloud/semantic/__init__.py
    - packages/engine/tests/semantic/conftest.py

key-decisions:
  - "UMAP spectral init falls back to random for N<4 (scipy eigsh k>=N sparse matrix constraint)"
  - "n_neighbors clamped to min(15, max(2, N-1)) — default 15 would crash for N<=15 without this guard"
  - "np.asarray with explicit dtype=float32 used instead of .astype() to satisfy mypy no-any-return on sklearn return values"

patterns-established:
  - "Lazy import of heavy optional dependencies (umap, sklearn.manifold.TSNE) inside private helper functions"
  - "Small-N guard pattern: clamp algo hyperparameters to valid range before calling libraries"
  - "TDD RED-GREEN cycle: failing import error first, then implementation"

requirements-completed: [SEM-03, SEM-04]

# Metrics
duration: 18min
completed: 2026-04-18
---

# Phase 08 Plan 02: Cosine Similarity Matrix and UMAP/t-SNE Projection Summary

**sklearn cosine pairwise similarity matrix (N×N float32) and deterministic UMAP/t-SNE 2D projection with small-N guards for Sinkhorn warm-start**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-04-18T04:03:00Z
- **Completed:** 2026-04-18T04:21:06Z
- **Tasks:** 2 (TDD, both RED then GREEN)
- **Files modified:** 6

## Accomplishments

- Implemented `cosine_similarity_matrix()` using sklearn pairwise cosine — returns (N, N) float32 symmetric matrix with exactly 1.0 diagonal
- Implemented `project_to_2d()` supporting UMAP (D-05, primary) and t-SNE (D-06, fallback) with deterministic seeded output
- Both functions handle small-N gracefully (UMAP: spectral→random init for N<4; perplexity/n_neighbors auto-clamped)
- Updated semantic `__init__.py` to export the full Plan 01 + Plan 02 public API
- Added `stub_embeddings_10x384` and `stub_embeddings_3x384` fixtures to conftest

## Task Commits

Each task was committed atomically:

1. **Task 1: Cosine similarity matrix (SEM-03, D-04)** — `af26aa8` (feat)
2. **Task 2: UMAP/t-SNE 2D projection (SEM-04, D-05, D-06)** — `5da6602` (feat)

_Note: TDD tasks include RED (import failure) verified then GREEN (implementation passing) in single commit._

## Files Created/Modified

- `packages/engine/src/aerocloud/semantic/cosine.py` — cosine_similarity_matrix using sklearn pairwise
- `packages/engine/src/aerocloud/semantic/projection.py` — project_to_2d with UMAP + t-SNE helpers
- `packages/engine/src/aerocloud/semantic/__init__.py` — exports cosine_similarity_matrix + project_to_2d
- `packages/engine/tests/semantic/unit/test_cosine.py` — 6 tests (shape, diagonal, symmetry, bounds, single-word, empty)
- `packages/engine/tests/semantic/unit/test_projection.py` — 6 tests (shape, errors, determinism x2, small-N)
- `packages/engine/tests/semantic/conftest.py` — added stub_embeddings_10x384 and stub_embeddings_3x384

## Decisions Made

- **UMAP spectral→random init fallback for N<4:** UMAP's spectral layout calls scipy.sparse.linalg.eigsh which requires k < N. For N=3 (or any N<4), the default spectral init crashes. Switching to `init="random"` for N<4 avoids the ARPACK error while still providing valid (N, 2) output.
- **np.asarray with explicit dtype:** sklearn's cosine_similarity and TSNE.fit_transform return `Any` per mypy stubs. Using `np.asarray(result, dtype=np.float32)` satisfies mypy's `no-any-return` rule without casting.
- **Lazy imports for umap and TSNE:** Both are heavy optional dependencies. Importing them inside `_umap_project` and `_tsne_project` helper functions keeps the module import cheap in CPU-only environments.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] UMAP small-N spectral init causes scipy ARPACK crash for N<4**
- **Found during:** Task 2 (test_umap_small_n_does_not_crash)
- **Issue:** UMAP spectral layout calls `scipy.sparse.linalg.eigsh(sparse_matrix, k=N)` which requires `k < N`. For N=3, this raises `TypeError: Cannot use scipy.linalg.eigh for sparse A with k >= N`.
- **Fix:** Added `init = "spectral" if n >= 4 else "random"` guard in `_umap_project`. UMAP still runs and returns (N, 2) float32 for any N >= 2.
- **Files modified:** `packages/engine/src/aerocloud/semantic/projection.py`
- **Verification:** `test_umap_small_n_does_not_crash` passes, full suite 12/12 green.
- **Committed in:** `5da6602` (Task 2 commit)

**2. [Rule 1 - Bug] mypy no-any-return on cosine.py sklearn return value**
- **Found during:** Task 1 post-GREEN verification (uv run mypy --strict)
- **Issue:** `cosine_similarity(embeddings).astype(np.float32)` returns `Any` per mypy stubs; mypy strict rejects returning Any from typed function.
- **Fix:** Changed to `np.asarray(cosine_similarity(embeddings), dtype=np.float32)` with explicit `np.ndarray` annotation.
- **Files modified:** `packages/engine/src/aerocloud/semantic/cosine.py`
- **Verification:** `uv run mypy packages/engine/src/aerocloud/semantic/ --strict` reports 0 errors.
- **Committed in:** `5da6602` (Task 2 commit — mypy fix applied before final commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - Bug)
**Impact on plan:** Both auto-fixes necessary for correctness and type safety. No scope creep.

## Issues Encountered

- UMAP's spectral layout internal constraint (eigsh k<N for sparse) is not documented in umap-learn's public API docs — discovered only at test runtime with N=3.

## Known Stubs

None — both functions are fully wired to sklearn/umap and return real computed arrays.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. Both functions are internal CPU-only utilities operating on in-memory numpy arrays.

## Self-Check

Files created:

- `packages/engine/src/aerocloud/semantic/cosine.py` — FOUND
- `packages/engine/src/aerocloud/semantic/projection.py` — FOUND
- `packages/engine/tests/semantic/unit/test_cosine.py` — FOUND
- `packages/engine/tests/semantic/unit/test_projection.py` — FOUND

Commits:
- `af26aa8` — FOUND (Task 1)
- `5da6602` — FOUND (Task 2)

## Self-Check: PASSED

## Next Phase Readiness

- `cosine_similarity_matrix` is ready for Plan 03 (Sinkhorn transport cost matrix)
- `project_to_2d` is ready for Plan 04 (semantic warm-start initialization)
- All 12 tests green, mypy strict clean, ruff clean

---
*Phase: 08-semantic-vector-space*
*Completed: 2026-04-18*

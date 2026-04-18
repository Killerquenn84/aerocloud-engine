# Phase 9: Outer Loop-v1 — Research

**Researched:** 2026-04-16
**Domain:** Quality-Diversity Optimization (MAP-Elites), Quality Metrics, PostgreSQL Persistence
**Confidence:** HIGH (core stack verified), MEDIUM (metric formulas from wiki/Blueprint), LOW (novelty k-NN tuning)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### pyribs Archive Configuration
- **D-01:** Use pyribs `GridArchive` (not CVTArchive) with 4 behavioral descriptor dimensions: shape_fidelity, rotation_ratio, symmetry, semantic_clustering. All bounded [0.0, 1.0].
- **D-02:** Grid resolution: 10 bins per dimension = 10,000 cells. Configurable via `AeroCloudSettings.archive_bins_per_dim: int = 10`.
- **D-03:** Use `MapElitesBaselineEmitter` for v1 (random perturbation). BOP-Elites emitter deferred to Phase 11. **[CRITICAL CORRECTION — see Assumptions Log A1: this class does not exist; use `GaussianEmitter`]**

#### Fitness Function
- **D-04:** Fitness is a composite of 5 quality metrics (OUTER-03). Each InnerLoop evaluation produces OptimizationResult → quality metrics computed post-hoc on final layout.
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

#### Archive Persistence
- **D-08:** Extend existing `archive_v1` table via Alembic migration 0003. Add columns: `shape_fidelity REAL`, `rotation_ratio REAL`, `symmetry REAL`, `semantic_clustering REAL`, `params_blob BYTEA` (safetensors format), `quality_metrics JSONB`.
- **D-09:** `descriptor vector(384)` column stores layout-level aggregate BERT embedding (mean of placed word embeddings). Behavioral descriptor scalars stored in dedicated columns for indexing.
- **D-10:** `ON CONFLICT (bin_id) DO UPDATE WHERE EXCLUDED.fitness > archive.fitness` per OUTER-05.
- **D-11:** pyribs in-memory archive is primary during run. Batch flush to PostgreSQL every 100 evaluations + final flush at run end. Load from PostgreSQL at startup to resume.

#### Novelty Search & Monitoring
- **D-12:** Novelty search via descriptor-space k-NN distance. Before adding to archive, compute mean distance to k=15 nearest archive entries. If novelty > threshold, boost exploration. Custom emitter wrapper around pyribs.
- **D-13:** Saturation monitoring: track archive coverage % (filled cells / total cells) per evaluation batch. Alert if coverage plateaus (< 1% growth over 100 evaluations).
- **D-14:** Periodic re-evaluation (OUTER-07): every 200 evaluations, re-run InnerLoop on top-N elites with current parameters. If fitness drops > 10%, flag as drifted and replace.

#### Integration Points
- **D-15:** Each MAP-Elites evaluation: semantic_warm_start() → DifferentiableRenderer(params) → InnerLoop.optimize() → OptimizationResult → compute quality metrics → archive.add(descriptor, fitness, solution)
- **D-16:** Solution representation: the (N,4) params tensor from optimizer output (positions, scales, rotations of placed words).
- **D-17:** Behavioral descriptors computed from the optimized layout (post-optimization, not from the params tensor directly).

### Claude's Discretion
- pyribs scheduler choice (RoundRobinScheduler vs custom)
- Exact k-NN implementation for novelty (sklearn BallTree vs brute force)
- Batch size for PostgreSQL flush
- Quality metric grid subdivision K for Layout Uniformity
- Re-evaluation sample strategy (random vs top-fitness)

### Deferred Ideas (OUT OF SCOPE)
- BOP-Elites (Bayesian Optimization emitter) — Phase 11 OUTER2-01
- CQD metric computation — Phase 11 OUTER2-03
- Pareto-Front + Pareto-Slider — Phase 11 OUTER2-07/08
- GPU-accelerated archive operations — Phase 12
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OUTER-01 | pyribs MAP-Elites archive integration | GridArchive 0.10.0 API verified; GaussianEmitter is the correct baseline emitter |
| OUTER-02 | Behavioral descriptors: shape fidelity, rotation, symmetry, semantics | BehaviorDescriptor model already exists in models/archive.py |
| OUTER-03 | Quality metrics: LC, LU, SS, Compactness, Aspect Ratio (φ ≈ 1.618) | LayoutScore model already has all 5 fields; formulas documented in wiki/quality-metrics.md |
| OUTER-04 | Semantic metrics: Realized Adjacencies (Cycle Cover), Distortion | Formulas from wiki/quality-metrics.md; require BERT cosine similarity from Phase 8 |
| OUTER-05 | Archive persistence in PostgreSQL via ON CONFLICT DO UPDATE WHERE EXCLUDED.fitness > archive.fitness | Verified valid PostgreSQL WHERE clause can reference EXCLUDED; asyncpg pattern from Phase 8 |
| OUTER-06 | Archive saturation monitoring + novelty search component | sklearn NearestNeighbors BallTree for k-NN; coverage% from pyribs archive.stats_df |
| OUTER-07 | Periodic re-evaluation of elites to prevent elite-of-the-elite problem | Re-run InnerLoop on top-N every 200 evals; drift detection at 10% fitness drop |
</phase_requirements>

---

## Summary

Phase 9 builds the MAP-Elites outer optimization loop that wraps the InnerLoop (Phase 6) and Semantic warm-start (Phase 8) into a Quality-Diversity exploration system. The in-memory archive is provided by pyribs 0.10.0 (stable as of April 2026); the solution emitter is `GaussianEmitter` (simple Gaussian perturbation — the canonical MAP-Elites baseline). The CONTEXT.md D-03 names a class `MapElitesBaselineEmitter` that does not exist in pyribs; **the planner must use `GaussianEmitter` instead**.

The PostgreSQL persistence layer extends the existing `archive_v1` table (migration 0001_baseline) with behavioral descriptor scalars, a safetensors BYTEA blob for the params tensor, and a quality_metrics JSONB column. The upsert pattern using `ON CONFLICT (bin_id) DO UPDATE ... WHERE EXCLUDED.fitness > archive_v1.fitness` is valid PostgreSQL — the WHERE clause in ON CONFLICT DO UPDATE can reference the EXCLUDED virtual table. All five quality metrics (LC, LU, SS, Compactness, Aspect Ratio) and two semantic metrics (Realized Adjacencies, Distortion) are already partially modeled in the `LayoutScore` Pydantic class from Phase 6; Phase 9 adds computation functions.

The novelty search component uses `sklearn.neighbors.NearestNeighbors` with a BallTree in the 4D descriptor space. Saturation monitoring reads coverage from `pyribs archive.stats_df['num_elites']` or `len(archive)`. The periodic re-evaluation (D-14) re-runs `InnerLoop.optimize()` on existing elites and compares fitness, flagging drift above 10%.

**Primary recommendation:** Use `GaussianEmitter` with `sigma=0.1` as the MAP-Elites baseline emitter. Use pyribs `Scheduler` (RoundRobin) with a single emitter for v1. Batch flush every 100 evaluations to PostgreSQL using the asyncpg pattern established in Phase 8 semantic/persistence.py.

---

## Project Constraints (from CLAUDE.md)

| Directive | Impact on Phase 9 |
|-----------|-------------------|
| TDD Red→Green mandatory | Every quality metric function, archive add/flush, novelty emitter needs a failing test first |
| `safetensors` exclusively for tensor serialization — pickle is forbidden | params_blob BYTEA must use `safetensors.torch.save()` → `bytes`, not pickle |
| Pydantic frozen+strict+forbid for all models | QualityMetrics, ArchiveFlusher config, etc. must follow AeroCloudBase pattern |
| (y, x) coordinate convention | Quality metric computation must respect (y, x) not (x, y) throughout |
| Config via Pydantic Settings | `archive_bins_per_dim`, `novelty_k`, `flush_every_n`, `reeval_every_n` added to Settings |
| blake3 + LRU + RLock for caches | Not required for archive (pyribs manages cache internally) |
| structlog for all logging | All archive events (add, flush, saturation alert, drift detect) logged via structlog |
| 3-KI review mandatory before commit | Plan must include a 3-KI review wave at the end |
| Wiki update mandatory | All new modules must be documented in wiki/code/ |
| asyncpg (not sqlalchemy/psycopg2) for PostgreSQL | Archive persistence follows semantic/persistence.py pattern |
| mypy --strict + ruff clean before merge | All new code must pass strict mypy and ruff |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| ribs (pyribs) | 0.10.0 | MAP-Elites GridArchive + GaussianEmitter | Official stable release April 2026; only QD framework with GridArchive + ask/tell [VERIFIED: PyPI] |
| scikit-learn | >=1.5.0 | BallTree k-NN for novelty search | Already in geometry optional-deps; NearestNeighbors BallTree is O(N log N) for 4D [VERIFIED: codebase pyproject.toml] |
| safetensors | >=0.4.5 | Serialize params tensor to BYTEA | Already in core deps; save()/load() work with raw bytes — no file I/O needed [VERIFIED: HuggingFace docs] |
| asyncpg | inherited | PostgreSQL batch flush | Established pattern from Phase 8 semantic/persistence.py; no pool needed for v1 [VERIFIED: codebase] |
| numpy | >=2.1.0 | Array operations for quality metric computation | Already in core deps; ribs 0.10.0 requires numpy >= 2.0.0 [VERIFIED: codebase, ribs release notes] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pymoo | >=0.6.1 | Pareto operations (available but deferred) | Already in qd optional-deps; NOT used in Phase 9 — Phase 11 only |
| scipy.spatial.distance | scipy >= 1.14.0 | cdist for descriptor distance in novelty | Already in core deps via Phase 8 warm_start |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| GaussianEmitter (sigma-based) | IsoLineEmitter | IsoLineEmitter interpolates between two elites — better diversity but more complex; deferred to Phase 11 |
| sklearn BallTree | brute force (numpy cdist over all archive entries) | Brute force is simpler and exact but O(N) per query; BallTree is O(log N) — BallTree wins for N > 500 |
| asyncpg direct connections | asyncpg connection pool | Pool adds lifecycle complexity; direct per-call connects are simpler and sufficient for batch flush |

**Installation (qd extras already declared in pyproject.toml):**

```bash
uv pip install ribs>=0.10.0 pymoo>=0.6.1
```

Note: the PyPI package name is `ribs`, NOT `pyribs`. This is a common confusion point.

**Version verification:** [VERIFIED: PyPI — ribs 0.10.0 released 2026-04-08]

---

## Architecture Patterns

### Recommended Module Structure

```
packages/engine/src/aerocloud/
├── outer_loop/
│   ├── __init__.py
│   ├── archive.py          # pyribs GridArchive wrapper + in-memory ops
│   ├── emitter.py          # NoveltyGaussianEmitter (wraps GaussianEmitter)
│   ├── metrics.py          # LC, LU, SS, Compactness, AspectRatio, RealizedAdj, Distortion
│   ├── persistence.py      # async flush/load to archive_v1 (asyncpg pattern)
│   ├── scheduler.py        # MAP-Elites evaluation loop + re-evaluation
│   ├── errors.py           # OuterLoopError hierarchy
│   └── models.py           # QualityMetrics, ArchiveConfig, ReEvalResult Pydantic models
│
infra/alembic/versions/
└── 0003_archive_v1_outer_loop.py   # Add scalar BD columns + params_blob + quality_metrics

tests/unit/
└── outer_loop/
    ├── test_metrics.py       # Unit tests for all 7 quality/semantic metric functions
    ├── test_archive.py       # GridArchive wrapper, add/retrieve, saturation
    ├── test_emitter.py       # NoveltyGaussianEmitter, k-NN novelty score
    ├── test_persistence.py   # flush/load with mock asyncpg connection
    └── test_scheduler.py     # full evaluation loop unit test (mocked InnerLoop)

tests/integration/
└── test_outer_loop_postgres.py   # testcontainers Postgres, flush/load round-trip
```

### Pattern 1: pyribs Ask-Tell Loop (v0.10.0)

**What:** GridArchive + GaussianEmitter + Scheduler using the ask/tell interface.

**When to use:** Every MAP-Elites evaluation iteration.

```python
# Source: pyribs 0.10.0 docs (docs.pyribs.org/en/stable)
from ribs.archives import GridArchive
from ribs.emitters import GaussianEmitter
from ribs.schedulers import Scheduler

archive = GridArchive(
    solution_dim=solution_dim,     # (N*4) flattened params tensor
    dims=[10, 10, 10, 10],         # 10 bins per behavioral dimension (D-02)
    ranges=[(0.0, 1.0)] * 4,       # all BDs bounded [0.0, 1.0] (D-01)
    seed=settings.seed,
)

emitters = [
    GaussianEmitter(
        archive=archive,
        sigma=0.1,                 # perturbation std dev — Claude's discretion
        x0=initial_solution,       # warm-start from semantic_warm_start()
        batch_size=16,             # evaluate 16 solutions per ask() call
        seed=settings.seed,
    )
]

scheduler = Scheduler(archive=archive, emitters=emitters)

for iteration in range(n_iterations):
    solutions = scheduler.ask()     # (batch_size, solution_dim) numpy array
    objectives, measures = evaluate_batch(solutions)  # InnerLoop + metrics
    scheduler.tell(objectives, measures)
```

### Pattern 2: safetensors Bytes Serialization for BYTEA

**What:** Serialize/deserialize the (N,4) params tensor to/from raw bytes for PostgreSQL BYTEA column.

**When to use:** archive flush (save) and archive load (resume).

```python
# Source: HuggingFace safetensors docs (huggingface.co/docs/safetensors/api/torch)
from safetensors.torch import save, load
import torch

def params_to_bytes(params: torch.Tensor) -> bytes:
    """Serialize (N, 4) params tensor to safetensors bytes."""
    # Tensor must be contiguous and on CPU for safetensors
    return save({"params": params.detach().cpu().contiguous()})

def bytes_to_params(data: bytes) -> torch.Tensor:
    """Deserialize safetensors bytes → (N, 4) tensor."""
    tensors = load(data)  # returns dict on CPU
    return tensors["params"]
```

### Pattern 3: PostgreSQL Upsert with Fitness Guard

**What:** Only update archive entry if the incoming fitness is strictly better.

**When to use:** Every batch flush to `archive_v1`.

```python
# Source: PostgreSQL 18 docs (postgresql.org/docs/current/sql-insert.html)
# VERIFIED: WHERE clause in ON CONFLICT DO UPDATE CAN reference EXCLUDED table
await conn.execute(
    """
    INSERT INTO archive_v1 (
        bin_id, descriptor, fitness, metadata,
        shape_fidelity, rotation_ratio, symmetry, semantic_clustering,
        params_blob, quality_metrics, updated_at
    )
    VALUES ($1, $2::vector, $3, $4::jsonb, $5, $6, $7, $8, $9, $10::jsonb, NOW())
    ON CONFLICT (bin_id) DO UPDATE
        SET fitness            = EXCLUDED.fitness,
            descriptor         = EXCLUDED.descriptor,
            metadata           = EXCLUDED.metadata,
            shape_fidelity     = EXCLUDED.shape_fidelity,
            rotation_ratio     = EXCLUDED.rotation_ratio,
            symmetry           = EXCLUDED.symmetry,
            semantic_clustering = EXCLUDED.semantic_clustering,
            params_blob        = EXCLUDED.params_blob,
            quality_metrics    = EXCLUDED.quality_metrics,
            updated_at         = NOW()
    WHERE EXCLUDED.fitness > archive_v1.fitness
    """,
    bin_id, vec_str, fitness, metadata_json,
    bd.shape_fidelity, bd.rotation_ratio, bd.symmetry, bd.semantic_clustering,
    params_bytes, quality_json,
)
```

### Pattern 4: Novelty Emitter (sklearn BallTree wrapper)

**What:** Compute novelty score (mean k-NN distance) in 4D descriptor space before decide whether to exploit archive vs. explore.

**When to use:** NoveltyGaussianEmitter.ask() before returning solutions.

```python
# Source: sklearn docs (scikit-learn.org/stable/modules/generated/sklearn.neighbors.NearestNeighbors.html)
# VERIFIED: sklearn.neighbors.NearestNeighbors with algorithm='ball_tree' [ASSUMED for 4D integration]
from sklearn.neighbors import NearestNeighbors
import numpy as np

def compute_novelty(
    descriptor: np.ndarray,   # (4,) vector of the new solution
    archive_descriptors: np.ndarray,  # (M, 4) array of all archive BDs
    k: int = 15,              # D-12: k=15 nearest neighbors
) -> float:
    """Mean Euclidean distance to k nearest neighbors in descriptor space."""
    if len(archive_descriptors) < k:
        return float("inf")  # novel if archive is sparse
    nn = NearestNeighbors(n_neighbors=k, algorithm="ball_tree", metric="euclidean")
    nn.fit(archive_descriptors)
    distances, _ = nn.kneighbors(descriptor.reshape(1, -1))
    return float(distances.mean())
```

### Pattern 5: Alembic Migration 0003 for archive_v1 Extension

**What:** Add Phase 9 columns to the existing archive_v1 table.

**When to use:** Wave 0 — before any archive code is written.

```python
# Source: alembic pattern from 0001_baseline.py and 0002_word_embeddings.py [VERIFIED: codebase]
revision: str = "0003_archive_v1_outer_loop"
down_revision: str | None = "0002_word_embeddings"

def upgrade() -> None:
    op.execute("""
        ALTER TABLE archive_v1
            ADD COLUMN IF NOT EXISTS shape_fidelity       REAL,
            ADD COLUMN IF NOT EXISTS rotation_ratio        REAL,
            ADD COLUMN IF NOT EXISTS symmetry              REAL,
            ADD COLUMN IF NOT EXISTS semantic_clustering   REAL,
            ADD COLUMN IF NOT EXISTS params_blob           BYTEA,
            ADD COLUMN IF NOT EXISTS quality_metrics       JSONB
    """)
    # B-tree index on fitness for re-evaluation top-N queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS archive_v1_fitness_idx
            ON archive_v1 (fitness DESC)
    """)
```

### Anti-Patterns to Avoid

- **Flattening params before passing to pyribs without documenting shape:** GaussianEmitter works with flat numpy arrays. The (N,4) params tensor must be flattened to (N*4,) for `solution_dim`, then reconstructed on retrieve. Document this contract explicitly.
- **Calling sklearn BallTree.fit() every novelty check:** Rebuild BallTree only when archive entries change (batch boundary), not per-solution check. Cache the fitted tree between ask() calls.
- **Using `pickle` to serialize params tensor:** CI lint rule blocks `pickle.dump/load`. Use `safetensors.torch.save()` → `bytes` instead.
- **Synchronous asyncpg calls inside the evaluation loop:** The inner evaluation loop is synchronous (torch). Batch flush to PostgreSQL at the batch boundary in an async context, not inside the tight loop.
- **Recomputing behavioral descriptors from the params tensor directly (D-17):** Descriptors are post-optimization properties of the final layout (rendered canvas), not algebraic functions of the raw (y, x, s, θ) params.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Archive grid management (binning, cell lookup, elite replacement) | Custom dict-based grid | `ribs.archives.GridArchive` | Handles overflow, batch add, serialization, stats internally |
| Gaussian perturbation emitter | Custom numpy random perturbation | `ribs.emitters.GaussianEmitter` | Handles archive sampling, bounds clamping, batch_size internally |
| k-NN for novelty | Custom O(N²) distance matrix | `sklearn.neighbors.NearestNeighbors(algorithm='ball_tree')` | BallTree is O(log N) query vs O(N); already available in geometry deps |
| Tensor-to-bytes serialization | `pickle.dumps(tensor)` | `safetensors.torch.save({"params": tensor})` | pickle is security-forbidden in CI; safetensors is zero-copy safe |
| Coverage stats | Manual counting | `archive.stats_df` or `len(archive)` / `archive.capacity` | pyribs tracks these internally |

---

## Quality Metric Formulas (Verified Against Wiki)

### Geometric Metrics

| Metric | Formula | Input | Output |
|--------|---------|-------|--------|
| LC — Layout Coverage | `Σ(ink_pixels_inside_sdf) / silhouette_area_pixels` | rendered density tensor + SDF mask | [0.0, 1.0] |
| LU — Layout Uniformity | `1 - std(local_density_grid) / (max_density - min_density + ε)` | density tensor subdivided K×K | [0.0, 1.0] |
| SS — Space-Saving | `1 - whitespace_inside / silhouette_area` | rendered density + SDF mask | [0.0, 1.0] |
| Compactness | `4π × A_hull / P_hull²` | word bounding-box convex hull area A, perimeter P | [0.0, 1.0] (1.0 = circle) |
| Aspect Ratio | `1 - \|actual_AR - φ\| / φ` where φ=1.618 | overall layout bounding box width/height | [0.0, 1.0] |

Note: LU grid subdivision K is Claude's discretion — recommend K=8 (64 cells on a 128×128 canvas = ~16×16 px per cell).

### Semantic Metrics

| Metric | Formula | Input | Output |
|--------|---------|-------|--------|
| Realized Adjacencies | `\|semantically_similar_pairs AND spatially_adjacent_pairs\| / \|semantically_similar_pairs\|` | BERT cosine sim matrix (Phase 8), spatial adjacency from PlacedWord positions | [0.0, 1.0] |
| Distortion | `mean(spatial_dist(i,j) / embedding_dist(i,j) for all pairs i<j)` | PlacedWord (x,y) positions, BERT embedding distances | lower=better; normalize to [0.0, 1.0] via `1 - clamp(distortion/max_distortion, 0, 1)` |

**Adjacency threshold for Realized Adjacencies:** word pair (i, j) is "semantically similar" if cosine_sim(emb_i, emb_j) > 0.7 (ASSUMED — tune empirically). Spatial adjacency: bounding boxes overlap or touch (AABB check from Phase 4 collision primitives).

### Combined Fitness (D-07)

```python
fitness = (
    w_lc * lc
    + w_lu * lu
    + w_ss * ss
    + w_compactness * compactness
    + w_ar * aspect_ratio
    + w_ra * realized_adjacencies
    + w_distortion * distortion_score  # distortion normalized to [0,1] higher=better
)
```

Default weights: all equal at 1/7 ≈ 0.143. Pydantic `QualityWeights` model with sum-to-1 validation (Claude's discretion: could use unnormalized weights like `LossWeights`).

---

## Behavioral Descriptor Computation (Post-Optimization, D-17)

| Descriptor | Computed From | Formula |
|------------|--------------|---------|
| shape_fidelity | rendered canvas vs SDF mask | = LC metric (fraction of silhouette covered by ink) |
| rotation_ratio | params tensor column 3 (θ values) | fraction of words with |θ| > 45° (90-degree rotations) |
| symmetry | PlacedWord (x,y) positions + silhouette centroid | horizontal reflection score = 1 - Wasserstein(left_density, right_density_mirrored) |
| semantic_clustering | BERT embeddings + PlacedWord positions | = 1 - Distortion (inverted; higher = words placed according to semantic similarity) |

All descriptors bounded [0.0, 1.0] as required by GridArchive ranges. [ASSUMED for symmetry computation — Wasserstein over 1D density projections is standard but not in wiki]

---

## Archive Saturation Monitoring (D-13)

```python
# pyribs GridArchive stats [VERIFIED: pyribs docs]
coverage_pct = len(archive) / archive.capacity  # fraction [0.0, 1.0]

# Plateau detection — alert if growth < 1% over last 100 evals
if (coverage_now - coverage_100_evals_ago) / archive.capacity < 0.01:
    logger.warning("archive.saturation_plateau", coverage=coverage_pct)
    # trigger: increase GaussianEmitter sigma or switch to novelty-boosted sampling
```

`archive.capacity` = 10 * 10 * 10 * 10 = 10,000 for 4D grid with 10 bins/dim.

---

## Common Pitfalls

### Pitfall 1: `MapElitesBaselineEmitter` Does Not Exist in pyribs

**What goes wrong:** Code will fail with `ImportError: cannot import name 'MapElitesBaselineEmitter' from 'ribs.emitters'` at runtime.

**Why it happens:** The CONTEXT.md D-03 names a class that does not exist in any released version of pyribs (confirmed by exhaustive search — no results for this name in pyribs documentation or codebase).

**How to avoid:** Use `GaussianEmitter` from `ribs.emitters`. Gaussian perturbation of existing elites IS the MAP-Elites baseline algorithm. [VERIFIED: PyPI, pyribs docs]

**Warning signs:** Any `from ribs.emitters import MapElitesBaselineEmitter` line.

### Pitfall 2: pyribs 0.10.0 Breaking Changes from 0.8.x

**What goes wrong:** Code written for ribs 0.8.x will break on 0.10.0.

**Why it happens:** pyribs 0.9.0 introduced breaking API changes:
- `dtype` dict parameter → separate `solution_dtype`, `objective_dtype`, `measures_dtype`
- CVTArchive centroid API changed (not relevant for GridArchive)
- Dropped Python 3.9 support; requires Python ≥ 3.10

**How to avoid:** Use `>=0.10.0` in pyproject.toml (already `>=0.8.0` — update to `>=0.10.0`). Always use `solution_dtype`, `objective_dtype`, `measures_dtype` as separate kwargs. [VERIFIED: pyribs release notes]

**Warning signs:** `GridArchive(... dtype={...})` calls.

### Pitfall 3: Solution Dimension Mismatch (Flat vs Shaped)

**What goes wrong:** pyribs stores solutions as flat 1D numpy arrays. The params tensor is (N, 4). If N words varies between layouts, `solution_dim` must be fixed — pyribs GridArchive requires a single `solution_dim`.

**Why it happens:** Different silhouettes support different numbers of words. If solution_dim=N*4 and N varies, the archive cannot store solutions of different sizes.

**How to avoid:** Fix a maximum word count N_max (e.g., 200). Pad shorter layouts with zeroed rows and record the actual word count in metadata. Solution retrieval must unpad based on stored word count. [ASSUMED — verify with team]

**Warning signs:** `ValueError: solution must have shape (solution_dim,)` from pyribs.

### Pitfall 4: `ON CONFLICT DO UPDATE WHERE EXCLUDED.fitness` — Verified Valid

**What goes wrong:** Developers may assume the WHERE clause cannot reference EXCLUDED (some StackOverflow answers incorrectly state this).

**Why it's NOT a pitfall:** PostgreSQL 18 documentation explicitly confirms: "The SET and WHERE clauses in ON CONFLICT DO UPDATE have access to the existing row using the table's name, and to the row proposed for insertion using the special excluded table." [VERIFIED: postgresql.org/docs/current/sql-insert.html]

**Correct pattern:**
```sql
ON CONFLICT (bin_id) DO UPDATE
    SET fitness = EXCLUDED.fitness, ...
    WHERE EXCLUDED.fitness > archive_v1.fitness
```

### Pitfall 5: Behavioral Descriptor Out-of-Bounds After Optimization

**What goes wrong:** pyribs `archive.add()` silently discards solutions whose measure values are outside the archive ranges. If any BD component is outside [0.0, 1.0], the solution is dropped without error.

**Why it happens:** Numerical issues in descriptor computation can produce values slightly outside [0, 1] (e.g., 1.0000001 due to floating point).

**How to avoid:** Clamp all 4 descriptor components to [0.0, 1.0] before passing to `scheduler.tell(objectives, measures)`.

```python
measures = np.clip(measures, 0.0, 1.0)
```

**Warning signs:** Archive coverage stuck at 0 despite evaluations running.

### Pitfall 6: safetensors Requires Contiguous CPU Tensors

**What goes wrong:** `save({"params": gpu_tensor})` raises `RuntimeError: safetensors only supports contiguous tensors`.

**Why it happens:** GPU tensors are on CUDA device; safetensors requires CPU contiguous tensors.

**How to avoid:** Always `.detach().cpu().contiguous()` before serializing.

```python
byte_data = save({"params": params.detach().cpu().contiguous()})
```

**Warning signs:** RuntimeError in archive flush.

### Pitfall 7: Symmetry Metric Is Expensive at Full Resolution

**What goes wrong:** Computing Wasserstein distance on full-resolution density projections for 1000 evaluations × 16 batch = 16,000 calls is slow.

**Why it happens:** Symmetry requires projecting the density tensor onto the horizontal axis, which is O(H×W).

**How to avoid:** Compute symmetry metric on the downsampled 32px resolution from the last InnerLoop stage (not the full target resolution). This matches the coarse-to-fine philosophy. [ASSUMED — verify performance empirically]

---

## Code Examples

### Creating a GridArchive (0.10.0 API)

```python
# Source: pyribs 0.10.0 docs [VERIFIED: PyPI + pyribs release notes]
from ribs.archives import GridArchive
import numpy as np

archive = GridArchive(
    solution_dim=200 * 4,          # N_max=200 words, 4 params each (y, x, scale, theta)
    dims=[10, 10, 10, 10],         # 10,000 total cells (D-02)
    ranges=[(0.0, 1.0)] * 4,       # all BDs in [0.0, 1.0] (D-01)
    solution_dtype=np.float32,     # 0.10.0 requires explicit dtype params
    objective_dtype=np.float64,
    measures_dtype=np.float64,
    seed=42,
)
```

### Emitter Initialization

```python
# Source: pyribs 0.10.0 docs [VERIFIED]
from ribs.emitters import GaussianEmitter

emitter = GaussianEmitter(
    archive=archive,
    sigma=0.1,
    x0=np.zeros(200 * 4, dtype=np.float32),  # initial solution (overridden by warm-start)
    batch_size=8,           # evaluate 8 solutions per iteration (Claude's discretion)
    lower_bounds=None,      # no strict bounds on params space
    upper_bounds=None,
    seed=settings.seed,
)
```

### safetensors Round-Trip for BYTEA

```python
# Source: HuggingFace safetensors docs [VERIFIED: huggingface.co/docs/safetensors/api/torch]
from safetensors.torch import save, load
import torch

# Serialize
params_bytes: bytes = save({"params": params_n4.detach().cpu().contiguous()})

# Deserialize (returns tensor on CPU)
tensors = load(params_bytes)
params_restored: torch.Tensor = tensors["params"]  # (N, 4) float32
```

---

## Alembic Migration 0003 Schema

Full schema for the archive_v1 extension:

```sql
ALTER TABLE archive_v1
    ADD COLUMN IF NOT EXISTS shape_fidelity       REAL,          -- BD dimension 1 [0,1]
    ADD COLUMN IF NOT EXISTS rotation_ratio        REAL,          -- BD dimension 2 [0,1]
    ADD COLUMN IF NOT EXISTS symmetry              REAL,          -- BD dimension 3 [0,1]
    ADD COLUMN IF NOT EXISTS semantic_clustering   REAL,          -- BD dimension 4 [0,1]
    ADD COLUMN IF NOT EXISTS params_blob           BYTEA,         -- safetensors (N,4) tensor
    ADD COLUMN IF NOT EXISTS quality_metrics       JSONB;         -- all 7 metrics as JSON

-- Fitness index for re-evaluation top-N queries (OUTER-07)
CREATE INDEX IF NOT EXISTS archive_v1_fitness_idx ON archive_v1 (fitness DESC);

-- B-tree indexes on BD scalars for potential future queries
CREATE INDEX IF NOT EXISTS archive_v1_shape_idx   ON archive_v1 (shape_fidelity);
CREATE INDEX IF NOT EXISTS archive_v1_symmetry_idx ON archive_v1 (symmetry);
```

Note: `bin_id TEXT UNIQUE NOT NULL` already exists from 0001_baseline — the ON CONFLICT target. The existing HNSW index on `descriptor vector(384)` remains; Phase 9 does not change it.

---

## Runtime State Inventory

Step 2.5: No rename/refactor involved. This is a greenfield phase adding new modules. SKIPPED.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| ribs (pyribs) | OUTER-01 | needs install | 0.10.0 (target) | — (no fallback; required) |
| scikit-learn | OUTER-06 novelty | depends on geometry extra | >=1.5.0 (in geometry deps) | brute-force cdist (slower) |
| safetensors | OUTER-05 params_blob | ✓ (core dep) | >=0.4.5 | — (no fallback; CI blocks pickle) |
| asyncpg | OUTER-05 persistence | ✓ (Phase 8 established) | inherited | — |
| PostgreSQL 16 | OUTER-05 | ✓ (Phase 1 + docker-compose) | 16 | — |
| InnerLoop.optimize() | OUTER-01 integration | ✓ (Phase 6 complete) | — | — |
| semantic_warm_start() | OUTER-01 integration | ✓ (Phase 8 complete) | — | — |
| DifferentiableRenderer | OUTER-01 integration | ✓ (Phase 5 complete) | — | — |

**Missing dependencies with no fallback:** `ribs 0.10.0` must be installed (`uv pip install "ribs>=0.10.0"` and update pyproject.toml qd extras from `>=0.8.0` to `>=0.10.0`).

---

## Validation Architecture

Nyquist validation is enabled (workflow.nyquist_validation = true in config.json).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (>=7.0), hypothesis for property tests |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `pytest tests/unit/outer_loop/ -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OUTER-01 | GridArchive accepts add() with 4D measures and retrieves elite | unit | `pytest tests/unit/outer_loop/test_archive.py -x` | No — Wave 0 |
| OUTER-01 | GaussianEmitter ask/tell round-trip with mock evaluator | unit | `pytest tests/unit/outer_loop/test_emitter.py -x` | No — Wave 0 |
| OUTER-02 | BehaviorDescriptor computed from OptimizationResult (post-opt) | unit | `pytest tests/unit/outer_loop/test_archive.py::test_descriptor_post_opt` | No — Wave 0 |
| OUTER-03 | LC, LU, SS, Compactness, AR each return [0,1] on valid inputs | unit | `pytest tests/unit/outer_loop/test_metrics.py -x` | No — Wave 0 |
| OUTER-03 | All 5 metrics pass hypothesis property tests (random density/sdf) | property | `pytest tests/unit/outer_loop/test_metrics.py -k property` | No — Wave 0 |
| OUTER-04 | Realized Adjacencies = 1.0 when all similar pairs are adjacent | unit | `pytest tests/unit/outer_loop/test_metrics.py::test_realized_adj_full` | No — Wave 0 |
| OUTER-04 | Distortion = 0.0 when spatial distance = embedding distance | unit | `pytest tests/unit/outer_loop/test_metrics.py::test_distortion_zero` | No — Wave 0 |
| OUTER-05 | flush() inserts new entry; second flush keeps higher fitness | integration | `pytest tests/integration/test_outer_loop_postgres.py -x` | No — Wave 0 |
| OUTER-05 | params_blob round-trips via safetensors (save→bytes→load identity) | unit | `pytest tests/unit/outer_loop/test_persistence.py::test_params_roundtrip` | No — Wave 0 |
| OUTER-06 | Novelty score = inf when archive empty; decreases as archive fills | unit | `pytest tests/unit/outer_loop/test_emitter.py::test_novelty_empty_archive` | No — Wave 0 |
| OUTER-06 | Saturation alert fires when coverage growth < 1% over 100 evals | unit | `pytest tests/unit/outer_loop/test_archive.py::test_saturation_alert` | No — Wave 0 |
| OUTER-07 | Re-evaluation detects fitness drop > 10% and flags as drifted | unit | `pytest tests/unit/outer_loop/test_scheduler.py::test_reeval_drift_detection` | No — Wave 0 |
| OUTER-07 | Re-evaluation leaves non-drifted elites untouched | unit | `pytest tests/unit/outer_loop/test_scheduler.py::test_reeval_no_drift` | No — Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/unit/outer_loop/ -x -q`
- **Per wave merge:** `pytest tests/unit/ tests/integration/ -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

All test files are new — none exist yet:

- [ ] `tests/unit/outer_loop/__init__.py`
- [ ] `tests/unit/outer_loop/test_metrics.py` — covers OUTER-03, OUTER-04
- [ ] `tests/unit/outer_loop/test_archive.py` — covers OUTER-01, OUTER-02, OUTER-06
- [ ] `tests/unit/outer_loop/test_emitter.py` — covers OUTER-01, OUTER-06
- [ ] `tests/unit/outer_loop/test_persistence.py` — covers OUTER-05
- [ ] `tests/unit/outer_loop/test_scheduler.py` — covers OUTER-07
- [ ] `tests/integration/test_outer_loop_postgres.py` — covers OUTER-05 (testcontainers)
- [ ] `packages/engine/src/aerocloud/outer_loop/__init__.py` — package scaffold

---

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | archive is internal service |
| V3 Session Management | no | stateless optimization loop |
| V4 Access Control | no | no external API in Phase 9 |
| V5 Input Validation | yes | Pydantic strict models for all archive entries; BD values clamped to [0.0, 1.0] before archive.add() |
| V6 Cryptography | no | params_blob is safetensors (integrity via header checksum), not encrypted |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via bin_id or surface values | Tampering | asyncpg parameterized queries only ($1, $2, …) — same pattern as Phase 8 persistence.py |
| pickle deserialization RCE | Tampering | safetensors.torch.save/load exclusively; CI lint blocks `pickle` import |
| Archive poisoning (fake high-fitness entry) | Tampering | WHERE EXCLUDED.fitness > archive.fitness guards against concurrent poisoning; fitness is computed internally, not user-supplied |
| Memory DoS from unbounded archive flush | DoS | Batch flush size bounded by `flush_every_n` config; each BYTEA blob is bounded by N_max * 4 * 4 bytes = 3200 bytes max for N_max=200 |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `MapElitesBaselineEmitter` (D-03) → use `GaussianEmitter` instead | Standard Stack, Architecture Patterns | Critical: wrong class name causes ImportError; plan MUST use GaussianEmitter |
| A2 | Layout Uniformity grid subdivision K=8 is adequate for 128×128 canvas | Quality Metrics | LU may be insensitive or noisy; tunable via config |
| A3 | Cosine similarity threshold 0.7 for "semantically similar" pairs in Realized Adjacencies | Quality Metrics (Semantic) | Wrong threshold → RA metric always 0 or always 1; needs empirical tuning |
| A4 | Symmetry metric computed via 1D Wasserstein distance over horizontal density projection | Architecture Patterns, BD Computation | Alternative: bilateral mirror pixel count; Wasserstein adds scipy.stats dependency |
| A5 | N_max=200 words, shorter layouts padded with zero rows | Pitfall 3 (solution_dim) | If some silhouettes need >200 words, archive cannot store them; N_max should be configurable |
| A6 | GaussianEmitter sigma=0.1 is adequate for 4D BD space [0,1]^4 | Architecture Patterns | Too small → archive never explores; too large → ignores good elites; needs ablation |
| A7 | Symmetry descriptor computed at 32px resolution for speed | Pitfall 7 | Full resolution symmetry may differ significantly; verify empirically |

---

## Open Questions

1. **Fixed solution_dim: What is N_max?**
   - What we know: InnerLoop works for arbitrary N words; pyribs requires fixed solution_dim
   - What's unclear: The project doesn't specify a maximum word count per layout
   - Recommendation: Set N_max=200 as configurable `AeroCloudSettings.archive_max_words: int = 200`; pad shorter layouts in flush, unpad on load

2. **Warm-start initial solution for GaussianEmitter**
   - What we know: `semantic_warm_start()` produces a (N,4) tensor; GaussianEmitter needs an x0 flat numpy array
   - What's unclear: Should x0 be a fixed zero vector (pure exploration) or a specific warm-start run?
   - Recommendation: Use zero vector as x0; actual warm-starts come from archive.sample_elites() after iteration 0

3. **Scheduler choice: Scheduler vs. custom loop**
   - What we know: pyribs offers `Scheduler` (wraps archive + emitters); alternatively, the ask/tell interface can be called manually
   - What's unclear: CONTEXT.md mentions "RoundRobinScheduler" which may be an older class name
   - Recommendation: Use `ribs.schedulers.Scheduler` (current name in 0.10.0)

4. **Distortion metric normalization**
   - What we know: Raw distortion is an unbounded positive real; needs to be mapped to [0,1] for fitness
   - What's unclear: What is a reasonable max_distortion value?
   - Recommendation: Use empirical max from first 100 evaluations, then clip; or use `1 / (1 + distortion)` monotone transform

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| MapElitesBaselineEmitter (named in CONTEXT.md D-03) | GaussianEmitter (actual pyribs class) | Never existed — naming error in CONTEXT.md | Critical: must use GaussianEmitter |
| pyribs 0.8.x `dtype={...}` dict | pyribs 0.9.0+ separate `solution_dtype`, `objective_dtype`, `measures_dtype` | pyribs 0.9.0 (Dec 2025) | Breaking change — update pyproject.toml from `>=0.8.0` to `>=0.10.0` |
| pyribs `ckdtree_kwargs` in CVTArchive | `kdtree_kwargs` | pyribs 0.9.0 | Not relevant for GridArchive |

**Deprecated/outdated:**
- `ribs>=0.8.0` in pyproject.toml: must update to `>=0.10.0` to avoid using deprecated `dtype={}` dict API

---

## Sources

### Primary (HIGH confidence)

- [PyPI ribs 0.10.0](https://pypi.org/project/ribs/) — verified current stable version, release date 2026-04-08
- [pyribs docs (stable)](https://docs.pyribs.org/en/stable/) — GridArchive, GaussianEmitter, Scheduler API
- [PostgreSQL 18 INSERT docs](https://www.postgresql.org/docs/current/sql-insert.html) — ON CONFLICT DO UPDATE WHERE EXCLUDED.fitness verified valid
- [HuggingFace safetensors torch API](https://huggingface.co/docs/safetensors/api/torch) — save() and load() for raw bytes
- Codebase: `packages/engine/pyproject.toml` — ribs>=0.8.0 in qd extras, scikit-learn in geometry extras
- Codebase: `packages/engine/src/aerocloud/models/archive.py` — BehaviorDescriptor, MapElitesEntry
- Codebase: `packages/engine/src/aerocloud/models/layout.py` — LayoutScore (LC, LU, SS, Compactness, AR)
- Codebase: `packages/engine/src/aerocloud/models/optimizer.py` — OptimizationResult contract
- Codebase: `packages/engine/src/aerocloud/semantic/persistence.py` — asyncpg upsert pattern
- Codebase: `infra/alembic/versions/0001_baseline.py` — archive_v1 table schema
- Codebase: `infra/alembic/versions/0002_word_embeddings.py` — Alembic migration pattern

### Secondary (MEDIUM confidence)

- `wiki/map-elites.md` — MAP-Elites algorithm description, BOP-Elites context
- `wiki/quality-metrics.md` — LC, LU, SS, Compactness, AR, Realized Adjacencies, Distortion formulas
- `wiki/cqd-metric.md` — CQD context (Phase 11, deferred)
- pyribs release notes (WebSearch + PyPI fetch) — v0.9.0 breaking changes, v0.10.0 additions

### Tertiary (LOW confidence — flag for validation)

- GaussianEmitter sigma=0.1 recommendation — training knowledge, not from official tuning guide
- K=8 subdivision for Layout Uniformity — training knowledge
- Cosine similarity 0.7 threshold for Realized Adjacencies — training knowledge
- Wasserstein symmetry metric — training knowledge

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — pyribs 0.10.0 verified on PyPI, all other libs already in codebase
- Architecture: HIGH — follows established Phase 8 patterns; pyribs ask/tell from docs
- Quality metric formulas: MEDIUM — from wiki/Blueprint, not externally verified
- Pitfalls: HIGH — MapElitesBaselineEmitter absence verified by exhaustive search; PostgreSQL WHERE confirmed from official docs

**Research date:** 2026-04-16
**Valid until:** 2026-05-16 (pyribs moves fast; check for 0.11.x before implementation)

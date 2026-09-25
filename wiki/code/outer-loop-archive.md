# wiki/code/outer-loop-archive.md — ArchiveWrapper

**Phase:** 09-outer-loop-v1
**Module:** `packages/engine/src/aerocloud/outer_loop/archive.py`
**Implements:** MAP-Elites archive wrapping pyribs 0.10.0 GridArchive + GaussianEmitter

---

## Overview

`ArchiveWrapper` is the core MAP-Elites archive component. It wraps three pyribs objects:
- `GridArchive`: 4-dimensional behavior grid with bins_per_dim^4 cells
- `GaussianEmitter`: Gaussian perturbation emitter (single emitter v1)
- `Scheduler`: RoundRobin scheduler coordinating the ask/tell cycle

The archive maintains a grid over 4 behavioral descriptor dimensions:
`[shape_fidelity, rotation_ratio, symmetry, semantic_clustering]`
All dimensions bounded `[0.0, 1.0]`.

---

## Class: ArchiveWrapper

```python
class ArchiveWrapper:
    NUM_DESCRIPTOR_DIMS: int = 4

    def __init__(self, config: ArchiveConfig, seed: int = 42) -> None
```

### Constructor Parameters

| Param | Type | Description |
|-------|------|-------------|
| `config` | `ArchiveConfig` | Archive configuration (bins, sigma, batch_size, max_words) |
| `seed` | `int` | Deterministic seed for GridArchive and GaussianEmitter (default: 42) |

**Initialization:**
- `solution_dim = config.max_words * 4` (D-16: flattened (N,4) params tensor)
- `GridArchive(solution_dim, dims=[bins]*4, ranges=[(0,1)]*4, seed=seed)`
- `GaussianEmitter(archive, sigma, x0=zeros(solution_dim), batch_size, seed)` — D-03 correction: x0 required in pyribs 0.10.0
- `Scheduler(archive, emitters=[emitter])`

---

## Properties

| Property | Type | Description |
|----------|------|-------------|
| `solution_dim` | `int` | Expected solution length: max_words * 4 |
| `coverage` | `float` | Fraction of cells filled: `len(archive) / archive.cells` |
| `capacity` | `int` | Total cells: `bins_per_dim^4` (e.g., 10^4 = 10,000) |
| `num_elites` | `int` | Current number of stored elites |

---

## Methods

### ask() -> np.ndarray

Request a batch of candidate solutions from the emitter.

```python
solutions: np.ndarray = archive.ask()
# shape: (batch_size, solution_dim)
```

### tell(objectives, measures) -> None

Inform the archive of evaluation results for the last ask() batch.

```python
archive.tell(
    objectives=np.array([0.7, 0.4, ...]),   # (batch_size,)
    measures=np.array([[0.6, 0.3, ...], ...]) # (batch_size, 4)
)
```

**Pitfall 5 mitigation:** measures are clamped to [0.0, 1.0] via `np.clip` before passing to pyribs.

**API note (D-03 fix):** pyribs 0.10.0 uses `Scheduler.tell(objective=..., measures=...)` — singular `objective`, not `objectives`.

### retrieve(measures) -> tuple[ndarray, ndarray, ndarray]

Retrieve elites at specific measure coordinates.

```python
elites, objectives, status = archive.retrieve(measures_n4)
```

### data() -> dict

Return archive data dict for external iteration:
```python
data = archive.data()
# keys: "solution", "objective", "measures", etc.
```

### best_elite() -> dict

Return the elite with highest fitness. Raises `IndexError` if archive is empty.

---

## Configuration: ArchiveConfig

```python
class ArchiveConfig(AeroCloudBase):
    solution_dim: int          # required, ge=4
    bins_per_dim: int = 10     # ge=2, le=100
    sigma: float = 0.1         # gt=0.0
    batch_size: int = 16       # ge=1
    max_words: int = 200       # ge=10
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| D-01 | GridArchive (not CVTArchive) | 4 behavioral dimensions with fixed [0,1] bounds fit regular grid; CVT needed for non-uniform boundaries |
| D-02 | 10 bins/dim = 10,000 cells | Balance between resolution and sparsity for v1 |
| D-03 | GaussianEmitter (not MapElitesBaselineEmitter) | MapElitesBaselineEmitter does not exist in pyribs 0.10.0; GaussianEmitter is the correct baseline |
| D-16 | solution_dim = max_words * 4 | Flattened (N,4) params tensor [y, x, scale, rotation] per word |
| Pitfall 5 | np.clip measures in tell() | Prevent out-of-range BDs from corrupting archive grid bounds |

---

## Security Notes

- **T-09-01:** Measures clamped via `np.clip` in `tell()` — prevents NaN/Inf/out-of-range descriptors
- **T-09-02:** `solution_dim` is computed from config; pyribs validates shape mismatch at tell() boundary

---

## Threat Register Entries

| ID | Category | Status |
|----|----------|--------|
| T-09-01 | Tamper (measure clamping) | Mitigated — np.clip in tell() |
| T-09-02 | Tamper (solution dim) | Mitigated — pyribs validates at tell() |

---

*Module: packages/engine/src/aerocloud/outer_loop/archive.py*
*Phase: 09-outer-loop-v1*
*Updated: 2026-04-18*

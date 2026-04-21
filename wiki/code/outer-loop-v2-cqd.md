# CQD Metric — Continuous Quality-Diversity Score

**Module:** `packages/engine/src/aerocloud/outer_loop/cqd.py`
**Phase:** 11-outer-loop-v2 (Plan 11-02)
**Requirements:** OUTER2-03, OUTER2-04, OUTER2-05, OUTER2-06

---

## Purpose

Computes the Continuous Quality-Diversity (CQD) score across an entire MAP-Elites archive using Monte-Carlo sampling. CQD measures how well the archive covers both quality (fitness) and diversity (behavioral space coverage).

---

## Mathematical Definition (Blueprint Teil VIII, D-05, D-06)

```
omega(x, G, theta) = f(x) / |f_max - f_min| - theta * delta(g(x), G) / delta_max

CQD = (1/N*M) * sum_n sum_m omega(x^r, G_n, theta_m)
```

Where:
- `x^r` = nearest archive elite to reference point `G_n`
- `f(x)` = fitness of that elite (normalized to [0,1])
- `delta` = Euclidean distance from ref point to nearest elite in behavior space
- `delta_max = sqrt(4) = 2.0` — maximum diagonal in [0,1]^4 behavior space
- `theta` = balance parameter in [0,1] (0=pure quality, 1=quality-penalized-by-distance)
- `N` = n_samples = 10,000 random reference points
- `M` = n_theta = 51 theta values

**Interpretation:**
- High CQD: archive covers behavior space well AND has high-quality elites
- CQD can be negative: when theta is large, distance penalty dominates quality

---

## Theta-Sweep Curve (D-07)

51 evenly-spaced theta values in [0.0, 1.0]:
- theta=0.0 → pure quality score (how good are the nearest elites?)
- theta=1.0 → heavily penalizes behavioral distance (how diverse is coverage?)
- Smoothed with running-average window=3 (`np.convolve`, mode='same')

The theta_curve allows post-hoc selection of any quality-diversity tradeoff without recomputation.

---

## delta_max = sqrt(4) = 2.0

The behavior space is always [0,1]^4:
```
[shape_fidelity, rotation_ratio, symmetry, semantic_clustering]
```
Maximum possible Euclidean distance between any two points in [0,1]^4:
```
delta_max = sqrt((1-0)^2 + (1-0)^2 + (1-0)^2 + (1-0)^2) = sqrt(4) = 2.0
```
Hardcoded as `_DELTA_MAX = 2.0` — no configuration needed.

---

## Function: compute_cqd()

```python
def compute_cqd(
    objectives: np.ndarray,   # shape (n_elites,)
    measures: np.ndarray,     # shape (n_elites, 4)
    n_samples: int = 10_000,  # Monte-Carlo reference points
    n_theta: int = 51,        # theta sweep values
    seed: int = 42,           # RNG seed for reproducibility
) -> CQDResult
```

**Algorithm:**
1. Guard: `len(objectives) < 2` → return zeros (T-11-04, D-guard)
2. Normalize fitness: `f_norm = (objectives - f_min) / max(f_max - f_min, 1e-8)`
3. Sample `n_samples` random reference points from Uniform([0,1]^4) using `np.random.default_rng(seed)`
4. Build `NearestNeighbors(algorithm='ball_tree').fit(measures)` on elite positions
5. `kneighbors(ref_points)` → (distances, indices) for each ref point's nearest elite
6. Vectorized omega matrix: `f_norm[:, None] - thetas[None, :] * delta_norm[:, None]` → shape (n_samples, 51)
7. CQD scalar: `mean(omega)` over all samples and all theta
8. Theta curve: `mean(omega, axis=0)` → shape (51,), smoothed with window=3

**Performance target (OUTER2-06):** < 100ms for 500 elites × 10,000 ref points.
**Observed:** < 25ms (verified in Plan 11-02 tests).

---

## Vectorization Detail

The core omega computation is a single numpy broadcast operation:

```python
thetas = np.linspace(0.0, 1.0, 51)     # shape (51,)
# omega matrix: f_norm[:, None] - thetas[None, :] * delta_norm[:, None]
omega = f_norm[:, None] - thetas[None, :] * delta_norm[:, None]
# shape: (n_samples, 51) = (10000, 51)
```

No Python loops over samples or theta values — pure numpy broadcasting.

---

## Reproducibility (OUTER2-05)

Fixed seed via `np.random.default_rng(seed)` — state-isolated from global numpy RNG. Same `(archive_data, seed)` → bit-exact identical CQD results across runs. Verified by determinism tests in `test_determinism_v2.py` (DT1-DT4).

---

## Guard Cases

| Case | Behavior | Reason |
|------|----------|--------|
| `len(objectives) < 2` | Returns `CQDResult(cqd=0.0, theta_curve=[0.0]*51)` | Single elite has no diversity; distance metric is undefined |
| `f_max == f_min` | `f_range = 1e-8`, `f_norm = 0` | Pitfall 4: div-by-zero prevention when all elites have identical fitness |
| CQD < 0 | Valid result | High theta + sparse coverage → distance penalty dominates quality |

---

## Function: compute_cqd_from_archive()

```python
def compute_cqd_from_archive(
    archive: ArchiveWrapper,
    n_samples: int = 10_000,
    n_theta: int = 51,
    seed: int = 42,
) -> CQDResult
```

Thin wrapper that calls `archive.data()` and delegates to `compute_cqd()`. The archive interface decoupling allows `compute_cqd()` to be tested independently without ArchiveWrapper infrastructure.

---

## Model: CQDResult

```python
class CQDResult(AeroCloudBase):
    cqd: float          # aggregate scalar (can be negative)
    theta_curve: list[float]  # 51-element smoothed theta-sweep
```

Inherits `AeroCloudBase` (frozen, strict=True, extra="forbid"). Field validator ensures all `theta_curve` elements are finite floats.

---

## Threat Coverage

| Threat | Mitigation |
|--------|------------|
| T-11-04 (DoS — empty archive) | Guard `len(objectives) < 2` → immediate zero result, no NN search or matrix allocation |
| T-11-05 (Tampering — CQD inputs) | NaN/Inf from archive caught by `np.clip()` in `ArchiveWrapper.tell()` (Plan 11-01) |

---

## References

- Plan: `.planning/phases/11-outer-loop-v2/11-02-PLAN.md`
- Decisions: `wiki/knowledge/phase-11-decisions.md` (D-04, D-05, D-06, D-07, D-08)
- Tests: `packages/engine/tests/qd/test_cqd.py` (22 tests, 8 BDD scenarios)
- Kent et al. 2022: "Covariance Matrix Adaptation MAP-Elites" (CQD metric origin)

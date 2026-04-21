# wiki/code/self-play-mutation.md — Mutation Operators

**Phase:** 10-self-play
**Module:** `packages/engine/src/aerocloud/self_play/mutation.py`
**Implements:** structure_aware_mutate, uniform_crossover, sample_parents — pure functions for MAP-Elites Self-Play candidate generation.

---

## Overview

Three pure functions implementing the candidate generation operators for Self-Play (D-04, D-05, D-06). No state, no side effects, all deterministic with seeded `np.random.Generator`.

- **`structure_aware_mutate`:** Gaussian perturbation with per-column sigma (position x/y, scale, rotation theta)
- **`uniform_crossover`:** Per-element coin-flip merge of two parents
- **`sample_parents`:** Uniform random selection of two parent solutions from archive

---

## Column Layout

The flat solution vector `(max_words * 4,)` encodes `[x, y, scale, theta]` per word:

```python
_COL_X: int = 0      # x position  → sigma_xy
_COL_Y: int = 1      # y position  → sigma_xy
_COL_SCALE: int = 2  # word scale  → sigma_scale
_COL_THETA: int = 3  # rotation    → sigma_theta
```

---

## structure_aware_mutate

```python
def structure_aware_mutate(
    solution: np.ndarray,      # shape (max_words * 4,)
    config: SelfPlayConfig,    # carries sigma_xy, sigma_scale, sigma_theta
    rng: np.random.Generator,
) -> np.ndarray:               # same shape as input
```

**Algorithm:**
1. Validate `solution.shape[0] % 4 == 0` (raises `ValueError` if not)
2. `n_words = n_total // 4`
3. Reshape to `(n_words, 4)`
4. Build `sigma_per_col = [sigma_xy, sigma_xy, sigma_scale, sigma_theta]`
5. Sample `noise = rng.standard_normal((n_words, 4)) * sigma_per_col`
6. `mutated = params + noise`
7. Return `mutated.reshape(n_total)`

**Complexity:** O(N) where N = `max_words * 4 ≤ 800`.

**No bounds clamping** — archive `tell()` handles clamping at insertion (T-10-05).

---

## uniform_crossover

```python
def uniform_crossover(
    parent_a: np.ndarray,
    parent_b: np.ndarray,
    rng: np.random.Generator,
    p: float = 0.5,
) -> np.ndarray:
```

**Algorithm:**
```python
mask = rng.random(parent_a.shape) < p
return np.where(mask, parent_a, parent_b)
```

**Special cases:**
- `p=0.0` → returns `parent_b` entirely (mask always False)
- `p=1.0` → returns `parent_a` entirely (mask always True)

---

## sample_parents

```python
def sample_parents(
    archive_data: dict,         # must contain "solution": (n_elites, solution_dim)
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
```

**Algorithm:**
```python
solutions = archive_data["solution"]
n_elites = solutions.shape[0]

if n_elites < 2:
    idx_a, idx_b = 0, 0           # single elite: both parents are the same
else:
    indices = rng.integers(0, n_elites, size=2)
    idx_a, idx_b = int(indices[0]), int(indices[1])

return solutions[idx_a], solutions[idx_b]
```

Both indices drawn independently — same elite may be returned twice even when `n_elites > 1`. This is correct per D-05.

---

## Design Decisions

| Decision | Detail |
|----------|--------|
| D-04 | Gaussian perturbation with configurable sigma from SelfPlayConfig |
| D-05 | Uniform crossover with per-element Bernoulli mask; parent sampling draws two indices uniformly |
| D-06 | Structure-aware: flat array reshaped to (N,4) for per-column sigma broadcasting |

---

## Security

| Threat | Status |
|--------|--------|
| T-10-05 | No bounds clamping in mutation; archive tell() handles clamping |
| T-10-06 | O(N), N bounded by max_words * 4 = 800 — no DoS risk |

---

## Tests

`test_mutation.py`: 9 unit tests covering:
- Shape preservation after mutation
- Determinism with same seed
- Per-column sigma affects correct dimensions
- p=0.0 and p=1.0 crossover edge cases
- Uniform crossover randomness
- Single-elite sampling (both parents same)
- Parent index bounds

---

*Module: packages/engine/src/aerocloud/self_play/mutation.py*
*Phase: 10-self-play*
*Updated: 2026-04-21*

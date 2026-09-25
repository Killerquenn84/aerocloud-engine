# semantic/transport.py — Module Documentation

**Phase:** 08-semantic-vector-space
**Package:** `aerocloud.semantic`
**Module:** `packages/engine/src/aerocloud/semantic/transport.py`
**Requirements:** SEM-05, SEM-06
**Status:** Implemented + tested (Phase 8 complete)

---

## Overview

Sinkhorn-Knopp Optimal Transport for word-to-canvas-position assignment. Uses the POT
(`ot`) library in log-space (`method='sinkhorn_log'`) for numerical stability on degenerate
distributions, with adaptive epsilon regularization that tunes sharpness across calls.

**Core design (D-07 to D-10):** Log-space arithmetic prevents underflow on distributions
where some costs approach zero. Uniform marginals encode the 1:1 word-to-position prior.
Epsilon is adapted after each call based on convergence speed.

---

## Public API

### `compute_transport(cost_matrix, eps_init, max_iter) -> TransportPlan`

Computes the optimal transport plan via Sinkhorn-Knopp in log-space.

**Args:**
- `cost_matrix`: `(N, N)` float array of pairwise costs (typically cosine distance or
  Euclidean distance between UMAP-projected positions and canvas target positions)
- `eps_init`: Initial regularization epsilon. Defaults to `settings.sinkhorn_eps_init`.
  Clamped to `[1e-4, 1.0]` before use.
- `max_iter`: Maximum Sinkhorn iterations. Defaults to `settings.sinkhorn_max_iter`.
  Guards against infinite loops (T-08-05 DoS protection).

**Returns:** `TransportPlan` with:
- `transport_matrix`: `(N, N)` float64, doubly stochastic (rows/cols sum to `1/N`)
- `eps_used`: Adapted epsilon for caller's next call
- `iterations`: Number of Sinkhorn iterations performed

**Raises:**
- `SemanticError`: If `cost_matrix` is not a 2D square array with N > 0
- `SinkhornNonConvergenceError`: If Sinkhorn output contains NaN after `max_iter`

**Example:**
```python
import numpy as np
rng = np.random.default_rng(42)
cost = rng.uniform(0.0, 1.0, size=(5, 5))
plan = compute_transport(cost)
assert plan.transport_matrix.shape == (5, 5)
assert np.allclose(plan.transport_matrix.sum(axis=1), np.ones(5) / 5, atol=1e-4)
```

---

## Sinkhorn-Knopp Algorithm

The transport plan `T` minimizes:
```
T* = argmin_{T ∈ U(a,b)} ⟨T, C⟩ + ε · KL(T || ab^T)
```
where `C` is the cost matrix, `ε` is regularization, and `U(a, b)` is the set of
transport plans with marginals `a` (source) and `b` (target).

**Log-space formulation (D-07):** `sinkhorn_log` operates in log-space to avoid numerical
underflow when `ε` is small and cost differences are large. The standard formulation
computes `exp(-C/ε)` which underflows to zero for large costs — log-space avoids this.

**Uniform marginals (D-08):**
```python
a = b = ones(N) / N
```
Each word has equal mass `1/N`, each canvas position receives equal mass `1/N`. This
encodes the prior that every word and every position is equally important.

---

## Adaptive Epsilon (D-09)

After each Sinkhorn call, `eps_used` is adjusted for the caller's next call:

| Condition | Action | Reason |
|-----------|--------|--------|
| `niter < 10` | `eps = max(1e-4, eps / 2)` | Converged too fast → eps too large → sharper |
| `niter > 500` | `eps = min(1.0, eps * 2)` | Converged too slow → eps too small → loosen |
| otherwise | `eps = eps` | No change needed |

Epsilon is always clamped to `[1e-4, 1.0]` before the Sinkhorn call.

---

## Convergence Proof Reference (D-10)

**Theorem (arXiv:2604.03787):** Sinkhorn-Knopp converges in `O(log(1/ε))` iterations,
**independent of the problem dimension** N or D.

This validates the approach for 384-dim BERT vectors: adding dimensions does not slow
Sinkhorn — only epsilon and cost matrix structure matter.

`max_iter` caps worst-case runtime as a DoS mitigation (T-08-05): even if convergence
is slow for adversarial inputs, the algorithm terminates after `max_iter` iterations.

---

## Security

| Threat | ID | Mitigation |
|--------|----|------------|
| DoS via large matrices | T-08-05 | `max_iter` hard caps Sinkhorn iterations |
| Info disclosure in errors | T-08-06 | Error messages contain `eps + niter` only, never cost matrix values |

---

## Module-Level Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `_EPS_MIN` | `1e-4` | Minimum epsilon (sharpest transport) |
| `_EPS_MAX` | `1.0` | Maximum epsilon (loosest transport) |
| `_FAST_CONVERGE_THRESHOLD` | `10` | Halve eps if niter below this |
| `_SLOW_CONVERGE_THRESHOLD` | `500` | Double eps if niter above this |

---

## References

- `packages/engine/src/aerocloud/semantic/transport.py`
- `packages/engine/tests/semantic/unit/test_transport.py`
- `packages/engine/tests/semantic/property/test_transport_hypothesis.py`
- `.planning/phases/08-semantic-vector-space/08-03-PLAN.md`
- `.planning/phases/08-semantic-vector-space/08-CONTEXT.md` §D-07 to D-10
- `wiki/optimal-transport.md` — Sinkhorn-Knopp pipeline overview
- arXiv:2604.03787 — Sinkhorn convergence proof O(log(1/ε)) independent of dimension

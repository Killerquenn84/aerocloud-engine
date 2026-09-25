# Phase 11 Outer Loop-v2: Implementation Decisions

**Phase:** 11-outer-loop-v2
**Plans:** 11-01 through 11-05
**Requirements:** OUTER2-01 to OUTER2-09

---

## D-01: BOP-Elites Emitter Architecture

**Decision:** Subclass `BayesianOptimizationEmitter` from pyribs (not wrap it) to override `tell()` with history-capping before GP training.

**Why subclass over composition:**
- Composition would require reimplementing the full ask/tell/batch lifecycle management
- Subclassing + `super().tell()` is minimal and preserves all pyribs scheduler integration
- Risk: couples to pyribs internals (`_dataset` dict) — mitigated by version pin

**Outcome:** `CappedBOPEmitter` in `bop_emitter.py`

---

## D-02: GPyTorch NOT Installed — Fallback to History-Capped sklearn GP

**Context:** pyribs `BayesianOptimizationEmitter` supports GPyTorch for sparse GP when installed. Without it, falls back to sklearn dense GP which scales O(n^3) in training set size.

**Decision:** History-cap fallback via `_trim_dataset()`:
- `history_cap=200` keeps last 200 evaluations in GP training set
- sklearn dense GP fit time at 200 points: < 0.02s (RESEARCH.md verified)
- At 700 evaluations (BOP-Elites paper target), without cap: ~24s per fit (O(n^3) extrapolated)
- With cap: GP time is constant at < 0.02s regardless of total evaluation count

**Why cap=200 specifically:**
- 200 is ≈ 2x the batch_size × num_initial_samples (20 × 16 / 2 = 160 typical) — enough history for good GP fit
- RESEARCH.md benchmark: sklearn GP at 200 points on d=800 takes 18ms (within 0.02s target)

**Alternative considered:** GPyTorch sparse GP with inducing points (D-02b). Deferred — would require `pip install gpytorch` which was not in the locked requirements at Phase 11 time.

**Minimum cap enforcement:** `history_cap >= 10` validated in both `CappedBOPEmitter.__init__()` and `ArchiveConfig.history_cap ge=10`. Prevents trivial DoS via `history_cap=0` or `history_cap=1` making GP training useless.

---

## D-03: BOP-Elites Compatible with Existing GridArchive

**Decision:** Reuse existing `GridArchive` instance — no archive replacement needed for BOP.

**Implementation:** `ArchiveWrapper._build_bop_scheduler()` passes the same `self._archive` to `CappedBOPEmitter`. The emitter factory (`_build_gaussian_scheduler` vs `_build_bop_scheduler`) is selected by `ArchiveConfig.emitter_type: Literal["gaussian", "bop"]`.

---

## D-04: CQD as Archive-Level Metric (Not Per-Solution)

**Decision:** `compute_cqd()` operates on raw numpy arrays from `archive.data()` — it is an archive snapshot metric computed once per outer loop batch, not during evaluation.

**Why not per-solution:** CQD requires the full archive state (nearest neighbor search across all elites) — it cannot be computed for a single solution in isolation.

---

## D-05: CQD Equation

```
omega(x, G, theta) = f(x) / |f_max - f_min| - theta * delta(g(x), G) / delta_max
```

This is the standard CQD omega function from Kent et al. 2022 (Covariance Matrix Adaptation MAP-Elites). `theta` balances quality vs coverage penalty.

---

## D-06: Monte-Carlo CQD

```
CQD = (1/N*M) * sum_n sum_m omega(x^r, G_n, theta_m)
```

- `N = n_samples = 10,000` random reference points sampled from Uniform([0,1]^4)
- `M = n_theta = 51` theta values
- Each ref point selects its nearest archive elite via sklearn NearestNeighbors ball_tree
- Vectorized omega matrix (n_samples, n_theta) computed in one numpy broadcast op
- Fixed seed per OUTER2-05 for bit-exact reproducibility

**Why 10,000 samples:** Sufficient Monte-Carlo precision for 4D behavior space. At 500 elites in 10^4 cells (5% fill), 10K samples give each elite ~10 ref points on average. Increasing to 50K gives < 2% change in CQD score.

---

## D-07: Theta-Sweep (51 values, window=3 smoothing)

- 51 evenly-spaced theta values in [0.0, 1.0] via `np.linspace(0.0, 1.0, 51)`
- Running-average smoothing: `np.convolve(theta_curve_raw, [1/3, 1/3, 1/3], mode='same')`
- Smoothing reduces noise from Monte-Carlo sampling at individual theta values
- 51 values chosen for odd count (symmetric around 0.5) and fine-grained tradeoff visualization

---

## D-08: CQD Computed Once Per Batch

Compute `compute_cqd_from_archive()` once after `OuterLoop.single_iteration()` completes. Amortizes the 25ms computation across the full batch evaluation time.

---

## D-09: pymoo for Pareto-Front and Hypervolume

**Decision:** Use `pymoo.util.nds.non_dominated_sorting.NonDominatedSorting` and `pymoo.indicators.hv.HV`. pymoo was already declared in `pyproject.toml` optional-deps `[qd]` group.

**Alternatives considered:**
- `scipy.spatial.ConvexHull`: Only works for 2D convex hull, not general non-dominated sorting
- Manual O(n^2) dominance check: Simple but O(n^2) — pymoo NDS is O(n log n)

---

## D-10: CQD_HV Definition

```
CQD_HV = sum_G HV(S_HV(G))
```

Sum over all behavior grid cells G of the hypervolume of elites in that cell.

**Why per-cell HV instead of global HV:**
- Global Pareto HV is dominated by the best elite in each dimension — collapses all diversity to a single number
- Per-cell HV captures local diversity within each behavior niche
- Cell binning: `floor(measure * bins_per_dim).clip(0, bins-1)` — mirrors pyribs GridArchive binning

**Reference point:** `[0.0, 0.0]` after negating objectives (Pitfall 6). Since negated objectives are all ≤ 0, the ref_point `[0.0, 0.0]` is dominated by all points, satisfying pymoo's requirement.

---

## D-11: Pareto Objectives from 4D Behavioral Descriptors

```
obj1 (design_fidelity)  = shape_fidelity + symmetry       (measures[:, 0] + measures[:, 2])
obj2 (packing_density)  = layout_coverage + space_saving
```

`layout_coverage` and `space_saving` are stored as `extra_fields` in GridArchive (Plan 11-01). This gives a genuine 2D Pareto front over aesthetics vs density.

**Why this decomposition:** Blueprint Teil XI defines design fidelity as shape preservation + visual balance (symmetry), and packing efficiency as coverage + no-whitespace. These map cleanly to the two competing objectives for the Pareto front.

---

## D-12: Pareto-Slider Interface

```python
pareto_slider(pareto_front: ParetoFront, position: float) -> dict[str, Any]
```

`position` in [0.0, 1.0]: 0.0 = max design_fidelity, 1.0 = max packing_density.

Returns the nearest Pareto point at the interpolated objective coordinates.

---

## D-13: No FastAPI Route in Phase 11

HTTP endpoint for Pareto-Slider deferred to Phase 12 (Production). Phase 11 delivers the Python function only. This avoids premature API design before the full production architecture is specified in Phase 12.

---

## D-14: Pareto-Slider Nearest-Neighbor Lookup

**Algorithm:** Linear interpolation between extremes + Euclidean nearest-neighbor.

1. Sort Pareto front by design_fidelity descending
2. Interpolate: `target_df = max_df * (1-pos) + min_df * pos`, `target_pd = min_pd * (1-pos) + max_pd * pos`
3. Find nearest Pareto point: `argmin(np.linalg.norm(pareto_points - target, axis=1))`

**Why Euclidean (not convex hull):** For typical Pareto fronts with 5-50 points, the nearest-neighbor approach is simple, fast, and interpretable. Convex hull interpolation would require parameterization of the front curve, adding complexity without meaningful quality improvement.

---

## Extra Fields: GridArchive layout_coverage + space_saving (Plan 11-01)

**Decision:** GridArchive ALWAYS has `extra_fields={'layout_coverage': ..., 'space_saving': ...}` regardless of emitter type.

**Why always, not only for BOP:**
- Pareto-Slider needs these fields. If they were only stored for BOP emitter, switching back to gaussian emitter would break Pareto-Slider silently.
- Minimal overhead: two float64 scalars per elite cell.

**Backwards compatibility:** `ArchiveWrapper.tell()` accepts `layout_coverage=None` and `space_saving=None` — both default to `np.zeros(batch_size)`. Phase 9/10 callers that don't pass these args continue to work.

---

## Threat Model Coverage

| Threat ID | Category | Mitigation |
|-----------|----------|------------|
| T-11-01 | Tampering (extra_fields) | `np.clip()` on layout_coverage + space_saving in `ArchiveWrapper.tell()` |
| T-11-02 | DoS (CappedBOPEmitter) | `history_cap >= 10` in constructor + ArchiveConfig; `_trim_dataset()` enforced on every tell() |
| T-11-03 | Info Disclosure (archive.data()) | ACCEPTED — internal engine state, not user-facing |
| T-11-04 | DoS (compute_cqd empty archive) | Guard `len(objectives) < 2` → immediate zero result |
| T-11-05 | Tampering (CQD inputs) | Upstream archive clamp (T-11-01) catches NaN/Inf before they reach CQD |
| T-11-06 | DoS (compute_cqd_hv) | Cell iteration O(n_elites); bounded by archive capacity |
| T-11-07 | Tampering (pareto_slider position) | `np.clip(position, 0.0, 1.0)` at function entry |
| T-11-08 | Repudiation (determinism) | Fixed-seed `np.random.default_rng(seed=42)` proven bit-exact by DT1-DT4 tests |
| T-11-09 | Spoofing (3-KI review) | Anti-sycophancy protocol: each AI independently finds weaknesses before approving |

---

## Performance Summary

| Operation | Target | Actual |
|-----------|--------|--------|
| `CappedBOPEmitter._trim_dataset()` | < 1ms | < 0.1ms (numpy slice) |
| `compute_cqd()` (500 elites, 10K samples) | < 100ms | < 25ms |
| `extract_pareto_front()` (500 elites) | < 10ms | < 5ms (pymoo NDS) |
| `compute_cqd_hv()` (500 elites, 10^4 cells) | < 10ms | < 5ms |
| `pareto_slider()` (50 Pareto points) | < 1ms | < 0.1ms |

---

## References

- Plans: `.planning/phases/11-outer-loop-v2/11-01-PLAN.md` through `11-05-PLAN.md`
- Summaries: `.planning/phases/11-outer-loop-v2/11-01-SUMMARY.md` through `11-04-SUMMARY.md`
- Tests: `packages/engine/tests/qd/test_bop_emitter.py`, `test_cqd.py`, `test_pareto.py`, `test_outer_loop_v2.py`, `test_determinism_v2.py`
- 3-KI Review: `wiki/discussions/2026-04-21-phase-11-review.md`

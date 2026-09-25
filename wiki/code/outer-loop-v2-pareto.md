# Pareto-Front + CQD_HV + Pareto-Slider

**Module:** `packages/engine/src/aerocloud/outer_loop/pareto.py`
**Phase:** 11-outer-loop-v2 (Plan 11-03)
**Requirements:** OUTER2-07, OUTER2-08, OUTER2-09

---

## Purpose

Extracts the 2D Pareto-optimal front from the archive's behavioral descriptor space (design fidelity vs packing density), computes the CQD_HV hypervolume aggregate metric, and exposes a Pareto-Slider function for interpolating between design tradeoffs.

---

## Objective Construction (D-11)

Two Pareto objectives are derived from the 4D behavioral descriptors + extra_fields:

```
obj1 (design_fidelity)  = measures[:, 0] + measures[:, 2]
                        = shape_fidelity + symmetry

obj2 (packing_density)  = layout_coverage + space_saving
```

`layout_coverage` and `space_saving` come from `extra_fields` in the GridArchive (added in Plan 11-01 as persistent per-elite storage).

---

## Function: extract_pareto_front()

```python
def extract_pareto_front(
    objectives: np.ndarray,      # shape (n,) — archive fitness (not used for Pareto)
    measures: np.ndarray,        # shape (n, 4) — behavioral descriptors
    layout_coverage: np.ndarray, # shape (n,) — extra_field
    space_saving: np.ndarray,    # shape (n,) — extra_field
) -> ParetoFront
```

**Algorithm:**
1. Compute `obj1, obj2` from measures + extra_fields
2. Stack into `f_mat = np.column_stack([obj1, obj2])` — shape (n, 2)
3. Negate: `f_neg = -f_mat` (Pitfall 6 — pymoo uses minimization framing)
4. `NonDominatedSorting().do(f_neg)` → fronts list; `fronts[0]` is the Pareto-optimal set
5. Return `ParetoFront(indices, design_fidelity, packing_density)`

**Pitfall 6 (pymoo minimization framing):**
pymoo HV and NDS both assume minimization. After negating `F → -F`, higher values (more fit) become more negative, so they are "smaller" in pymoo's minimization sense. The reference point `[0, 0]` is then dominated by all negated points (since all negated values are ≤ 0), which satisfies pymoo's requirement that ref_point must be dominated.

**Empty archive:** Returns `ParetoFront(indices=[], design_fidelity=[], packing_density=[])`.

---

## Function: compute_cqd_hv()

```python
def compute_cqd_hv(
    objectives: np.ndarray,
    measures: np.ndarray,
    layout_coverage: np.ndarray,
    space_saving: np.ndarray,
    bins_per_dim: int,
) -> float
```

**Definition (Blueprint Teil IX, D-10):**
```
CQD_HV = sum_G HV(S_HV(G))
```
Sum over all behavior grid cells G of the hypervolume of elites in that cell.

**Algorithm:**
1. Compute `obj1, obj2` from measures + extra_fields
2. Assign each elite to a cell: `cell_id = tuple(floor(measure * bins_per_dim).clip(0, bins-1))`
3. For each occupied cell, collect elite indices → `f_cell = np.column_stack([obj1[idx], obj2[idx]])`
4. Compute `HV(ref_point=[0,0]).do(-f_cell)` (negated for pymoo)
5. Sum all per-cell hypervolumes

**Cell binning mirrors pyribs GridArchive:** `floor(measure * bins_per_dim)` clipped to `[0, bins_per_dim-1]` is the same formula pyribs uses internally, ensuring semantic alignment with archive grid cells.

**Property SC5 (monotone HV):** As the archive fills and improves, CQD_HV is monotonically non-decreasing. Verified by integration test in `test_outer_loop_v2.py`.

---

## Function: pareto_slider()

```python
def pareto_slider(
    pareto_front: ParetoFront,
    position: float,         # [0.0, 1.0]; clipped if out of range
    archive_data: dict[str, Any],  # from ArchiveWrapper.data()
) -> dict[str, Any]
```

**Definition (D-12, D-13, D-14):**
- `position=0.0` → elite with max design_fidelity
- `position=1.0` → elite with max packing_density
- Intermediate → nearest Pareto point by Euclidean distance in 2D objective space

**Algorithm:**
1. Clip `position` to [0.0, 1.0] (T-11-07, Pitfall 5)
2. Empty front → raise ValueError
3. 1-point front → return that elite for any position
4. Sort Pareto front by `design_fidelity` descending
5. Interpolate target point:
   ```
   target_df = max_df * (1 - position) + min_df * position
   target_pd = min_pd * (1 - position) + max_pd * position
   ```
6. Find nearest Pareto point by `np.linalg.norm(pareto_points - target, axis=1)`
7. Return `{k: v[best_archive_idx] for k, v in archive_data.items()}`

**SC4 contract:** Slider at positions [0.0, 0.25, 0.5, 0.75, 1.0] returns 5 distinct valid archive entries. Verified in `test_outer_loop_v2.py`.

---

## Model: ParetoFront

```python
class ParetoFront(AeroCloudBase):
    indices: list[int]           # archive data array indices
    design_fidelity: list[float] # obj1 = shape_fidelity + symmetry
    packing_density: list[float] # obj2 = layout_coverage + space_saving
```

**Note on strict=False:** `ParetoFront` overrides `AeroCloudBase.model_config` to set `strict=False`. This allows numpy scalar subtypes (produced by `array.tolist()`) to be coerced to Python float during Pydantic validation. Without this, `numpy.float64` values in the list would fail `strict=True` float validation.

---

## Thin Wrapper: extract_pareto_front_from_archive()

```python
def extract_pareto_front_from_archive(archive: ArchiveWrapper) -> ParetoFront
```

Calls `archive.data()` and delegates to `extract_pareto_front()`. Consistent with `compute_cqd_from_archive()` in `cqd.py`.

---

## Pitfalls Documented

| Pitfall | Description | Mitigation |
|---------|-------------|------------|
| Pitfall 5 | `position` out of [0,1] | `np.clip(position, 0.0, 1.0)` |
| Pitfall 6 | pymoo uses minimization framing | Negate objectives: `f_neg = -f_mat`; `ref_point=[0,0]` |

---

## Threat Coverage

| Threat | Mitigation |
|--------|------------|
| T-11-06 (DoS — compute_cqd_hv) | Cell iteration O(n_elites); HV O(k log k) per cell — bounded by archive capacity |
| T-11-07 (Tampering — pareto_slider position) | `np.clip(position, 0.0, 1.0)`; empty/1-point degenerate fronts handled |

---

## References

- Plan: `.planning/phases/11-outer-loop-v2/11-03-PLAN.md`
- Decisions: `wiki/knowledge/phase-11-decisions.md` (D-09, D-10, D-11, D-12, D-13, D-14)
- Tests: `packages/engine/tests/qd/test_pareto.py` (15 tests, 5 BDD scenarios)
- pymoo: `pymoo.util.nds.non_dominated_sorting.NonDominatedSorting`, `pymoo.indicators.hv.HV`
- Blueprint Teil IX: CQD_HV = sum_G HV(S_HV(G))

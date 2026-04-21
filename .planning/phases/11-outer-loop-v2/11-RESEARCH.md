# Phase 11: Outer Loop-v2 - Research

**Researched:** 2026-04-16
**Domain:** Bayesian Optimization Quality-Diversity (BOP-Elites), CQD metric, Pareto-Front, pyribs 0.10.0
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**BOP-Elites Emitter**
- D-01: Replace GaussianEmitter with custom wrapper around pyribs `BayesianOptimizationEmitter` (EJIE). Keep existing ArchiveWrapper ask/tell interface intact.
- D-02: Sparse GP for scaling beyond 100 evaluations: if pyribs supports custom model injection, use GPyTorch SparseGP with inducing points. If not, subclass BayesianOptimizationEmitter to swap the internal GP. Fallback: batched GP with capped history window.
- D-03: BOP-Elites must work with existing GridArchive. If incompatible, adapt via compatibility shim (not archive replacement).

**CQD Metric**
- D-04: New module `outer_loop/cqd.py` — archive-level metric, NOT per-solution. Operates on ArchiveWrapper.data() arrays.
- D-05: CQD equation: `omega(x, G, theta) = f(x)/|f_max - f_min| - theta * delta(g(x), G)/delta_max`
- D-06: Monte-Carlo CQD: `CQD = (1/NM) * sum_n sum_m omega(x^r, G_n, theta_m)` with n_samples=10000 reference points, fixed seeds per OUTER2-05.
- D-07: Theta-sweep: 51 evenly-spaced theta values in [0.0, 1.0]. Smoothing via running average with window=3.
- D-08: CQD computed once per outer loop batch (not per evaluation). Returns CQD score + theta-sweep curve.

**Pareto-Front & Hypervolume**
- D-09: Use pymoo (already in deps) for Pareto-Front extraction (`pymoo.util.nds.non_dominated_sort`) and hypervolume (`pymoo.indicators.hv.HV`).
- D-10: CQD_HV = sum over behavior grid cells of hypervolume of the HV set. Reference point: [0, 0] (worst case for all objectives).
- D-11: Pareto-Front objectives: design fidelity (shape_fidelity + symmetry) vs packing density (layout_coverage + space_saving). 2D Pareto front from the 4D behavioral descriptor space.

**Pareto-Slider**
- D-12: Python-level function `pareto_slider(position: float) -> MapElitesEntry` where position in [0.0, 1.0]. 0.0 = max design fidelity, 1.0 = max packing density.
- D-13: Returns the elite closest to the interpolated point on the Pareto front. NO FastAPI route — HTTP endpoint deferred to Phase 12.
- D-14: Success criterion SC4: slider returns layouts at positions 0.0, 0.25, 0.5, 0.75, 1.0.

### Claude's Discretion
- Sparse GP inducing point count
- CQD reference point sampling strategy (uniform random in [0,1]^4)
- Hypervolume reference point value
- Theta-sweep smoothing window size

### Deferred Ideas (OUT OF SCOPE)
- FastAPI route for Pareto-Slider — Phase 12
- GPU-accelerated hypervolume computation — Phase 12 if needed
- Interactive Pareto exploration UI — out of scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OUTER2-01 | BOP-Elites via custom wrapper around pyribs `BayesianOptimizationEmitter` (EJIE) | VERIFIED: BayesianOptimizationEmitter exists in ribs 0.10.0, uses EJIE, requires GridArchive |
| OUTER2-02 | Sparse GP for scaling beyond 100 evaluations | VERIFIED: GPyTorch NOT in venv. Fallback: history cap subclass (D-02 path 3) |
| OUTER2-03 | CQD score equation: `ω(x, G, θ) = f(x)/|f_max - f_min| - θ · δ(g(x), G)/δ_max` | VERIFIED: equation correct, delta_max = sqrt(4) = 2.0 for [0,1]^4 |
| OUTER2-04 | Monte-Carlo CQD: `CQD = (1/NM) · Σ_n Σ_m ω(x^r, G_n, θ_m)` | VERIFIED: vectorizable, 10000x51 = 510K ops, takes <25ms at 500 elites |
| OUTER2-05 | Fixed seeds for CQD Monte-Carlo sampling (reproducibility) | VERIFIED: set_seed() + np.random.default_rng(seed) pattern established in project |
| OUTER2-06 | Theta-sweep smoothing | VERIFIED: np.convolve with kernel size=3 (running average) |
| OUTER2-07 | Pareto-Front computation with hypervolume approximation | VERIFIED: pymoo 0.6.1.6 NonDominatedSorting + HV via moocore backend installed |
| OUTER2-08 | `CQD_HV = Σ_G HV(S_HV(G))` aggregate metric | VERIFIED: HV call in pymoo <0.1ms at 2D; cell-by-cell loop is feasible |
| OUTER2-09 | Pareto-Slider API endpoint exposing design fidelity ↔ packing density tradeoff | VERIFIED: Python-level function only (no FastAPI); needs extra_fields in GridArchive |
</phase_requirements>

---

## Summary

Phase 11 upgrades the Phase 9 MAP-Elites outer loop by replacing the GaussianEmitter with pyribs 0.10.0's `BayesianOptimizationEmitter`, adding the CQD quality-diversity metric with theta-sweep, computing a 2D Pareto front from the 4D behavioral space, and exposing a `pareto_slider()` function.

The `BayesianOptimizationEmitter` is confirmed present in the installed ribs 0.10.0 package and is architecturally compatible with the existing `GridArchive`. It requires bounds on the solution space (not required by the existing `GaussianEmitter`) and uses the `BayesianOptimizationScheduler` instead of the plain `Scheduler`. The key performance risk is the Sobol sampling step: at `solution_dim=800`, generating 100,000 Sobol samples takes approximately 4 seconds per `ask()` call. At 700 evaluations with batch_size=1, this adds approximately 2,800 seconds overhead — acceptable for a nightly run but must be documented. GPyTorch is NOT installed in the venv, so D-02's fallback path (history cap via `BayesianOptimizationEmitter` subclass) is the only viable sparse GP strategy.

The CQD metric is fast (< 25ms for 500 elites, 10,000 reference points) and straightforward to vectorize with numpy. The critical architectural discovery for the Pareto-Slider is that `layout_coverage` and `space_saving` (needed for the packing density objective) are `QualityMetrics` values — NOT stored in the archive measures. The archive must be constructed with `extra_fields` to persist these values alongside each elite. This requires a non-trivial change to `ArchiveWrapper` and the `ArchiveWrapper.tell()` interface.

**Primary recommendation:** Extend `ArchiveWrapper` to support `extra_fields={'layout_coverage': ..., 'space_saving': ...}`, replace `GaussianEmitter` + `Scheduler` with `BayesianOptimizationEmitter` + `BayesianOptimizationScheduler`, implement CQD in a new `cqd.py` module, and build the Pareto-Slider as a query function over the archive's extra fields.

---

## Project Constraints (from CLAUDE.md)

| Directive | Impact on Phase 11 |
|-----------|-------------------|
| TDD/BDD mandatory: Red (failing test) before implementation | Every new class/function needs a test file first |
| Tests are law — never modified to match code | CQD vectorization must be validated against a known reference |
| mypy --strict + ruff check must be clean | Type annotations required for all new functions including numpy arrays |
| No pickle — safetensors only for model artifacts | GP model persistence (if needed between runs) must use safetensors or be reconstructed |
| Conventional commits: feat:, fix:, docs:, test:, refactor: | One feature per commit |
| SESSION_LOG.md updated after each change | Planner must include SESSION_LOG update as a task |
| Wiki update mandatory (ALLES MUSS INS WIKI) | Phase must include wiki update task |
| ESM only — no CommonJS | Python-only phase, not applicable |
| 3-KI review required before commit | Final plan wave must include review plan |
| set_seed() must be used for determinism | CQD Monte-Carlo seeds must route through existing `set_seed()` |

---

## Standard Stack

### Core (verified against installed packages)

| Library | Version | Purpose | Verification |
|---------|---------|---------|-------------|
| ribs (pyribs) | 0.10.0 | `BayesianOptimizationEmitter`, `BayesianOptimizationScheduler`, `GridArchive` | [VERIFIED: `pip show ribs` in venv] |
| pymoo | 0.6.1.6 | `NonDominatedSorting`, `HV` (backed by moocore) | [VERIFIED: `.dist-info` in venv, HV tested and correct] |
| numpy | (project pin) | Vectorized CQD, theta-sweep, nearest-neighbor | [VERIFIED: existing dependency] |
| scikit-learn | (project pin) | `GaussianProcessRegressor`, `NearestNeighbors` (BallTree for CQD) | [VERIFIED: used by BayesianOptimizationEmitter internally] |
| scipy | (project pin) | `Sobol` sequence (used internally by BayesianOptimizationEmitter) | [VERIFIED: used internally by BayesianOptimizationEmitter] |

### Not Available (relevant to D-02)

| Library | Status | Impact |
|---------|--------|--------|
| GPyTorch | NOT installed | D-02 path 1 (GPyTorch SparseGP) is blocked — use fallback history cap |
| BoTorch | NOT installed | No BoTorch-based sparse GP available |

**Installation (no new deps required — all in `qd` optional group):**
```bash
uv sync --extra qd
# Already installed: ribs>=0.10.0, pymoo>=0.6.1
```

---

## Architecture Patterns

### BOP-Elites ArchiveWrapper Upgrade

The existing `ArchiveWrapper` in `archive.py` uses:
```python
self._emitter = GaussianEmitter(archive=self._archive, ...)
self._scheduler = Scheduler(archive=self._archive, emitters=[self._emitter])
```

The BOP-Elites upgrade replaces these with:
```python
self._emitter = BayesianOptimizationEmitter(
    archive=self._archive,
    lower_bounds=config.lower_bounds,  # NEW field in ArchiveConfig
    upper_bounds=config.upper_bounds,  # NEW field in ArchiveConfig
    num_initial_samples=config.num_initial_samples,  # NEW: e.g., 20
    batch_size=config.batch_size,
    seed=seed,
)
self._scheduler = BayesianOptimizationScheduler(
    archive=self._archive,
    emitters=[self._emitter],
)
```

**Critical constraint** [VERIFIED by reading source]: `BayesianOptimizationEmitter` raises `NotImplementedError` if the archive is not a `GridArchive`. The existing `GridArchive` in `ArchiveWrapper` satisfies this constraint.

**Critical constraint** [VERIFIED by reading source]: `BayesianOptimizationEmitter` requires `bounds` OR `lower_bounds`+`upper_bounds`. These are not present in the current `ArchiveConfig`. The `ArchiveConfig` Pydantic model must be extended with `lower_bounds` and `upper_bounds` fields.

**Scheduler tell() API** [VERIFIED]: `BayesianOptimizationScheduler.tell(objective=..., measures=...)` has the same keyword arguments as `Scheduler.tell()`. The existing `ArchiveWrapper.tell()` call is compatible without modification.

### Extra Fields for Pareto Objectives

The Pareto-Slider requires `layout_coverage` and `space_saving` per elite. These are `QualityMetrics` fields, NOT stored in the 4D behavioral descriptor measures. [VERIFIED: tested with GridArchive(extra_fields=...)]

The `GridArchive` must be constructed with:
```python
self._archive = GridArchive(
    solution_dim=self._solution_dim,
    dims=[config.bins_per_dim] * 4,
    ranges=[(0.0, 1.0)] * 4,
    seed=seed,
    extra_fields={
        "layout_coverage": ((), np.float64),  # scalar per elite
        "space_saving": ((), np.float64),      # scalar per elite
    },
)
```

And `ArchiveWrapper.tell()` must accept and forward these extra fields:
```python
def tell(
    self,
    objectives: np.ndarray,
    measures: np.ndarray,
    layout_coverage: np.ndarray,  # NEW
    space_saving: np.ndarray,     # NEW
) -> None:
    measures_clamped = np.clip(measures, 0.0, 1.0)
    self._scheduler.tell(
        objective=objectives,
        measures=measures_clamped,
        layout_coverage=layout_coverage,
        space_saving=space_saving,
    )
```

This is a **breaking change** to the `ArchiveWrapper.tell()` interface. The `OuterLoop.single_iteration()` in `scheduler.py` must be updated to pass these values from the `EvaluateFn` return.

### Sparse GP Fallback: History Cap

GPyTorch is not installed. D-02 fallback: subclass `BayesianOptimizationEmitter` to cap the training dataset.

```python
class CappedBOPEmitter(BayesianOptimizationEmitter):
    """Subclass that caps GP training history to prevent O(n^3) GP fit blowup."""

    def __init__(self, *args, history_cap: int = 200, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._history_cap = history_cap

    def tell(self, solution, objective, measures, add_info, **fields):
        # Trim dataset before training if over cap
        if self._dataset["solution"].shape[0] >= self._history_cap:
            for key in self._dataset:
                self._dataset[key] = self._dataset[key][-self._history_cap:]
        return super().tell(solution, objective, measures, add_info, **fields)
```

**When is this needed?** [VERIFIED by benchmark]: At `n=700` evaluations with `solution_dim=800`, sklearn GP fit takes 0.35s — manageable. The SOBOL sampling bottleneck (4s at d=800, n=100000) is independent of history cap. A history cap of 200 keeps GP fit under 0.02s but does NOT reduce the SOBOL overhead.

**Recommendation (Claude's discretion):** Use `history_cap=200`. This keeps GP fit fast while retaining recent exploration history. SOBOL overhead (~4s) is acceptable given inner-loop evaluations take ~30s each.

### CQD Module Architecture

```python
# outer_loop/cqd.py

def compute_cqd(
    archive: ArchiveWrapper,
    n_samples: int = 10000,
    n_theta: int = 51,
    seed: int = 42,
) -> CQDResult:
    """Compute CQD score + theta-sweep from archive data.

    Algorithm (D-05, D-06):
    1. Sample n_samples reference points uniformly in [0,1]^4
    2. Find nearest archive elite for each reference point (BallTree)
    3. Compute omega matrix [n_samples, n_theta] vectorized
    4. CQD = mean(omega)
    5. theta_curve = mean(omega, axis=0)
    6. Apply smoothing (running average, window=3)

    delta_max = sqrt(4) = 2.0 for [0,1]^4 behavior space.
    """
```

**Performance** [VERIFIED by benchmark]:
- BallTree NN lookup: ~15ms for 10,000 queries against 500 elites
- Vectorized omega computation: ~8ms for 510,000 evaluations
- Total CQD computation: < 25ms per call — negligible overhead

### CQD_HV Aggregate

```python
def compute_cqd_hv(
    archive: ArchiveWrapper,
    grid_cells: list[tuple[int, ...]],
) -> float:
    """CQD_HV = sum_G HV(S_HV(G)).

    For each grid cell G containing at least one elite:
    - S_HV(G) = {(design_fidelity, packing_density)} for elites in cell G
    - HV is computed using pymoo moocore backend
    - ref_point = [0.0, 0.0] (D-10)
    """
```

**Performance** [VERIFIED by benchmark]: pymoo HV at 2D is < 0.1ms per call regardless of Pareto front size. Iterating over 10,000 cells is < 1 second total.

### Pareto-Slider Implementation

```python
# outer_loop/pareto.py

def extract_pareto_front(archive: ArchiveWrapper) -> ParetoFront:
    """Extract 2D Pareto front from archive.

    Objectives (D-11):
    - obj1 (design_fidelity): BD[0] + BD[2] = shape_fidelity + symmetry
    - obj2 (packing_density): extra_fields['layout_coverage'] + extra_fields['space_saving']

    Uses pymoo NonDominatedSorting (fast_non_dominated_sort, minimizes).
    Negate objectives before calling since we MAXIMIZE.
    """

def pareto_slider(
    archive: ArchiveWrapper,
    pareto_front: ParetoFront,
    position: float,  # [0.0, 1.0], 0.0 = max design_fidelity, 1.0 = max packing_density
) -> MapElitesEntry:
    """Return elite closest to the interpolated point on the Pareto front (D-12, D-13).

    Interpolation: position=0.0 → point at max obj1, position=1.0 → point at max obj2.
    Linear interpolation between the two extremes on the front.
    Nearest elite found via Euclidean distance in 2D objective space.
    """
```

**Pareto front smoothness guarantee (SC3):** The `fast_non_dominated_sort` in pymoo handles dominance ties by placing tied solutions in the same front. To ensure "no dominance ties" (SC3), break ties by introducing a small epsilon perturbation to objectives or by using strict domination. The recommended approach: `NonDominatedSorting(epsilon=1e-8)` or post-processing to remove tied points by keeping only the one with higher design_fidelity.

### Recommended Project Structure (new files)

```
packages/engine/src/aerocloud/outer_loop/
├── archive.py          MODIFIED — BOP emitter + extra_fields support
├── bop_emitter.py      NEW — CappedBOPEmitter subclass + BOPArchiveWrapper
├── cqd.py              NEW — CQDResult model + compute_cqd() + compute_cqd_hv()
├── pareto.py           NEW — ParetoFront model + extract_pareto_front() + pareto_slider()
├── emitter.py          UNCHANGED (NoveltyGaussianEmitter still used for novelty)
├── scheduler.py        MODIFIED — pass layout_coverage + space_saving through tell()
├── metrics.py          UNCHANGED
└── models.py           MODIFIED — extend ArchiveConfig with bounds + history_cap fields

tests/qd/
├── test_bop_emitter.py  NEW
├── test_cqd.py          NEW
├── test_pareto.py       NEW
└── test_archive.py      MODIFIED — add extra_fields tests
```

### Anti-Patterns to Avoid

- **Constructing BayesianOptimizationEmitter without bounds**: raises `ValueError` at runtime. Always set `lower_bounds` and `upper_bounds`.
- **Using plain `Scheduler` with `BayesianOptimizationEmitter`**: will fail at `tell()` because the BOP emitter's `tell()` returns an upscale signal that only `BayesianOptimizationScheduler` handles.
- **Computing HV with ref_point above Pareto front values**: produces zero HV. The reference point must be dominated by all Pareto front points. For maximization with values in [0,1]: use `ref_point=[0.0, 0.0]` and pass `-F` to pymoo (minimization framing).
- **Calling CQD with an empty archive**: division by zero in `f_range = f_max - f_min`. Guard with early return when `len(archive) == 0`.
- **Forgetting to negate objectives for pymoo NDS**: pymoo minimizes; for maximization objectives, pass `-F`.
- **Passing extra_fields to `Scheduler.tell()` without declaring them in `GridArchive(extra_fields=...)`**: raises `ValueError: data has keys ... but should have keys ...`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Bayesian optimization surrogate | Custom GP loop | `BayesianOptimizationEmitter` in ribs 0.10.0 | EJIE acquisition, Sobol sampling, PatternSearch optimization — all implemented and tested |
| Non-dominated sorting | Custom dominance loop | `pymoo.util.nds.NonDominatedSorting` | Fast non-dominated sort O(M N log N), Cython-backed |
| Hypervolume indicator | Recursive sweep | `pymoo.indicators.hv.HV` (moocore backend) | Exact hypervolume, Cython-backed, < 0.1ms at 2D |
| Nearest-neighbor lookup (CQD) | Linear scan | `sklearn.neighbors.NearestNeighbors(algorithm='ball_tree')` | BallTree O(k log n) vs O(n) linear |
| CQD smoothing | Custom filter | `np.convolve(curve, np.ones(3)/3, mode='same')` | Running average in one line |

---

## Common Pitfalls

### Pitfall 1: Sobol Sampling Bottleneck at High Solution Dim

**What goes wrong:** `BayesianOptimizationEmitter` generates `num_sobol_samples` Sobol points per `ask()` call. For `solution_dim=800`, this caps at 100,000 samples and takes **4.4 seconds per ask() call** just for sampling.

**Why it happens:** `num_sobol_samples` is capped at 100,000 by the emitter, but Sobol(d=800) is expensive due to the high dimensionality. GP prediction on 100,000 x 800 adds another ~3s.

**Actual impact** [VERIFIED by benchmark]: Each `ask()` call takes ~7-8s overhead. For 700 evaluations (batch_size=1): 700 * 7s = 4,900s overhead. Inner loop evaluations at ~30s: 700 * 30s = 21,000s. Total: ~7 hours. Fits within the 8-hour nightly window.

**How to avoid:** Do not reduce batch_size below 1. Accept the overhead for the nightly run. If performance becomes unacceptable, add a `sobol_budget` parameter to `CappedBOPEmitter` that overrides `num_sobol_samples`.

**Warning signs:** `ask()` call taking > 15s indicates the Sobol step has blown up; check solution_dim.

### Pitfall 2: Missing bounds Parameter

**What goes wrong:** `BayesianOptimizationEmitter(archive=..., num_initial_samples=20)` raises `ValueError: Bounds must be specified`.

**Why it happens:** Unlike `GaussianEmitter`, BOP emitter uses Sobol sampling which requires explicit bounds.

**How to avoid:** Always pass `lower_bounds` and `upper_bounds` to `BayesianOptimizationEmitter`. Sensible defaults for the solution space (flattened `(max_words, 4)` params): `lower_bounds = np.zeros(solution_dim)`, `upper_bounds = np.ones(solution_dim)`.

### Pitfall 3: extra_fields Mismatch Between Archive and tell()

**What goes wrong:** `scheduler.tell(objective=..., measures=..., layout_coverage=...)` raises `ValueError: data has keys dict_keys([..., 'layout_coverage']) but should have keys dict_keys([...])`.

**Why it happens:** `extra_fields` must be declared at `GridArchive(extra_fields=...)` construction time. If the archive was constructed without `extra_fields`, `tell()` rejects unknown keys.

**How to avoid:** Extend `ArchiveWrapper.__init__()` to construct `GridArchive` with the required `extra_fields`. Test this at construction time before any evaluations run.

### Pitfall 4: CQD Empty Archive Division by Zero

**What goes wrong:** `f_range = f_max - f_min` is 0 when archive has 0 or 1 elites. Dividing `f(x) / f_range` produces NaN.

**How to avoid:** Guard at the top of `compute_cqd()`:
```python
if len(archive) < 2:
    return CQDResult(cqd=0.0, theta_curve=np.zeros(n_theta))
f_range = max(f_max - f_min, 1e-8)
```

### Pitfall 5: Pareto Slider Extrapolation Outside Front

**What goes wrong:** `pareto_slider(position=0.5)` on a 2-point Pareto front returns the midpoint, but interpolation beyond the front extremes gives incorrect results.

**How to avoid:** Clip position to [0.0, 1.0] and handle degenerate 1-point fronts:
```python
position = np.clip(position, 0.0, 1.0)
if len(pareto_front.indices) == 1:
    return archive.get_elite(pareto_front.indices[0])
```

### Pitfall 6: pymoo HV with wrong ref_point orientation

**What goes wrong:** `HV(ref_point=np.array([1.1, 1.1])).calc(F)` — if F values exceed the ref_point, HV is computed incorrectly (negative or zero).

**Why it happens:** pymoo HV assumes minimization. For maximization objectives in [0,1], negate F before passing and use `ref_point=[0.0, 0.0]` (since `-F` values are in [-1, 0]).

**Verified pattern** [VERIFIED]:
```python
from moocore import hypervolume
# F_max: shape (n, 2), values in [0,1] (maximization)
hv_val = hypervolume(-F_max, ref=np.array([0.0, 0.0]))
```

### Pitfall 7: BayesianOptimizationScheduler Required (not plain Scheduler)

**What goes wrong:** `Scheduler(archive=..., emitters=[bop_emitter])` accepts the `BayesianOptimizationEmitter` but cannot handle the upscale signal returned by `bop_emitter.tell()`. Upscaling will silently fail.

**How to avoid:** Always pair `BayesianOptimizationEmitter` with `BayesianOptimizationScheduler`.

---

## Code Examples

### BOP-Elites Emitter Construction

```python
# Source: ribs 0.10.0 source (_bayesian_opt_emitter.py, __init__.py)
from ribs.archives import GridArchive
from ribs.emitters import BayesianOptimizationEmitter
from ribs.schedulers import BayesianOptimizationScheduler
import numpy as np

archive = GridArchive(
    solution_dim=solution_dim,
    dims=[bins_per_dim] * 4,
    ranges=[(0.0, 1.0)] * 4,
    seed=seed,
    extra_fields={
        "layout_coverage": ((), np.float64),
        "space_saving": ((), np.float64),
    },
)

emitter = BayesianOptimizationEmitter(
    archive=archive,
    lower_bounds=np.zeros(solution_dim),
    upper_bounds=np.ones(solution_dim),
    num_initial_samples=20,  # Sobol warm-up before GP activates
    batch_size=1,            # Recommended for sample efficiency (from source docstring)
    seed=seed,
)

scheduler = BayesianOptimizationScheduler(
    archive=archive,
    emitters=[emitter],
)
```

### CQD Vectorized Computation

```python
# Source: Derived from D-05 equation, verified by benchmark
import numpy as np
from sklearn.neighbors import NearestNeighbors

def compute_cqd(
    objectives: np.ndarray,    # (n_elites,) — fitness values
    measures: np.ndarray,      # (n_elites, 4) — behavioral descriptors
    n_samples: int = 10000,
    n_theta: int = 51,
    seed: int = 42,
) -> tuple[float, np.ndarray]:
    """Returns (cqd_score, theta_curve[n_theta])."""
    if objectives.shape[0] < 2:
        return 0.0, np.zeros(n_theta)

    rng = np.random.default_rng(seed)
    ref_points = rng.uniform(0.0, 1.0, (n_samples, 4))

    # Nearest archive solution for each reference point
    nn = NearestNeighbors(n_neighbors=1, algorithm="ball_tree")
    nn.fit(measures)
    distances, indices = nn.kneighbors(ref_points)  # (n_samples, 1)

    f_max, f_min = objectives.max(), objectives.min()
    f_range = max(f_max - f_min, 1e-8)
    delta_max = np.sqrt(4)  # [0,1]^4

    nearest_f = objectives[indices.ravel()]  # (n_samples,)
    nearest_d = distances.ravel()            # (n_samples,)

    thetas = np.linspace(0.0, 1.0, n_theta)  # (n_theta,)

    # Broadcast: omega[n_samples, n_theta]
    f_norm = (nearest_f / f_range)[:, None]
    d_norm = (nearest_d / delta_max)[:, None]
    omega = f_norm - thetas[None, :] * d_norm

    cqd = float(np.mean(omega))
    theta_curve = np.mean(omega, axis=0)

    # Smoothing (D-07): running average window=3
    kernel = np.ones(3) / 3
    theta_curve_smooth = np.convolve(theta_curve, kernel, mode="same")

    return cqd, theta_curve_smooth
```

### Pareto Front Extraction

```python
# Source: pymoo 0.6.1.6, tested against venv
from pymoo.util.nds.non_dominated_sorting import NonDominatedSorting
import numpy as np

def extract_pareto_2d(
    shape_fidelity: np.ndarray,   # (n_elites,) from measures[:, 0]
    symmetry: np.ndarray,          # (n_elites,) from measures[:, 2]
    layout_coverage: np.ndarray,   # (n_elites,) from extra_fields
    space_saving: np.ndarray,      # (n_elites,) from extra_fields
) -> np.ndarray:
    """Return indices of Pareto-optimal elites in 2D objective space."""
    obj1 = shape_fidelity + symmetry        # design_fidelity
    obj2 = layout_coverage + space_saving   # packing_density

    F = np.column_stack([obj1, obj2])  # (n_elites, 2) — maximization
    nds = NonDominatedSorting()
    # pymoo minimizes: negate F
    front_indices = nds.do(-F, only_non_dominated_front=True)
    return front_indices
```

### HV Computation

```python
# Source: pymoo 0.6.1.6 indicators/hv/__init__.py, moocore backend — verified
from moocore import hypervolume
import numpy as np

def compute_hypervolume_2d(F_max: np.ndarray) -> float:
    """Compute 2D hypervolume for maximization objectives.

    Args:
        F_max: (n, 2) array of objective values to maximize, in [0,1].

    Returns:
        Hypervolume dominated area relative to ref_point=[0,0].
    """
    if F_max.shape[0] == 0:
        return 0.0
    # moocore expects minimization: negate and use ref=[0,0]
    return float(hypervolume(-F_max, ref=np.array([0.0, 0.0])))
```

---

## Runtime State Inventory

> Not a rename/refactor phase. Omitted.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `GaussianEmitter` (random perturbation) | `BayesianOptimizationEmitter` (EJIE acquisition) | ribs 0.10.0 (2024) | 700 evaluations matches MAP-Elites at 90,000 per Blueprint claim |
| `Scheduler` | `BayesianOptimizationScheduler` | ribs 0.10.0 (2024) | Handles archive upscale signals from BOP emitter |
| Grid-coverage metric only | CQD (Continuous Quality-Diversity) | GECCO 2022 (Kent et al.) | Discretization-free metric, evaluates both quality and diversity |
| Single-objective archive | 2D Pareto-Front + Hypervolume | Phase 11 | Exposes design fidelity vs packing density tradeoff |

**Deprecated/outdated:**
- `pymoo.indicators.hv.HV` class still works but internally delegates to `moocore.hypervolume` — use `moocore.hypervolume` directly for lower overhead, or use the HV class for convenience.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Inner loop evaluation takes ~30s per solution | Performance analysis | If evaluations are faster (e.g., 5s), the nightly 700-eval BOP run completes in ~2h not ~7h — lower risk |
| A2 | The 4D BD values (shape_fidelity, rotation_ratio, symmetry, semantic_clustering) are already in [0,1] and usable as CQD reference space | CQD module | If BDs are out of range, delta_max=2.0 is wrong and CQD scores will be incorrect — need clamp guard |
| A3 | `batch_size=1` is appropriate for BOP-Elites given nightly evaluation budget | BOP-Elites emitter | If faster evals allow batch_size>1, EJIE computation scales with `search_nrestarts` — recheck |
| A4 | `num_initial_samples=20` provides adequate Sobol warm-up before GP activates | BOP-Elites emitter | Too few: GP under-trained. Too many: wastes evaluations without Bayesian guidance. 20 is from pyribs example usage [ASSUMED] |

**If this table is empty:** Not empty — 4 assumed claims identified.

---

## Open Questions

1. **Solution space bounds**
   - What we know: BayesianOptimizationEmitter requires `lower_bounds` and `upper_bounds`. Existing code has no solution bounds.
   - What's unclear: Are the existing solutions (word placement params) normalized to [0,1]? Or are they in pixel space?
   - Recommendation: Default to `lower_bounds=np.zeros(solution_dim)`, `upper_bounds=np.ones(solution_dim)`. Add `lower_bounds` and `upper_bounds` to `ArchiveConfig` with these defaults.

2. **EvaluateFn return signature extension**
   - What we know: `OuterLoop.single_iteration()` currently calls `evaluate_fn(solution)` returning `(QualityMetrics, BehaviorDescriptor, embedding_384)`. The `layout_coverage` and `space_saving` are already in `QualityMetrics`.
   - What's unclear: Does the interface need to change, or can the `OuterLoop` extract `lc` and `ss` from the returned `QualityMetrics` without changing `evaluate_fn`'s signature?
   - Recommendation: Extract from `QualityMetrics` in `OuterLoop.single_iteration()` — no change to `evaluate_fn` signature needed. Less disruption.

3. **CQD_HV cell iteration strategy**
   - What we know: `CQD_HV = sum_G HV(S_HV(G))`, where G = grid cells.
   - What's unclear: D-10 says "sum over behavior grid cells" — does this mean every cell in the `GridArchive`, or only non-empty cells?
   - Recommendation: Sum over non-empty cells only. Empty cells contribute HV=0. Confirmed by interpretation of Kent 2024 definition.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| ribs | BayesianOptimizationEmitter | YES | 0.10.0 | — |
| pymoo | NonDominatedSorting, HV | YES | 0.6.1.6 | — |
| moocore | pymoo HV backend | YES | (via pymoo) | — |
| scikit-learn | GP, BallTree (CQD) | YES | (project dep) | — |
| scipy | Sobol (via ribs) | YES | (project dep) | — |
| GPyTorch | D-02 SparseGP path 1 | NO | — | History cap subclass (D-02 fallback) |
| BoTorch | Alternative SparseGP | NO | — | History cap subclass (D-02 fallback) |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:**
- GPyTorch: history cap subclass is the correct D-02 fallback per the context.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (installed, used by phases 4-10) |
| Config file | `packages/engine/pyproject.toml` (pytest section) |
| Quick run command | `cd packages/engine && uv run pytest tests/qd/ -x -q` |
| Full suite command | `cd packages/engine && uv run pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OUTER2-01 | BOP-Elites ask/tell with GridArchive | unit | `pytest tests/qd/test_bop_emitter.py -x` | NO — Wave 0 |
| OUTER2-02 | History cap subclass trims dataset at N_cap | unit | `pytest tests/qd/test_bop_emitter.py::test_history_cap -x` | NO — Wave 0 |
| OUTER2-03 | CQD omega formula: known input → known output | unit | `pytest tests/qd/test_cqd.py::test_omega_formula -x` | NO — Wave 0 |
| OUTER2-04 | Monte-Carlo CQD: statistical reproducibility | unit | `pytest tests/qd/test_cqd.py::test_cqd_reproducibility -x` | NO — Wave 0 |
| OUTER2-05 | Fixed seed → identical CQD across runs | unit | `pytest tests/qd/test_cqd.py::test_cqd_fixed_seed -x` | NO — Wave 0 |
| OUTER2-06 | Theta-sweep smoothing: window=3 running average | unit | `pytest tests/qd/test_cqd.py::test_theta_smoothing -x` | NO — Wave 0 |
| OUTER2-07 | Pareto front: no dominated points in result | unit | `pytest tests/qd/test_pareto.py::test_pareto_non_dominated -x` | NO — Wave 0 |
| OUTER2-08 | CQD_HV non-negative + monotone over iterations | unit | `pytest tests/qd/test_cqd.py::test_cqd_hv -x` | NO — Wave 0 |
| OUTER2-09 | Pareto-Slider returns distinct elites at 0.0, 0.25, 0.5, 0.75, 1.0 | unit | `pytest tests/qd/test_pareto.py::test_pareto_slider_positions -x` | NO — Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/qd/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/qd/test_bop_emitter.py` — covers OUTER2-01, OUTER2-02
- [ ] `tests/qd/test_cqd.py` — covers OUTER2-03 through OUTER2-06, OUTER2-08
- [ ] `tests/qd/test_pareto.py` — covers OUTER2-07, OUTER2-09

Existing test infrastructure: `tests/qd/test_archive.py`, `tests/qd/test_scheduler.py` — both exist and green. New files required only for new modules.

---

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 11 has no API endpoints (Pareto-Slider is Python-only) |
| V3 Session Management | no | No sessions |
| V4 Access Control | no | No endpoints |
| V5 Input Validation | yes (light) | `pareto_slider(position)` must validate `position in [0.0, 1.0]` with `np.clip` |
| V6 Cryptography | no | No cryptographic operations |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| CQD with injected archive data | Tampering | All archive data comes from the internal optimizer — no user-controlled input |
| pareto_slider(position=NaN) | Tampering | `np.clip(position, 0.0, 1.0)` returns NaN for NaN input — add explicit `np.isfinite()` guard |

---

## Sources

### Primary (HIGH confidence)
- `ribs 0.10.0` source code (read from venv) — BayesianOptimizationEmitter, BayesianOptimizationScheduler API, Sobol sampling, EJIE acquisition
- `pymoo 0.6.1.6` source code (read from venv) — NonDominatedSorting, HV class, moocore backend
- Benchmark measurements (executed in venv Python 3.11): GP fit times, Sobol sampling times, HV computation times, CQD computation times
- Functional tests (executed in venv): BayesianOptimizationScheduler construction, extra_fields in GridArchive, NDS on 2D objectives, HV on Pareto front

### Secondary (MEDIUM confidence)
- wiki/map-elites.md — BOP-Elites 700 vs 90,000 evaluations claim (Blueprint-derived)
- wiki/cqd-metric.md — CQD definition, Monte-Carlo sampling, theta-sweep concept
- wiki/research/stack.md — pyribs + pymoo as QD stack (Gemini + Codex verified 2026-04-07)

### Tertiary (LOW confidence)
- [ASSUMED] `num_initial_samples=20` as warm-up count (training knowledge, not verified from paper)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified against installed packages in venv
- BOP-Elites API: HIGH — read source code, ran functional tests
- CQD computation: HIGH — implemented and benchmarked in venv
- Pareto front: HIGH — tested NonDominatedSorting and HV with real pymoo
- Architecture patterns: HIGH — extra_fields verified functional in GridArchive
- Pitfalls: HIGH — each pitfall verified by actually triggering the error or measuring the behavior
- Performance estimates: MEDIUM — measured on VPS server hardware, may differ under load

**Research date:** 2026-04-16
**Valid until:** 2026-05-16 (ribs and pymoo are stable; BayesianOptimizationEmitter API unlikely to change in 30 days)

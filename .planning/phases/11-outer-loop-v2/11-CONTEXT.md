# Phase 11: Outer Loop-v2 - Context

**Gathered:** 2026-04-21 (assumptions mode)
**Status:** Ready for planning

<domain>
## Phase Boundary

BOP-Elites + CQD metric + Pareto-Front + Pareto-Slider. Upgrades the Phase 9 MAP-Elites with Bayesian Optimization emitter, adds the CQD quality-diversity metric with theta-sweep, computes Pareto-Front with hypervolume, and exposes a Pareto-Slider function for the design fidelity vs packing density tradeoff.

Requirements: OUTER2-01 to OUTER2-09.

</domain>

<decisions>
## Implementation Decisions

### BOP-Elites Emitter
- **D-01:** Replace GaussianEmitter with custom wrapper around pyribs `BayesianOptimizationEmitter` (EJIE). Keep existing ArchiveWrapper ask/tell interface intact.
- **D-02:** Sparse GP for scaling (OUTER2-02): if pyribs supports custom model injection, use GPyTorch SparseGP with inducing points. If not, subclass BayesianOptimizationEmitter to swap the internal GP. Fallback: batched GP with capped history window.
- **D-03:** BOP-Elites must work with existing GridArchive. If incompatible, adapt via compatibility shim (not archive replacement).

### CQD Metric
- **D-04:** New module `outer_loop/cqd.py` — archive-level metric, NOT per-solution. Operates on ArchiveWrapper.data() arrays.
- **D-05:** CQD equation: `omega(x, G, theta) = f(x)/|f_max - f_min| - theta * delta(g(x), G)/delta_max`
- **D-06:** Monte-Carlo CQD: `CQD = (1/NM) * sum_n sum_m omega(x^r, G_n, theta_m)` with n_samples=10000 reference points, fixed seeds per OUTER2-05.
- **D-07:** Theta-sweep: 51 evenly-spaced theta values in [0.0, 1.0]. Smoothing via running average with window=3.
- **D-08:** CQD computed once per outer loop batch (not per evaluation). Returns CQD score + theta-sweep curve.

### Pareto-Front & Hypervolume
- **D-09:** Use pymoo (already in deps) for Pareto-Front extraction (`pymoo.util.nds.non_dominated_sort`) and hypervolume (`pymoo.indicators.hv.HV`).
- **D-10:** CQD_HV = sum over behavior grid cells of hypervolume of the HV set. Reference point: [0, 0] (worst case for all objectives).
- **D-11:** Pareto-Front objectives: design fidelity (shape_fidelity + symmetry) vs packing density (layout_coverage + space_saving). 2D Pareto front from the 4D behavioral descriptor space.

### Pareto-Slider
- **D-12:** Python-level function `pareto_slider(position: float) -> MapElitesEntry` where position in [0.0, 1.0]. 0.0 = max design fidelity, 1.0 = max packing density.
- **D-13:** Returns the elite closest to the interpolated point on the Pareto front. NO FastAPI route — HTTP endpoint deferred to Phase 12.
- **D-14:** Success criterion SC4: slider returns layouts at positions 0.0, 0.25, 0.5, 0.75, 1.0.

### Claude's Discretion
- Sparse GP inducing point count
- CQD reference point sampling strategy (uniform random in [0,1]^4)
- Hypervolume reference point value
- Theta-sweep smoothing window size

</decisions>

<canonical_refs>
## Canonical References

### CQD & Quality-Diversity
- `wiki/cqd-metric.md` — CQD score equation, theta-sweep, hypervolume
- `wiki/map-elites.md` — MAP-Elites, BOP-Elites, behavioral descriptors
- `wiki/quality-metrics.md` — Geometric and semantic quality metrics

### Existing Outer Loop
- `packages/engine/src/aerocloud/outer_loop/archive.py` — ArchiveWrapper (GridArchive + emitter + Scheduler)
- `packages/engine/src/aerocloud/outer_loop/emitter.py` — NoveltyGaussianEmitter
- `packages/engine/src/aerocloud/outer_loop/scheduler.py` — OuterLoop orchestrator
- `packages/engine/src/aerocloud/outer_loop/metrics.py` — 7 quality metrics + compute_all_metrics
- `packages/engine/src/aerocloud/outer_loop/models.py` — QualityMetrics, ArchiveConfig, BehaviorDescriptor

### Dependencies
- `packages/engine/pyproject.toml` — ribs>=0.10.0, pymoo>=0.6.1 already declared

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- ArchiveWrapper.data() returns {solution, objective, measures} numpy arrays — CQD input
- QualityMetrics model with combined_fitness() — fitness normalization for CQD
- pymoo already in deps — HV + non_dominated_sort ready
- set_seed() determinism — for CQD Monte-Carlo fixed seeds

### Integration Points
- BOP-Elites emitter replaces GaussianEmitter in ArchiveWrapper
- CQD computed from archive data after OuterLoop.run()
- Pareto-Front extracted from archive behavioral descriptors
- Pareto-Slider queries the Pareto front

</code_context>

<deferred>
## Deferred Ideas

- FastAPI route for Pareto-Slider — Phase 12
- GPU-accelerated hypervolume computation — Phase 12 if needed
- Interactive Pareto exploration UI — out of scope

</deferred>

---

*Phase: 11-outer-loop-v2*
*Context gathered: 2026-04-21*

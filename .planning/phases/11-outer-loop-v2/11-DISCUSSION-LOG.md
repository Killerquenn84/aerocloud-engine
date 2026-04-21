# Phase 11: Outer Loop-v2 - Discussion Log (Assumptions Mode)

> Audit trail only. Decisions in CONTEXT.md.

**Date:** 2026-04-21
**Phase:** 11-outer-loop-v2
**Mode:** assumptions (--auto)

## Auto-Resolved
- BOP-Elites (Likely → wrapper around BayesianOptimizationEmitter, keep GridArchive)
- Sparse GP (Unclear → GPyTorch SparseGP if injectable, else batched GP with history cap)
- Pareto-Front (Likely → pymoo HV + non_dominated_sort)
- Pareto-Slider (Likely → Python function, no HTTP route until Phase 12)

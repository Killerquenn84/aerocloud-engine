# wiki/code/self-play-reviewer.md — AdversarialReviewer

**Phase:** 10-self-play
**Module:** `packages/engine/src/aerocloud/self_play/reviewer.py`
**Implements:** AdversarialReviewer — rule-based heuristic to detect reward hacking in Self-Play candidates (D-10, D-11, D-12).

---

## Overview

`AdversarialReviewer` applies 4 rejection rules in priority order to each Self-Play candidate. It is rule-based (NOT a trained ML model), deterministic, and interpretable. The reviewer is instantiated once per `SelfPlayLoop.__init__` with archive statistics, then called once per `single_iteration`.

**Success criterion (D-12):** Rejection rate > 5% across a nightly run (verified in integration tests with 33% degenerate inputs).

---

## Constants

```python
_METRIC_FIELDS: list[str] = [
    "layout_coverage", "layout_uniformity", "space_saving",
    "compactness", "aspect_ratio", "realized_adjacencies", "distortion_score",
]

_DEGENERATE_LC_THRESHOLD: float = 0.1   # Rule 3: strict < 0.1
_OOD_ZSCORE_THRESHOLD: float = 3.0      # Rule 2: |z| > 3.0
_GAMING_SHARE_THRESHOLD: float = 0.5    # Rule 4: > 50% of combined fitness
_REWARD_HACK_MIN_DECREASES: int = 2     # Rule 1: >= 2 metrics must decrease
```

---

## Class: AdversarialReviewer

```python
class AdversarialReviewer:
    def __init__(
        self,
        archive_solutions: np.ndarray,   # shape (n_elites, solution_dim)
        weights: QualityWeights,
    ) -> None
```

**At construction:**
- Computes `archive_mean = np.mean(archive_solutions, axis=0)`
- Computes `archive_std = np.std(archive_solutions, axis=0) + 1e-8` (population std, epsilon prevents divide-by-zero on zero-variance dimensions)

---

## Method: review

```python
def review(
    self,
    solution: np.ndarray,               # flat (solution_dim,)
    metrics_new: QualityMetrics,        # candidate metrics
    metrics_baseline: QualityMetrics | None,  # None → skip Rule 1
) -> tuple[bool, str]:
```

**Returns:** `(True, "")` if all rules pass; `(False, reason_string)` on first violation.

---

## Rule Priority Order

Rules are evaluated cheapest/most-critical first. First violation wins.

### Rule 3 — Degenerate Layout (O(1), most common failure)

```python
if metrics_new.layout_coverage < _DEGENERATE_LC_THRESHOLD:
    return (False, "degenerate_layout: layout_coverage < 0.1")
```

Catches empty/collapsed layouts before any expensive checks.

### Rule 2 — OOD Parameters (O(solution_dim), vectorized)

```python
z_scores = np.abs((solution - self._archive_mean) / self._archive_std)
if float(np.max(z_scores)) > _OOD_ZSCORE_THRESHOLD:
    return (False, "ood_parameters: z_score > 3.0")
```

Catches solutions numerically implausible relative to archive distribution (e.g., extreme positions, unrealistically large words).

### Rule 4 — Single-Metric Gaming (O(1), structural check)

```python
combined = metrics_new.combined_fitness(self._weights)
if combined > 0.0:
    ar_contribution = self._weights.w_ar * metrics_new.aspect_ratio
    ar_share = ar_contribution / combined
    if ar_share > _GAMING_SHARE_THRESHOLD:
        return (False, "gaming_aspect_ratio: single metric > 50% of total fitness")
```

Detects aspect_ratio gaming (solution optimized only for AR, ignoring all other metrics). Division guarded by `combined > 0.0` check.

### Rule 1 — Reward Hacking (O(n_metrics), requires baseline)

Skipped when `metrics_baseline is None` (first night or baseline not found).

```python
combined_new > combined_baseline   # only if this is True:
n_decreased = count(val_new < val_old for each field in _METRIC_FIELDS)
if n_decreased >= 2:
    return (False, "reward_hacking: N metrics decreased while combined increased")
```

Detects solutions that increase combined fitness by inflating one metric while sacrificing two or more others.

---

## Test Arithmetic Notes

For reward_hacking tests to fire correctly, `combined_new > combined_baseline` must be true. With 7 equal weights (1/7 each), 4 metrics at 1.0 and 3 at 0.1 gives `combined_new ≈ 0.614 > 0.5`. All test values in `test_reviewer.py` are documented with inline arithmetic comments.

Borderline degenerate test: `layout_coverage = 0.1` is NOT degenerate (threshold is strict `< 0.1`, not `<= 0.1`).

---

## Design Decisions

| Decision | Detail |
|----------|--------|
| D-10 | Rule-based heuristics only; no ML model; deterministic, interpretable |
| D-11 | Returns `(bool, str)` — empty string on acceptance |
| D-12 | > 5% rejection rate is success criterion (integration-tested) |

---

## Tests

`test_reviewer.py`: 9 unit tests covering:
- Accept case (all rules pass)
- Degenerate layout rejection (Rule 3)
- OOD parameters rejection (Rule 2)
- Gaming aspect ratio rejection (Rule 4)
- Reward hacking rejection (Rule 1)
- Baseline=None skips Rule 1
- Rule priority order
- Borderline LC (= 0.1, not degenerate)
- Exact-2 metric decrease triggers Rule 1

---

*Module: packages/engine/src/aerocloud/self_play/reviewer.py*
*Phase: 10-self-play*
*Updated: 2026-04-21*

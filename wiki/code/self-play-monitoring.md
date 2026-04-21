# wiki/code/self-play-monitoring.md — Distribution-Shift Monitoring

**Phase:** 10-self-play
**Module:** `packages/engine/src/aerocloud/self_play/monitoring.py`
**Implements:** compute_kl_divergence (4 marginal 1D histograms), check_distribution_shift (SP-07, D-13, D-14).

---

## Overview

Nightly distribution-shift monitoring compares the behavioral descriptor (BD) distribution of the current Self-Play run against the previous night's distribution. Uses KL divergence computed over 4 independent 1D marginal histograms (one per BD dimension).

**Critical research correction:** 4 marginal 1D histograms, NOT joint 4D `histogramdd`. Joint 4D on identical uniform distributions gives KL ≈ 11.5 (false alarm). Marginal 1D correctly gives KL ≈ 0.0.

---

## Constants

```python
_EPS: float = 1e-8  # smoothing to prevent log(0)
```

---

## compute_kl_divergence

```python
def compute_kl_divergence(
    descriptors_prev: np.ndarray,    # shape (n, 4) — previous night
    descriptors_curr: np.ndarray,    # shape (m, 4) — current night
    n_bins: int = 10,
) -> float:
```

**Algorithm (per dimension, 4 times):**
1. Extract 1D marginal: `prev_dim = descriptors_prev[:, dim]`
2. `np.histogram(prev_dim, bins=n_bins, range=(0.0, 1.0))` → `hist_prev`
3. `np.histogram(curr_dim, bins=n_bins, range=(0.0, 1.0))` → `hist_curr`
4. Add `_EPS` smoothing: `p = hist_prev.astype(float64) + EPS`
5. Normalize: `p /= p.sum()`, `q /= q.sum()`
6. `kl_dim = scipy.special.rel_entr(p, q).sum()` (numerically stable)

**Return:** Sum of 4 per-dimension KL values as Python `float`.

**Range fixed at [0.0, 1.0]:** BD dimensions are designed to be normalized; values outside this range are clipped into edge bins.

**Why marginal, not joint:**
- Joint 4D histogramdd with 10 bins = 10^4 = 10,000 cells
- For typical archive sizes (< 1,000 elites), most cells are empty → KL dominated by empty-bin comparisons → artificially high KL
- Marginal 1D: 10 cells each, well-populated, gives stable KL estimate

**Typical values:**
- No drift (identical distributions): KL ≈ 0.0
- Mild drift: KL ≈ 0.1–0.4
- Severe collapse (all BDs at same value): KL > 0.5

---

## check_distribution_shift

```python
def check_distribution_shift(
    kl_value: float,
    threshold: float = 0.5,     # default per SelfPlayConfig.kl_threshold
) -> bool:
```

Returns `True` if `kl_value > threshold` (shift detected).

Logs `self_play.monitoring.distribution_shift_detected` via structlog when alert fires (T-10-09 repudiation mitigation).

**Usage in SelfPlayLoop:**
```python
kl = compute_kl_divergence(prev_histogram, current_measures, n_bins=config.kl_n_bins)
shift = check_distribution_shift(kl, threshold=config.kl_threshold)
```

---

## Design Decisions

| Decision | Detail |
|----------|--------|
| D-13 | 4D behavioral descriptor distribution tracked per nightly run |
| D-14 | Alert threshold: KL > 0.5 → structlog warning + Telegram (Telegram wiring in Phase 12) |
| Research correction | Marginal 1D histograms, NOT joint 4D histogramdd |

---

## Tests

`test_monitoring.py`: 9 unit tests covering:
- Identical distributions → KL ≈ 0.0
- No-drift case → KL < 0.1
- Severe collapse → KL > 0.5
- Output is Python float
- Single-dimension collapse still detected
- Shift detected (True) and not detected (False)
- Marginal-not-joint verification

---

*Module: packages/engine/src/aerocloud/self_play/monitoring.py*
*Phase: 10-self-play*
*Updated: 2026-04-21*

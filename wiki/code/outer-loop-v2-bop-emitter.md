# CappedBOPEmitter — BOP-Elites Emitter with GP History Capping

**Module:** `packages/engine/src/aerocloud/outer_loop/bop_emitter.py`
**Phase:** 11-outer-loop-v2 (Plan 11-01)
**Requirements:** OUTER2-01, OUTER2-02

---

## Purpose

Replaces the Phase 9 `GaussianEmitter` with a Bayesian Optimization Emitter (BOP-Elites EJIE algorithm via pyribs `BayesianOptimizationEmitter`). Prevents O(n^3) GP matrix inversion blowup by trimming the internal training history to the last `history_cap` entries before each GP fit.

---

## Why GPyTorch Fallback (D-02)

GPyTorch was not installed in the venv at Phase 11 build time. Without GPyTorch's sparse GP implementation, pyribs uses a dense sklearn GP that scales as O(n^3) in training set size. Without capping:
- 700 evaluations (BOP-Elites paper target) × O(n^3) → ~24s per GP fit at eval 700
- With `history_cap=200` → sklearn GP fit stays under 0.02s at all times (RESEARCH.md benchmark)

GPyTorch sparse GP with inducing points would be the preferred solution when available. See D-02 in `wiki/knowledge/phase-11-decisions.md` for full decision rationale.

---

## Class: CappedBOPEmitter

```python
class CappedBOPEmitter(BayesianOptimizationEmitter):
    def __init__(self, *args: object, history_cap: int = 200, **kwargs: object) -> None
```

**Inherits from:** `ribs.emitters.BayesianOptimizationEmitter`

**Constructor parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `*args` | positional | — | Forwarded to parent (archive, lower_bounds, upper_bounds, num_initial_samples, batch_size) |
| `history_cap` | int | 200 | Max GP training set size. Must be >= 10 (T-11-02 DoS mitigation) |
| `**kwargs` | keyword | — | Forwarded to parent (seed, etc.) |

**Raises:** `ValueError` if `history_cap < 10`

---

## Method: _trim_dataset()

```python
def _trim_dataset(self) -> None
```

Trims `BayesianOptimizationEmitter._dataset` dict to at most `history_cap` most recent rows.

**Algorithm:**
1. Check `hasattr(self, "_dataset")` — failure-open guard if pyribs renames the attribute
2. Check `len(dataset["solution"]) <= history_cap` — skip if already within cap
3. For each key in `("solution", "objective", "measures")`: assign `arr[-history_cap:]`
4. Log before/after row counts at DEBUG level

**FIFO drop:** Oldest entries are dropped first. GP always trains on the most recent evaluations.

**Key risk:** Only known pyribs 0.10.0 keys are trimmed. If a future pyribs version adds keys to `_dataset`, those would grow unbounded. Mitigated by `ribs>=0.10.0` version pin.

---

## Method: tell()

```python
def tell(
    self,
    solution: np.ndarray,
    objective: np.ndarray,
    measures: np.ndarray,
    **kwargs: object,
) -> None
```

1. Calls `super().tell()` — appends to `_dataset` and triggers GP refit
2. Calls `_trim_dataset()` — trims `_dataset` to `history_cap` rows

**Order matters:** Trim AFTER super().tell() so each batch is included before dropping oldest entries.

---

## Performance

| Config | GP fit time | Source |
|--------|-------------|--------|
| history_cap=200, sklearn dense GP | < 0.02s | RESEARCH.md benchmark |
| 700 evaluations uncapped | ~24s | Extrapolated O(n^3) |
| Sobol initial phase (num_initial_samples=20) | ~0.6s | Plan 11-04 SC7 test |

**Sobol overhead at d=800 (solution_dim=800):** ~4s per `ask()` on first call (Sobol sequence generation). Acceptable for nightly batch. Subsequent `ask()` calls (GP acquisition) are sub-second.

---

## Usage

```python
from aerocloud.outer_loop import ArchiveConfig, ArchiveWrapper

config = ArchiveConfig(
    solution_dim=40,          # max_words=10 x 4
    emitter_type="bop",
    num_initial_samples=20,   # Sobol phase before GP
    history_cap=200,          # GP training set cap
    lower_bounds=np.zeros(40),
    upper_bounds=np.ones(40),
)
archive = ArchiveWrapper(config, seed=42)
# BOP emitter is selected automatically
solutions = archive.ask()
archive.tell(objectives, measures, layout_coverage, space_saving)
```

---

## Integration with ArchiveWrapper

`ArchiveWrapper._build_bop_scheduler()` constructs `CappedBOPEmitter` and wraps it in `BayesianOptimizationScheduler`. The emitter selection is controlled by `ArchiveConfig.emitter_type: Literal["gaussian", "bop"]`.

GridArchive always includes `extra_fields={'layout_coverage': ..., 'space_saving': ...}` regardless of emitter type — enabling Pareto-Slider for both emitter types (D-03).

---

## Threat Coverage

| Threat | Mitigation |
|--------|------------|
| T-11-02 (DoS via history_cap=0) | `history_cap >= 10` validated in constructor AND in ArchiveConfig.ge constraint |

---

## References

- Plan: `.planning/phases/11-outer-loop-v2/11-01-PLAN.md`
- Decisions: `wiki/knowledge/phase-11-decisions.md` (D-01, D-02, D-03)
- Tests: `packages/engine/tests/qd/test_bop_emitter.py` (14 tests)
- pyribs API: `ribs.emitters.BayesianOptimizationEmitter`

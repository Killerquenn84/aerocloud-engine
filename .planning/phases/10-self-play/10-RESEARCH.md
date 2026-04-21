# Phase 10: Self-Play - Research

**Researched:** 2026-04-16
**Domain:** Celery Beat scheduling, MAP-Elites self-play mutation, KL divergence monitoring, Alembic replay tables
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Scheduling Infrastructure**
- D-01: Celery Beat nightly job using existing `celery[redis]>=5.4.0` from apps/worker. Queue: `background`. Pool: `solo` (CUDA fork safety).
- D-02: Task: `self_play_nightly(n_iterations=1000, soft_time_limit=28800)`. Calls OuterLoop.run() with self-play mutation operators.
- D-03: Graceful exit: on SIGTERM or soft_time_limit, finish current iteration, flush archive, write replay log summary, exit 0.

**Mutation & Crossover Operators**
- D-04: Gaussian perturbation on flat `(max_words * 4)` solution arrays (reuse existing sigma from ArchiveConfig).
- D-05: Crossover: uniform crossover on two parent solutions sampled via Monte-Carlo from archive. Per-parameter probability p=0.5 of taking from parent A vs B.
- D-06: Structure-aware mutation: reshape to (N,4), apply different sigma per column (position sigma_xy, scale sigma_s, rotation sigma_theta). Configurable via `SelfPlayConfig`.

**Frozen Baseline & Stricter Dominance**
- D-07: Frozen baseline = snapshot of archive at start of nightly run via ArchivePersistence.load_all(). Stored in memory, not a separate table.
- D-08: Stricter dominance: mutated solution must exceed baseline fitness by `dominance_margin` (default 0.01). `fitness_new > fitness_baseline + dominance_margin`.
- D-09: SP-04 evaluation: compare quality metrics of mutated solution against frozen baseline for the same bin_id.

**Adversarial Reviewer**
- D-10: Rule-based heuristic, NOT trained ML model. Flags reward-hacking patterns:
  - combined_fitness increases but >= 2 individual metrics decrease
  - any parameter value exceeds 3 std devs from archive mean
  - layout_coverage < 0.1 (degenerate empty layout)
  - aspect_ratio metric contributes > 50% of total fitness (gaming one metric)
- D-11: Reviewer returns `(accepted: bool, reason: str)`. Rejected mutations logged but not added to archive.
- D-12: Success criterion: > 5% rejection rate across a nightly run.

**Distribution-Shift Monitoring**
- D-13: Track 4D behavioral descriptor distribution per nightly run. Compare consecutive nights via KL divergence on discretized histograms.
- D-14: Alert threshold: KL divergence > 0.5 between consecutive nights. Log warning via structlog + Telegram notification.

**Replay Log**
- D-15: New Alembic migration for `self_play_runs` table: `(run_id UUID PK, started_at TIMESTAMPTZ, ended_at TIMESTAMPTZ, n_iterations INT, n_accepted INT, n_rejected INT, kl_divergence REAL, config JSONB)`.
- D-16: New `self_play_events` table: `(event_id BIGSERIAL PK, run_id UUID FK, iteration INT, parent_bin_ids TEXT[], mutation_type TEXT, fitness_before REAL, fitness_after REAL, accepted BOOL, reject_reason TEXT)`.
- D-17: Replay log enables full reconstruction of each Self-Play run per success criterion 4.

### Claude's Discretion
- Exact histogram bin count for KL divergence
- Celery Beat schedule cron expression (default: 0 2 * * * Berlin time)
- Crossover parent selection strategy (uniform random vs fitness-proportional)
- Replay log retention policy

### Deferred Ideas (OUT OF SCOPE)
- Trained adversarial reviewer model (discriminator network) — Phase 12+ if rule-based proves insufficient
- Multi-GPU parallel Self-Play workers — Phase 12 scaling
- Warm-start Self-Play from prior night's best solutions — consider for v2
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SP-01 | Celery Beat scheduled nightly job in `queue='background'` | D-01/D-02: Celery 5.6.3 installed; crontab + soft_time_limit verified working |
| SP-02 | Monte-Carlo sampling from current archive | D-05: uniform random sampling from ArchiveWrapper.data()["solution"] verified |
| SP-03 | Mutation operators (parameter perturbation, crossover) | D-04/D-05/D-06: Gaussian + uniform crossover math verified; structure-aware reshape pattern confirmed |
| SP-04 | Evaluation against frozen baseline metrics | D-07/D-08/D-09: ArchivePersistence.load_all() returns (bin_id, fitness, measures, solution_flat); dominance check verified |
| SP-05 | Archive update with stricter dominance check | D-08: strict greater-than comparison `fitness_new > fitness_baseline + dominance_margin`; tie at margin = rejected |
| SP-06 | Adversarial reviewer model penalizing reward hacking | D-10/D-11: All 4 rule predicates verified mathematically; rule 1 triggers correctly |
| SP-07 | Distribution-shift monitoring across consecutive nights | D-13/D-14: marginal KL divergence approach validated; threshold 0.5 verified discriminates collapse from noise |
| SP-08 | Replay log for every Self-Play run | D-15/D-16: Alembic migration pattern established from migrations 0001-0003; asyncpg UUID support confirmed |
</phase_requirements>

---

## Summary

Phase 10 implements nightly Self-Play training that wraps the existing OuterLoop (Phase 9) with a new mutation layer, adversarial reviewer, distribution-shift monitor, and full replay logging. All major dependencies (Celery 5.6.3, pyribs 0.10.0, asyncpg 0.31.0, scipy 1.17.1, alembic 1.18.4) are already installed and verified. The worker package (`apps/worker`) currently contains only a stub `__init__.py` — the full Celery app definition, beat schedule, and task implementation are new work for this phase.

The key architectural pattern is: `CeleryBeat → self_play_nightly task (solo pool) → SelfPlayLoop (wraps OuterLoop) → MutationOperator + AdversarialReviewer + ReplayLogger`. The SelfPlayLoop is a new class that injects self-play mutation operators into the existing OuterLoop ask/evaluate/tell cycle. The frozen baseline is loaded once at task start via `ArchivePersistence.load_all()` and held in memory.

The most important implementation subtlety is the KL divergence computation: a naive 4D joint histogram with 10^4 bins and only ~1000 samples per night produces ~90% empty bins, making KL divergence numerically unstable. The correct approach is 4 independent 1D marginal histograms (one per descriptor dimension), summed. Verified: no-drift condition produces KL sum ~0.007 (well below 0.5); severe collapse produces ~67 (far above). The threshold of 0.5 is a clean discriminator.

**Primary recommendation:** Build `SelfPlayLoop` as a thin wrapper around `OuterLoop` that overrides the `ask()` step with mutation/crossover operators, applies the adversarial reviewer before `tell()`, and feeds the replay logger. Reuse all existing Phase 9 components without modification.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| celery[redis] | 5.6.3 | Task scheduling + Beat | Already installed [VERIFIED: uv run] |
| pyribs | 0.10.0 | MAP-Elites archive (ArchiveWrapper) | Already installed, Phase 9 [VERIFIED: uv run] |
| numpy | 2.4.4 | Array math for mutation/crossover | Already installed [VERIFIED: uv run] |
| scipy | 1.17.1 | KL divergence via `scipy.special.rel_entr` | Already installed [VERIFIED: uv run] |
| asyncpg | 0.31.0 | PostgreSQL replay table writes | Already installed, Phase 9 pattern [VERIFIED: uv run] |
| alembic | 1.18.4 | Migration for self_play_runs/events tables | Already installed [VERIFIED: uv run] |
| structlog | 25.5.0 | Replay event logging | Already installed throughout codebase [VERIFIED: uv run] |
| pydantic | 2.12.5 | SelfPlayConfig, SelfPlayRunResult models | Already installed, project-wide standard [VERIFIED: uv run] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `celery.exceptions.SoftTimeLimitExceeded` | 5.6.3 | Catch soft timeout in task body | Task's try/except block for graceful exit |
| `celery.schedules.crontab` | 5.6.3 | Define nightly cron expression | Beat schedule config |
| `scipy.stats.entropy` | 1.17.1 | Alternative KL divergence (equivalent to rel_entr) | Interchangeable with rel_entr |
| `uuid.uuid4()` | stdlib | Generate run_id for replay tables | asyncpg supports UUID natively [VERIFIED] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Marginal 1D KL (4 histograms) | Joint 4D histogram | Joint has 10^4 bins vs ~1000 samples — 90% empty bins, numerically unstable [VERIFIED] |
| Rule-based reviewer | ML discriminator | ML deferred to Phase 12+; rule-based is faster, auditable, requires no training data [LOCKED D-10] |
| uniform crossover p=0.5 | fitness-proportional sampling | Uniform is simpler; fitness-proportional could bias toward high-fitness parents (discretion item) |

**Installation:** All packages already installed. No new dependencies required.
[VERIFIED: uv run python -c "import celery, ribs, numpy, scipy, asyncpg, alembic, structlog, pydantic"]

---

## Architecture Patterns

### Recommended Project Structure

```
apps/worker/src/aerocloud_worker/
├── celery_app.py        # Celery app + beat_schedule + timezone config
├── tasks/
│   └── self_play.py     # @app.task self_play_nightly()
└── __init__.py          # existing stub (unchanged)

packages/engine/src/aerocloud/self_play/
├── __init__.py
├── config.py            # SelfPlayConfig (Pydantic)
├── loop.py              # SelfPlayLoop wraps OuterLoop
├── mutation.py          # GaussianMutator, UniformCrossover (structure-aware)
├── reviewer.py          # AdversarialReviewer (rule-based)
├── monitoring.py        # KL divergence distribution-shift monitor
├── replay.py            # ReplayLogger asyncpg writes
└── models.py            # SelfPlayRunResult, SelfPlayEvent

packages/engine/tests/self_play/
├── __init__.py
├── conftest.py
├── unit/
│   ├── test_config.py
│   ├── test_mutation.py
│   ├── test_reviewer.py
│   ├── test_monitoring.py
│   └── test_replay.py
├── integration/
│   └── test_self_play_loop.py
└── determinism/
    └── test_determinism.py

infra/alembic/versions/
└── 0004_self_play_replay_tables.py
```

### Pattern 1: Celery Beat Task with Graceful Soft-Timeout Exit

**What:** A long-running task (8h = 28800s) registered with `soft_time_limit`. On timeout, `SoftTimeLimitExceeded` is raised in the task body, allowing a try/except to flush archive state and write a replay summary before exiting.

**When to use:** Any nightly batch job needing clean exit on timeout.

```python
# Source: Celery 5.6.3 documentation + verified locally
from celery.exceptions import SoftTimeLimitExceeded
from aerocloud_worker.celery_app import app

@app.task(
    bind=True,
    name="aerocloud_worker.tasks.self_play.self_play_nightly",
    queue="background",
    soft_time_limit=28800,   # 8 hours — raises SoftTimeLimitExceeded
    time_limit=28900,        # hard kill 100s later (safety net)
    max_retries=0,           # nightly job, no retries
)
def self_play_nightly(self, n_iterations: int = 1000) -> dict:
    loop = SelfPlayLoop.build_from_env()
    try:
        result = loop.run(n_iterations)
    except SoftTimeLimitExceeded:
        result = loop.flush_and_finalize(reason="soft_timeout")
    return result.model_dump()
```

**Key points:**
- `soft_time_limit=28800` raises `SoftTimeLimitExceeded` in the task body (catchable) [VERIFIED: hasattr(Task, 'soft_time_limit')]
- `time_limit=28900` sends SIGKILL 100s later if task doesn't exit (uncatchable safety net)
- The exception is actually `billiard.exceptions.SoftTimeLimitExceeded` (imported from `celery.exceptions`) [VERIFIED]
- `max_retries=0` prevents accidental re-queuing of an 8-hour job
- `--pool=solo` is set at worker startup, not in the task decorator

### Pattern 2: Celery Beat Schedule with Berlin Timezone

**What:** Beat schedule using `crontab(hour=2, minute=0)` with `app.conf.timezone = 'Europe/Berlin'` so the cron expression is interpreted in Berlin local time (handles CEST/CET DST automatically).

```python
# Source: Celery 5.6.3 — app.conf.timezone config verified locally
from celery.schedules import crontab

app.conf.timezone = "Europe/Berlin"
app.conf.enable_utc = True

app.conf.beat_schedule = {
    "self-play-nightly": {
        "task": "aerocloud_worker.tasks.self_play.self_play_nightly",
        "schedule": crontab(hour=2, minute=0),   # 02:00 Berlin time
        "options": {"queue": "background"},
    }
}
```

**Key points:**
- `enable_utc = True` + `timezone = 'Europe/Berlin'` = crontab interpreted in local time, stored in UTC [VERIFIED]
- `options={"queue": "background"}` routes the beat-triggered task to the background queue
- Worker startup command: `celery -A aerocloud_worker.celery_app worker --pool=solo --queues=background`

### Pattern 3: Structure-Aware Mutation (D-06)

**What:** Reshape flat solution array to (max_words, 4) and apply different sigma per column. Columns are (y, x, scale, rotation).

```python
# Source: verified locally — numpy reshape + broadcast multiplication
import numpy as np

def structure_aware_mutate(
    solution: np.ndarray,   # shape: (max_words * 4,)
    config: SelfPlayConfig,
    rng: np.random.Generator,
) -> np.ndarray:
    max_words = len(solution) // 4
    params = solution.reshape(max_words, 4)   # (N, 4): [y, x, scale, theta]
    
    sigma_per_col = np.array([
        config.sigma_xy,     # y
        config.sigma_xy,     # x
        config.sigma_scale,  # scale
        config.sigma_theta,  # rotation
    ])
    noise = rng.standard_normal((max_words, 4)) * sigma_per_col
    mutated = params + noise
    return mutated.flatten()
```

**Key points:**
- `sigma_per_col` broadcasts across all words — one noise draw per word
- Default values: `sigma_xy=0.05, sigma_scale=0.02, sigma_theta=0.1` (discretion — tune in testing)
- No clamping needed here; archive bounds clamping happens at `tell()` time in ArchiveWrapper

### Pattern 4: Uniform Crossover (D-05)

**What:** Per-element coin flip between two parent solutions sampled uniformly from archive.

```python
# Source: verified locally
def uniform_crossover(
    parent_a: np.ndarray,
    parent_b: np.ndarray,
    rng: np.random.Generator,
    p: float = 0.5,
) -> np.ndarray:
    mask = rng.random(len(parent_a)) < p
    return np.where(mask, parent_a, parent_b)
```

**Monte-Carlo parent sampling from archive:**

```python
# Source: verified against ArchiveWrapper.data() return schema
archive_data = archive.data()
solutions = archive_data["solution"]          # (n_elites, solution_dim)
n_elites = solutions.shape[0]
# Uniform random parent selection (Claude's discretion)
idx_a, idx_b = rng.integers(0, n_elites, size=2)
parent_a = solutions[idx_a]
parent_b = solutions[idx_b]
```

### Pattern 5: Adversarial Reviewer (D-10)

**What:** Rule-based reviewer that returns `(accepted: bool, reason: str)`. Applied after evaluating a mutated solution, before calling `archive.tell()`.

```python
# Source: verified rule math locally
from aerocloud.outer_loop.models import QualityMetrics, QualityWeights

class AdversarialReviewer:
    _METRIC_FIELDS = [
        "layout_coverage", "layout_uniformity", "space_saving",
        "compactness", "aspect_ratio", "realized_adjacencies", "distortion_score",
    ]

    def __init__(self, archive_solutions: np.ndarray, weights: QualityWeights) -> None:
        self._archive_solutions = archive_solutions  # (n_elites, solution_dim)
        self._weights = weights
        self._archive_mean = archive_solutions.mean(axis=0)
        self._archive_std = archive_solutions.std(axis=0) + 1e-8

    def review(
        self,
        solution: np.ndarray,
        metrics_new: QualityMetrics,
        metrics_baseline: QualityMetrics | None,
    ) -> tuple[bool, str]:
        # Rule 3: degenerate layout
        if metrics_new.layout_coverage < 0.1:
            return False, "degenerate_layout: layout_coverage < 0.1"

        # Rule 2: parameter out-of-distribution
        z_scores = np.abs((solution - self._archive_mean) / self._archive_std)
        if np.any(z_scores > 3.0):
            return False, "ood_parameters: z_score > 3.0"

        # Rule 4: single metric gaming
        fitness = metrics_new.combined_fitness(self._weights)
        ar_fraction = (self._weights.w_ar * metrics_new.aspect_ratio) / (fitness + 1e-8)
        if ar_fraction > 0.5:
            return False, "gaming_aspect_ratio: single metric > 50% of total fitness"

        # Rule 1: combined increases but >= 2 individual metrics decrease
        if metrics_baseline is not None:
            fitness_baseline = metrics_baseline.combined_fitness(self._weights)
            if fitness > fitness_baseline:
                n_decreased = sum(
                    getattr(metrics_new, f) < getattr(metrics_baseline, f)
                    for f in self._METRIC_FIELDS
                )
                if n_decreased >= 2:
                    return False, f"reward_hacking: {n_decreased} metrics decreased while combined increased"

        return True, ""
```

**Verified:** Rule 1 correctly triggers when combined fitness increases via gaming one metric while 2+ others drop [VERIFIED locally].

### Pattern 6: KL Divergence Distribution-Shift Monitor (D-13/D-14)

**What:** Compute marginal 1D histograms for each of 4 behavioral descriptor dimensions, sum 4 KL divergences, compare to threshold.

**Critical insight:** Do NOT use a joint 4D histogram (10^4 bins, ~1000 samples → 90% empty → numerically unstable). Use 4 independent 1D marginals. [VERIFIED: joint KL = 11.5 for no-drift, marginal KL = 0.007 for same no-drift case]

```python
# Source: verified locally with scipy.special.rel_entr
import numpy as np
from scipy.special import rel_entr

def compute_kl_divergence(
    descriptors_prev: np.ndarray,   # (n_prev, 4)
    descriptors_curr: np.ndarray,   # (n_curr, 4)
    n_bins: int = 10,
) -> float:
    """Sum of 4 marginal 1D KL divergences over behavioral descriptor dimensions."""
    kl_total = 0.0
    eps = 1e-8
    for dim in range(4):
        h_prev, _ = np.histogram(descriptors_prev[:, dim], bins=n_bins, range=(0.0, 1.0))
        h_curr, _ = np.histogram(descriptors_curr[:, dim], bins=n_bins, range=(0.0, 1.0))
        p = (h_prev + eps) / (h_prev + eps).sum()
        q = (h_curr + eps) / (h_curr + eps).sum()
        kl_total += float(rel_entr(p, q).sum())
    return kl_total
```

**Threshold validation (verified):**

| Scenario | KL (marginal sum) | Alert? |
|----------|-------------------|--------|
| No drift (uniform vs uniform, n=5000) | ~0.007 | No |
| Mild drift (normal 0.4±0.3) | ~0.37 | No |
| Severe collapse (corner 0-0.3) | ~67 | Yes |
| Threshold (D-14) | 0.5 | — |

**Verdict:** The threshold of 0.5 [LOCKED D-14] is appropriate. It will not fire on mild drift, but will fire immediately on actual collapse (diversity collapse = score ~100x threshold).

**n_bins recommendation (Claude's Discretion):** Use `n_bins=10` — matches `ArchiveConfig.bins_per_dim` default, keeps histograms interpretable, and avoids sparsity problems (10 bins × n_samples >> 10 even at low sample counts).

### Pattern 7: Alembic Migration for Replay Tables (D-15/D-16)

**What:** Migration `0004_self_play_replay_tables.py` following the established pattern from migrations 0001-0003.

```python
# Source: pattern from infra/alembic/versions/0003_archive_v1_outer_loop.py [VERIFIED]
revision: str = "0004_self_play_replay_tables"
down_revision: str | None = "0003_archive_v1_outer_loop"

def upgrade() -> None:
    # self_play_runs: one row per nightly run
    op.execute("""
        CREATE TABLE IF NOT EXISTS self_play_runs (
            run_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            started_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            ended_at     TIMESTAMPTZ,
            n_iterations INT NOT NULL DEFAULT 0,
            n_accepted   INT NOT NULL DEFAULT 0,
            n_rejected   INT NOT NULL DEFAULT 0,
            kl_divergence REAL,
            config       JSONB NOT NULL DEFAULT '{}'::jsonb
        )
    """)

    # self_play_events: one row per evaluated mutation
    op.execute("""
        CREATE TABLE IF NOT EXISTS self_play_events (
            event_id      BIGSERIAL PRIMARY KEY,
            run_id        UUID NOT NULL REFERENCES self_play_runs(run_id) ON DELETE CASCADE,
            iteration     INT NOT NULL,
            parent_bin_ids TEXT[] NOT NULL DEFAULT '{}',
            mutation_type TEXT NOT NULL,
            fitness_before REAL,
            fitness_after  REAL NOT NULL,
            accepted       BOOL NOT NULL,
            reject_reason  TEXT
        )
    """)

    # Index for replay reconstruction: all events for a run ordered by iteration
    op.execute("""
        CREATE INDEX IF NOT EXISTS self_play_events_run_id_iteration_idx
            ON self_play_events (run_id, iteration)
    """)
```

**Key points:**
- `gen_random_uuid()` generates UUID in PostgreSQL 13+ without extension [ASSUMED — verify Postgres version has this; fallback: use `uuid_generate_v4()` with uuid-ossp extension]
- `ON DELETE CASCADE` means deleting a run also deletes all its events (replay log cleanup)
- `TEXT[]` for `parent_bin_ids` stores the bin IDs of the 1 or 2 parent solutions
- asyncpg supports UUID natively — no codec registration needed [VERIFIED]
- `kl_divergence` is NULL until end-of-run (populated after comparing to previous night)

### Pattern 8: ReplayLogger asyncpg Integration

**What:** Two asyncpg operations — `insert_run()` (at task start), `insert_event()` (per iteration), `finalize_run()` (at task end with updated stats + KL).

```python
# Source: pattern from outer_loop/persistence.py [VERIFIED]
class ReplayLogger:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def insert_run(self, run_id: uuid.UUID, config: dict) -> None:
        """Create the run record at task start."""
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(
                "INSERT INTO self_play_runs (run_id, config) VALUES ($1, $2::jsonb)",
                run_id, json.dumps(config),
            )
        finally:
            await conn.close()

    async def insert_event(self, run_id: uuid.UUID, event: SelfPlayEvent) -> None:
        """Log one mutation event (one per iteration)."""
        # ... parameterized INSERT with $N placeholders — no string interpolation

    async def finalize_run(
        self, run_id: uuid.UUID, n_accepted: int, n_rejected: int,
        kl_divergence: float | None,
    ) -> None:
        """Update the run record with final stats at task end."""
        # UPDATE self_play_runs SET ended_at=NOW(), n_accepted=$1, ...
```

### Anti-Patterns to Avoid

- **Joint 4D histogram for KL:** With 10^4 bins and ~1000 samples, ~90% of bins are empty. KL divergence becomes dominated by epsilon smoothing noise. Use 4 marginal 1D histograms instead. [VERIFIED]
- **asyncio.run() inside SoftTimeLimitExceeded handler:** `asyncio.run()` creates a new event loop. Do NOT call it from a signal handler context. Instead, flush archive synchronously (it's a single DB call, acceptable) or pre-create an event loop.
- **Calling archive.tell() after adversarial rejection:** Rejected mutations MUST NOT call `tell()`. Only accepted mutations flow through to the archive.
- **Storing baseline in a separate DB table:** D-07 explicitly requires in-memory baseline. DB round-trips per iteration would kill performance.
- **Using `pformat` or string interpolation in SQL:** Follow T-09-05 pattern from persistence.py — all values as `$N` positional arguments.
- **SoftTimeLimitExceeded without time_limit fallback:** Always pair `soft_time_limit` with `time_limit = soft_time_limit + 100`. If the graceful handler hangs, the hard kill fires.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| KL divergence | Custom entropy formula | `scipy.special.rel_entr(p, q).sum()` | Numerically stable, handles zero bins with eps smoothing |
| MAP-Elites archive | Custom dict-based archive | `ArchiveWrapper` (Phase 9, existing) | Already implemented, tested, integrated with pyribs |
| Archive persistence | Custom SQL upsert | `ArchivePersistence` (Phase 9, existing) | Already handles ON CONFLICT fitness guard |
| PostgreSQL async I/O | Custom DB layer | asyncpg with pattern from persistence.py | Pattern established, consistent with project |
| Cron scheduling | Custom scheduler loop | Celery Beat + crontab | Already in dependency tree |
| Pydantic config validation | Custom argparse | `SelfPlayConfig(AeroCloudBase)` | Project-wide standard; frozen, strict, extra=forbid |

---

## Common Pitfalls

### Pitfall 1: 4D Joint Histogram KL Instability

**What goes wrong:** `np.histogramdd(descriptors, bins=10)` creates a 10^4 = 10,000-bin histogram. With ~1000 samples per nightly run, ~90% of bins are empty. After epsilon smoothing, KL divergence reflects epsilon distribution, not actual descriptor distribution.

**Why it happens:** High-dimensional histograms are exponentially sparse relative to sample count.

**How to avoid:** Use 4 independent 1D marginal histograms, sum 4 KL values. [VERIFIED: no-drift marginal KL ≈ 0.007; joint KL ≈ 11.5 for same data]

**Warning signs:** KL divergence > 0.5 on first night with no prior baseline (should be impossible with marginal approach).

### Pitfall 2: SoftTimeLimitExceeded in asyncio Context

**What goes wrong:** `SoftTimeLimitExceeded` is delivered as a signal (SIGXCPU under the hood in billiard). If the task is inside an `asyncio.run()` call at the moment, the signal interrupts the event loop in an undefined way.

**Why it happens:** Celery's solo pool runs tasks synchronously in the main thread. `asyncio.run()` creates a new event loop. Signal delivery to a running event loop can cause `RuntimeError`.

**How to avoid:** The SelfPlayLoop's main `run()` loop should be synchronous. All async DB operations (replay logging) should be called via `asyncio.run()` only in the task's top-level try/except, not nested inside the iteration loop.

**Pattern:**
```python
# GOOD: async call only at iteration boundaries (outside hot loop)
for i in range(n_iterations):
    result = loop.single_iteration_sync()   # sync
    asyncio.run(replay_logger.insert_event(run_id, result))  # async at boundary
```

### Pitfall 3: Dominance Margin Semantics — Tie is Rejected

**What goes wrong:** Using `>=` instead of `>` in the dominance check. With `dominance_margin=0.01`, a solution at exactly `fitness_baseline + 0.01` would be accepted.

**Why it happens:** D-08 says "must exceed" — strict greater-than.

**How to avoid:** Always use `fitness_new > fitness_baseline + dominance_margin` (strict `>`). [VERIFIED: 0.72 > 0.71 + 0.01 is False; 0.73 > 0.71 + 0.01 is True]

### Pitfall 4: Frozen Baseline Stale If Archive Is Updated

**What goes wrong:** The frozen baseline is loaded at task start. If the archive is updated during the run (via tell()), the in-memory baseline becomes stale for subsequent iterations.

**Why it happens:** `ArchivePersistence.load_all()` returns a snapshot. New elites added during the run are not in the snapshot.

**How to avoid:** This is the correct design (D-07). The baseline is intentionally frozen. Do not reload it during the run. The Self-Play loop competes against the archive as it was at the start of the night, not the evolving archive.

### Pitfall 5: Rule 4 (AR Gaming) Only Triggers on Degenerate Combinations

**What goes wrong:** With equal weights (1/7 ≈ 0.143 per metric), the AR metric alone can never contribute > 50% of total fitness unless all other metrics are near zero. This rule will rarely fire on well-formed solutions.

**Why it happens:** With 7 equal weights, max single-metric fraction is 14.3% (if all others are 0 it's 100%).

**How to avoid:** Rule 4 is a degenerate-state detector (AR high + all others collapsed), not a normal-operation discriminator. This is correct — it catches extreme gaming. Accept that this rule fires rarely; rejection rate target (> 5%) is primarily driven by rules 1, 2, and 3.

### Pitfall 6: `gen_random_uuid()` Availability

**What goes wrong:** `gen_random_uuid()` is a PostgreSQL built-in available since PG 13. If the Postgres instance is < 13 or the `uuid-ossp` extension isn't loaded, `DEFAULT gen_random_uuid()` in the DDL fails.

**Why it happens:** The migration sets UUID as a DEFAULT, not generated in Python.

**How to avoid:** Generate `uuid.uuid4()` in Python and pass it as a parameter to the INSERT rather than relying on a SQL default. This is safer and more portable. asyncpg handles UUID natively. [VERIFIED: asyncpg 0.31.0 UUID support confirmed]

```python
# SAFE: generate in Python
import uuid
run_id = uuid.uuid4()
await conn.execute("INSERT INTO self_play_runs (run_id, ...) VALUES ($1, ...)", run_id, ...)
```

---

## Code Examples

### Verified: SoftTimeLimitExceeded catch pattern

```python
# Source: celery.exceptions (verified: celery 5.6.3 + billiard)
from celery.exceptions import SoftTimeLimitExceeded

@app.task(soft_time_limit=28800, time_limit=28900, queue="background", max_retries=0)
def self_play_nightly(n_iterations: int = 1000) -> dict:
    loop = SelfPlayLoop.build_from_env()
    n_done = 0
    try:
        for _ in range(n_iterations):
            loop.single_iteration()
            n_done += 1
    except SoftTimeLimitExceeded:
        pass  # exit iteration loop cleanly
    finally:
        # This always runs — flush + finalize even on unexpected errors
        loop.flush_and_finalize(n_done=n_done)
    return {"n_iterations_completed": n_done, "status": "ok"}
```

### Verified: KL divergence monitoring call

```python
# Source: verified locally — scipy.special.rel_entr (scipy 1.17.1)
import numpy as np
from scipy.special import rel_entr

def compute_kl_marginal(
    prev_descriptors: np.ndarray,  # (n_prev, 4) — from previous night's run
    curr_descriptors: np.ndarray,  # (n_curr, 4) — from current run
    n_bins: int = 10,
    kl_threshold: float = 0.5,
) -> tuple[float, bool]:
    """Returns (kl_sum, alert_triggered)."""
    eps = 1e-8
    kl_sum = 0.0
    for dim in range(4):
        h_prev, _ = np.histogram(prev_descriptors[:, dim], bins=n_bins, range=(0.0, 1.0))
        h_curr, _ = np.histogram(curr_descriptors[:, dim], bins=n_bins, range=(0.0, 1.0))
        p = (h_prev + eps) / (h_prev + eps).sum()
        q = (h_curr + eps) / (h_curr + eps).sum()
        kl_sum += float(rel_entr(p, q).sum())
    return kl_sum, kl_sum > kl_threshold
```

### Verified: Dominance check

```python
# Source: D-08, verified locally
def passes_dominance(
    fitness_new: float,
    fitness_baseline: float,
    margin: float = 0.01,
) -> bool:
    """Strict greater-than — tie at margin = rejected."""
    return fitness_new > fitness_baseline + margin
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Joint 4D KL histogram | 4 marginal 1D KL histograms | This phase | Numerically stable with <10k samples |
| ML adversarial reviewer | Rule-based heuristic (D-10) | This phase (deferred to Phase 12+) | Faster, auditable, no training data needed |
| Celery prefork pool for GPU | `--pool=solo` (CUDA fork safety) | Phase 9 decision, nightly research 2026-04-11 | Prevents CUDA fork Segfaults |
| Celery 5.4.x | Celery 5.6.3 ("Recovery" series) | Early 2026 | Warm-shutdown heartbeat loss fixed |

**Deprecated/outdated:**
- `celery.utils.functional.fun_takes_argument`: removed in 5.x — don't use in task class detection
- `task.request.retries`: not applicable when `max_retries=0` — omit retry logic entirely

---

## Project Constraints (from CLAUDE.md)

| Directive | Applies to Phase 10 |
|-----------|---------------------|
| Tests are laws — NEVER adjusted to match code | All 10 test types apply; unit + integration + property mandatory |
| Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:` | All commits |
| NO pickle — safetensors only for tensor serialization | Replay log: don't serialize tensors to `self_play_events`; store scalars only |
| Codebase language: English (code, comments, commits, tests, API) | All new modules |
| structlog throughout for logging | ReplayLogger, SelfPlayLoop, reviewer all use structlog |
| asyncpg pattern: direct connection per call (no pool), `$N` placeholders | ReplayLogger follows persistence.py pattern |
| mypy --strict must pass | All new modules: full type annotations, no `Any` without reason |
| ruff check + ruff format | All new files |
| Wiki: all new modules documented in wiki/code/ | Post-phase wiki update required |
| Session handover to wiki/discussions/ after phase complete | Mandatory after Phase 10 |
| 3-AI review required before merge | Phase 10 final plan must include review wave |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `gen_random_uuid()` available in the deployed PostgreSQL | Architecture Patterns (Migration) | Migration DDL fails; mitigated by generating UUID in Python [recommended] |
| A2 | PostgreSQL instance is version 13+ | Architecture Patterns (Migration) | `gen_random_uuid()` unavailable; use Python uuid4() generation instead |
| A3 | `sigma_xy=0.05, sigma_scale=0.02, sigma_theta=0.1` are reasonable default sigmas for SelfPlayConfig | Standard Stack / Architecture | Too small = no exploration; too large = all solutions degenerate. Needs empirical tuning but safe for initial implementation |
| A4 | Fitness-proportional parent sampling not needed for crossover | Architecture Patterns (Crossover) | Uniform random sampling may produce weaker offspring; fitness-proportional could improve convergence but is out of scope per discretion |
| A5 | Replay log retention policy: no auto-delete by default | Architecture Patterns (Migration) | Table grows unboundedly; add retention policy in Phase 12 or document as operational task |

---

## Open Questions

1. **Where does the previous night's descriptor array come from for KL divergence?**
   - What we know: D-13 says "compare consecutive nights via KL divergence"
   - What's unclear: The previous night's descriptor array is not stored in any existing table. It must either be stored in `self_play_runs.config JSONB`, a new column, or recomputed from `self_play_events` (parent_bin_ids → archive lookup)
   - Recommendation: Store the 4D descriptor array (serialized as JSON) in `self_play_runs.config` under key `"descriptor_histogram"`. At start of each nightly run, load the previous run's histogram, compute KL against current run's descriptors, write result to `self_play_runs.kl_divergence`.

2. **How to handle first-night KL (no prior night exists)?**
   - What we know: KL divergence requires two nights to compare
   - What's unclear: Should first night write `kl_divergence = NULL` or 0.0?
   - Recommendation: `NULL` (explicitly missing, not "no drift"). The query that computes KL should `ORDER BY started_at DESC LIMIT 2` and skip if fewer than 2 rows exist.

3. **Should replay events be logged for rejected mutations?**
   - What we know: D-11 says "Rejected mutations logged but not added to archive"
   - What's unclear: D-16 event schema has `accepted BOOL` + `reject_reason TEXT` — suggests YES, both accepted and rejected events are logged
   - Recommendation: Log all events (accepted and rejected) — `accepted=False, reject_reason="reward_hacking:..."`. This is what "Replay log enables full reconstruction" (D-17) requires.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Celery + Redis broker | SP-01: Beat scheduling | Redis available (auth required) | celery 5.6.3 | — |
| PostgreSQL | SP-08: Replay tables | Available on :5432 | accepting connections | — |
| scipy.special.rel_entr | SP-07: KL divergence | Available | scipy 1.17.1 | scipy.stats.entropy (equivalent) |
| numpy | SP-03: Mutation operators | Available | 2.4.4 | — |
| asyncpg UUID | SP-08: run_id | Available | asyncpg 0.31.0 | — |
| pyribs ArchiveWrapper | SP-02: Monte-Carlo sampling | Available | pyribs 0.10.0 | — |
| Celery SoftTimeLimitExceeded | SP-01: Graceful exit | Available | celery 5.6.3 / billiard | — |
| pytest | Test framework | Available | pytest 9.0.2 | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + hypothesis |
| Config file | `pyproject.toml` (packages/engine) |
| Quick run command | `uv run pytest packages/engine/tests/self_play/ -x -q` |
| Full suite command | `uv run pytest packages/engine/tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SP-01 | Beat schedule registered correctly | unit | `uv run pytest packages/engine/tests/self_play/unit/test_config.py -x` | Wave 0 |
| SP-01 | SoftTimeLimitExceeded caught, finalize called | unit | `uv run pytest packages/engine/tests/self_play/unit/test_task.py -x` | Wave 0 |
| SP-02 | Monte-Carlo sampling returns valid solutions | unit | `uv run pytest packages/engine/tests/self_play/unit/test_mutation.py -x` | Wave 0 |
| SP-03 | Gaussian mutation: shape preserved, noise applied | unit | `uv run pytest packages/engine/tests/self_play/unit/test_mutation.py -x` | Wave 0 |
| SP-03 | Crossover child is elementwise from one of two parents | unit | `uv run pytest packages/engine/tests/self_play/unit/test_mutation.py -x` | Wave 0 |
| SP-03 | Structure-aware: per-column sigma differs | unit | `uv run pytest packages/engine/tests/self_play/unit/test_mutation.py -x` | Wave 0 |
| SP-04 | Baseline loaded from ArchivePersistence.load_all() at task start | integration | `uv run pytest packages/engine/tests/self_play/integration/test_self_play_loop.py -x` | Wave 0 |
| SP-05 | Dominance margin: tie at margin is rejected | unit | `uv run pytest packages/engine/tests/self_play/unit/test_mutation.py -x` | Wave 0 |
| SP-06 | Reviewer rule 1: triggers when combined increases + 2 metrics decrease | unit | `uv run pytest packages/engine/tests/self_play/unit/test_reviewer.py -x` | Wave 0 |
| SP-06 | Reviewer rule 2: ood parameter flagged | unit | `uv run pytest packages/engine/tests/self_play/unit/test_reviewer.py -x` | Wave 0 |
| SP-06 | Reviewer rule 3: degenerate layout flagged | unit | `uv run pytest packages/engine/tests/self_play/unit/test_reviewer.py -x` | Wave 0 |
| SP-06 | Reviewer rule 4: AR gaming flagged | unit | `uv run pytest packages/engine/tests/self_play/unit/test_reviewer.py -x` | Wave 0 |
| SP-07 | Marginal KL < 0.5 for identical distributions | unit | `uv run pytest packages/engine/tests/self_play/unit/test_monitoring.py -x` | Wave 0 |
| SP-07 | Marginal KL > 0.5 for collapsed distributions | unit | `uv run pytest packages/engine/tests/self_play/unit/test_monitoring.py -x` | Wave 0 |
| SP-07 | First night: KL is None/skipped when no prior baseline | unit | `uv run pytest packages/engine/tests/self_play/unit/test_monitoring.py -x` | Wave 0 |
| SP-08 | insert_run creates row in self_play_runs | integration | `uv run pytest packages/engine/tests/self_play/unit/test_replay.py -x` | Wave 0 |
| SP-08 | insert_event creates row in self_play_events with run_id FK | integration | `uv run pytest packages/engine/tests/self_play/unit/test_replay.py -x` | Wave 0 |
| SP-08 | finalize_run updates n_accepted, n_rejected, kl_divergence | integration | `uv run pytest packages/engine/tests/self_play/unit/test_replay.py -x` | Wave 0 |
| SP-08 | Replay events sufficient to reconstruct run (ordering by iteration) | integration | `uv run pytest packages/engine/tests/self_play/integration/test_self_play_loop.py -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest packages/engine/tests/self_play/ -x -q`
- **Per wave merge:** `uv run pytest packages/engine/tests/ -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `packages/engine/tests/self_play/__init__.py`
- [ ] `packages/engine/tests/self_play/conftest.py` — shared fixtures (mock archive, mock ArchivePersistence)
- [ ] `packages/engine/tests/self_play/unit/__init__.py`
- [ ] `packages/engine/tests/self_play/unit/test_config.py` — SelfPlayConfig validation
- [ ] `packages/engine/tests/self_play/unit/test_mutation.py` — Gaussian, crossover, dominance, structure-aware
- [ ] `packages/engine/tests/self_play/unit/test_reviewer.py` — all 4 adversarial rules
- [ ] `packages/engine/tests/self_play/unit/test_monitoring.py` — KL divergence + threshold
- [ ] `packages/engine/tests/self_play/unit/test_replay.py` — ReplayLogger (mock asyncpg or test DB)
- [ ] `packages/engine/tests/self_play/integration/__init__.py`
- [ ] `packages/engine/tests/self_play/integration/test_self_play_loop.py` — end-to-end loop
- [ ] `packages/engine/tests/self_play/determinism/__init__.py`
- [ ] `packages/engine/tests/self_play/determinism/test_determinism.py` — same seed = same results
- [ ] `infra/alembic/versions/0004_self_play_replay_tables.py` — migration file

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Internal background task, no user auth |
| V3 Session Management | No | No sessions in background task |
| V4 Access Control | No | No user-controlled access paths |
| V5 Input Validation | Yes | Pydantic SelfPlayConfig; SelfPlayEvent schema |
| V6 Cryptography | No | No encryption needed; no user secrets |
| SQL Injection | Yes | asyncpg `$N` parameterized — no string interpolation (pattern from persistence.py T-09-05) |

### Known Threat Patterns for Self-Play Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via bin_id or reject_reason | Tampering | All asyncpg inserts use `$N` positional parameters (T-09-05 pattern) |
| Deserialization RCE via params_blob | Tampering | Replay tables store only scalars (REAL, INT, TEXT) — no tensor blobs; no pickle anywhere |
| Degenerate KL (divide by zero) | Tampering | epsilon smoothing `eps=1e-8` applied before `rel_entr` |
| Unbounded replay table growth | DoS | Documented as known — retention policy deferred to Phase 12; add index on `started_at` |
| CUDA fork segfault | DoS | `--pool=solo` prevents forking [LOCKED D-01] |
| CVE-2026-24149 (Megatron-LM RCE via checkpoint) | Tampering | Not applicable — no checkpoint loading; safetensors only |
| Beat task double-trigger | Spoofing | `max_retries=0` + Celery's built-in "one instance" beat lock prevents double-run |

---

## Sources

### Primary (HIGH confidence)

- Codebase: `packages/engine/src/aerocloud/outer_loop/persistence.py` — asyncpg pattern, parameterized SQL, safetensors
- Codebase: `packages/engine/src/aerocloud/outer_loop/scheduler.py` — OuterLoop.run() integration point
- Codebase: `apps/worker/pyproject.toml` — celery[redis]>=5.4.0 dependency confirmed
- Codebase: `infra/alembic/versions/0003_archive_v1_outer_loop.py` — migration pattern
- Verified locally: `uv run python` — all package versions, scipy rel_entr, KL math, Celery soft_time_limit, UUID support

### Secondary (MEDIUM confidence)

- Wiki: `wiki/research/nightly/2026-04-11-celery-gpu-worker-pool-management.md` — Celery 5.6.3 "Recovery" series, solo pool pattern
- Web search: Celery workers guide (docs.celeryq.dev) — soft_time_limit, SIGTERM warm shutdown behavior

### Tertiary (LOW confidence)

- WebSearch: MAP-Elites self-play diversity collapse — general ecosystem awareness, no specific papers found for exact Phase 10 approach

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages installed and verified
- Architecture: HIGH — all patterns verified against existing codebase; math verified locally
- Pitfalls: HIGH — KL pitfall verified numerically; Celery patterns verified against installed version
- Alembic migration: HIGH — pattern established by 3 prior migrations in codebase
- KL threshold: MEDIUM — validated mathematically but exact behavior at 0.37 (mild drift) is close to threshold; empirical tuning during Phase 10 recommended

**Research date:** 2026-04-16
**Valid until:** 2026-05-16 (30 days — stable dependencies)

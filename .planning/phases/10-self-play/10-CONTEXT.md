# Phase 10: Self-Play - Context

**Gathered:** 2026-04-21 (assumptions mode)
**Status:** Ready for planning

<domain>
## Phase Boundary

Nightly Self-Play training with adversarial reviewer and replay logging. Celery Beat scheduled job samples elites from archive, mutates/crossovers, evaluates against frozen baseline, applies stricter dominance, and logs everything for replay. Runs 8 hours nightly then exits cleanly.

Requirements: SP-01 to SP-08.

</domain>

<decisions>
## Implementation Decisions

### Scheduling Infrastructure
- **D-01:** Celery Beat nightly job using existing `celery[redis]>=5.4.0` from apps/worker. Queue: `background`. Pool: `solo` (CUDA fork safety).
- **D-02:** Task: `self_play_nightly(n_iterations=1000, soft_time_limit=28800)`. Calls OuterLoop.run() with self-play mutation operators.
- **D-03:** Graceful exit: on SIGTERM or soft_time_limit, finish current iteration, flush archive, write replay log summary, exit 0.

### Mutation & Crossover Operators
- **D-04:** Gaussian perturbation on flat `(max_words * 4)` solution arrays (reuse existing sigma from ArchiveConfig).
- **D-05:** Crossover: uniform crossover on two parent solutions sampled via Monte-Carlo from archive. Per-parameter probability p=0.5 of taking from parent A vs B.
- **D-06:** Structure-aware mutation: reshape to (N,4), apply different sigma per column (position sigma_xy, scale sigma_s, rotation sigma_theta). Configurable via `SelfPlayConfig`.

### Frozen Baseline & Stricter Dominance
- **D-07:** Frozen baseline = snapshot of archive at start of nightly run via ArchivePersistence.load_all(). Stored in memory, not a separate table.
- **D-08:** Stricter dominance: mutated solution must exceed baseline fitness by `dominance_margin` (default 0.01). `fitness_new > fitness_baseline + dominance_margin`.
- **D-09:** SP-04 evaluation: compare quality metrics of mutated solution against frozen baseline for the same bin_id.

### Adversarial Reviewer
- **D-10:** Rule-based heuristic, NOT trained ML model. Flags reward-hacking patterns:
  - combined_fitness increases but >= 2 individual metrics decrease
  - any parameter value exceeds 3 std devs from archive mean
  - layout_coverage < 0.1 (degenerate empty layout)
  - aspect_ratio metric contributes > 50% of total fitness (gaming one metric)
- **D-11:** Reviewer returns `(accepted: bool, reason: str)`. Rejected mutations logged but not added to archive.
- **D-12:** Success criterion: > 5% rejection rate across a nightly run.

### Distribution-Shift Monitoring
- **D-13:** Track 4D behavioral descriptor distribution per nightly run. Compare consecutive nights via KL divergence on discretized histograms.
- **D-14:** Alert threshold: KL divergence > 0.5 between consecutive nights. Log warning via structlog + Telegram notification.

### Replay Log
- **D-15:** New Alembic migration for `self_play_runs` table: `(run_id UUID PK, started_at TIMESTAMPTZ, ended_at TIMESTAMPTZ, n_iterations INT, n_accepted INT, n_rejected INT, kl_divergence REAL, config JSONB)`.
- **D-16:** New `self_play_events` table: `(event_id BIGSERIAL PK, run_id UUID FK, iteration INT, parent_bin_ids TEXT[], mutation_type TEXT, fitness_before REAL, fitness_after REAL, accepted BOOL, reject_reason TEXT)`.
- **D-17:** Replay log enables full reconstruction of each Self-Play run per success criterion 4.

### Claude's Discretion
- Exact histogram bin count for KL divergence
- Celery Beat schedule cron expression (default: 0 2 * * * Berlin time)
- Crossover parent selection strategy (uniform random vs fitness-proportional)
- Replay log retention policy

</decisions>

<canonical_refs>
## Canonical References

### Outer Loop Integration
- `packages/engine/src/aerocloud/outer_loop/scheduler.py` — OuterLoop.run() entry point
- `packages/engine/src/aerocloud/outer_loop/archive.py` — ArchiveWrapper, archive.data()
- `packages/engine/src/aerocloud/outer_loop/emitter.py` — GaussianEmitter, NoveltyGaussianEmitter
- `packages/engine/src/aerocloud/outer_loop/persistence.py` — ArchivePersistence flush/load
- `packages/engine/src/aerocloud/outer_loop/metrics.py` — compute_all_metrics, QualityMetrics
- `packages/engine/src/aerocloud/outer_loop/models.py` — ArchiveConfig, QualityMetrics, ArchiveFlushEntry

### Worker Infrastructure
- `apps/worker/pyproject.toml` — celery[redis]>=5.4.0 dependency
- `wiki/research/nightly/2026-04-11-celery-gpu-worker-pool-management.md` — --pool=solo pattern

### Persistence
- `infra/alembic/versions/0001_baseline.py` — archive_v1 base table
- `infra/alembic/versions/0003_archive_v1_outer_loop.py` — Phase 9 extension

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- OuterLoop.run(n_iterations) — the evaluation loop Self-Play will wrap
- ArchivePersistence.load_all() — frozen baseline snapshot
- NoveltyGaussianEmitter — sigma boost pattern reusable for mutation
- structlog throughout outer_loop — replay logging pattern
- asyncpg persistence pattern — for replay tables

### Integration Points
- Celery task calls OuterLoop with self-play mutation operators
- Frozen baseline loaded from PostgreSQL at job start
- Replay log written to new tables during and after run
- Distribution monitoring compares descriptor distributions across runs

</code_context>

<deferred>
## Deferred Ideas

- Trained adversarial reviewer model (discriminator network) — Phase 12+ if rule-based proves insufficient
- Multi-GPU parallel Self-Play workers — Phase 12 scaling
- Warm-start Self-Play from prior night's best solutions — consider for v2

</deferred>

---

*Phase: 10-self-play*
*Context gathered: 2026-04-21*

"""Self-play data models: SelfPlayRunResult and SelfPlayEvent (Phase 10, SP-08).

Design decisions:
    D-15: SelfPlayRunResult captures aggregate metrics for a completed nightly run.
    D-16: SelfPlayEvent captures per-iteration mutation/evaluation details.
    Both extend AeroCloudBase (frozen=True, strict=True, extra="forbid").

Persistence:
    These models are serialized to/from self_play_runs and self_play_events tables
    via ReplayLogger (replay.py). Field types match the DB column types defined in
    migration 0004_self_play_replay_tables.
"""

from __future__ import annotations

from aerocloud.models.base import AeroCloudBase


class SelfPlayRunResult(AeroCloudBase):
    """Aggregate result for a completed self-play training run.

    Attributes:
        run_id: UUID string identifying this run (Python-generated, not SQL DEFAULT).
        started_at: ISO 8601 timestamp when the run started.
        ended_at: ISO 8601 timestamp when the run ended.
        n_iterations: Total number of mutation/evaluation iterations attempted.
        n_accepted: Number of iterations where mutant replaced archive entry.
        n_rejected: Number of iterations where mutant was rejected.
        kl_divergence: KL-divergence between current and previous descriptor
            histograms; None if no previous run exists.
        exit_reason: Human-readable exit reason (e.g., "completed", "soft_timeout",
            "error").
    """

    run_id: str
    started_at: str
    ended_at: str
    n_iterations: int
    n_accepted: int
    n_rejected: int
    kl_divergence: float | None
    exit_reason: str


class SelfPlayEvent(AeroCloudBase):
    """Per-iteration self-play event record.

    Attributes:
        iteration: Zero-based iteration index within the run.
        parent_bin_ids: Archive bin IDs from which parent(s) were drawn.
        mutation_type: Name of the mutation operator applied (e.g., "sigma_xy",
            "crossover", "sigma_scale").
        fitness_before: Fitness of the bin occupant before mutation; None if bin
            was empty.
        fitness_after: Fitness of the mutant after evaluation.
        accepted: True if mutant was accepted into the archive.
        reject_reason: Human-readable reason for rejection; empty string if accepted.
    """

    iteration: int
    parent_bin_ids: list[str]
    mutation_type: str
    fitness_before: float | None
    fitness_after: float
    accepted: bool
    reject_reason: str

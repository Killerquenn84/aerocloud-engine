"""AeroCloud Self-Play package (Phase 10).

Public API:
    SelfPlayConfig      — frozen Pydantic config for self-play hyperparameters
    SelfPlayRunResult   — immutable result model for a completed run
    SelfPlayEvent       — immutable model for a single iteration event
    SelfPlayLoop        — nightly self-play training loop orchestrator
    structure_aware_mutate — Gaussian mutation operator (per-column sigma)
    uniform_crossover   — per-element crossover operator
    sample_parents      — uniform random parent sampling from archive
    AdversarialReviewer — rule-based reward-hacking reviewer (4 rules)
    compute_kl_divergence  — KL divergence over 4 marginal 1D histograms
    check_distribution_shift — threshold check with structlog warning
    ReplayLogger        — asyncpg persistence for self_play_runs / self_play_events
"""

from __future__ import annotations

from aerocloud.self_play.config import SelfPlayConfig
from aerocloud.self_play.loop import SelfPlayLoop
from aerocloud.self_play.models import SelfPlayEvent, SelfPlayRunResult
from aerocloud.self_play.monitoring import check_distribution_shift, compute_kl_divergence
from aerocloud.self_play.mutation import sample_parents, structure_aware_mutate, uniform_crossover
from aerocloud.self_play.replay import ReplayLogger
from aerocloud.self_play.reviewer import AdversarialReviewer

__all__ = [
    "AdversarialReviewer",
    "ReplayLogger",
    "SelfPlayConfig",
    "SelfPlayEvent",
    "SelfPlayLoop",
    "SelfPlayRunResult",
    "check_distribution_shift",
    "compute_kl_divergence",
    "sample_parents",
    "structure_aware_mutate",
    "uniform_crossover",
]

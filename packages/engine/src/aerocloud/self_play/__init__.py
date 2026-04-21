"""AeroCloud Self-Play package (Phase 10).

Public API:
    SelfPlayConfig    — frozen Pydantic config for self-play hyperparameters
    SelfPlayRunResult — immutable result model for a completed run
    SelfPlayEvent     — immutable model for a single iteration event
    ReplayLogger      — asyncpg persistence for self_play_runs / self_play_events
"""

from __future__ import annotations

from aerocloud.self_play.config import SelfPlayConfig
from aerocloud.self_play.models import SelfPlayEvent, SelfPlayRunResult
from aerocloud.self_play.replay import ReplayLogger

__all__ = [
    "ReplayLogger",
    "SelfPlayConfig",
    "SelfPlayEvent",
    "SelfPlayRunResult",
]

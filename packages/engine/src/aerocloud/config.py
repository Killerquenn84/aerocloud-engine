"""Pydantic-Settings configuration for AeroCloud Engine.

Loads from environment variables (optionally via ``.env`` file in dev).

Usage:
    >>> from aerocloud.config import Settings
    >>> settings = Settings()  # reads env
    >>> settings.database_url
    'postgresql://...'

References:
    - .planning/phases/01-foundation/01-CONTEXT.md D-24..D-26
    - .planning/research/ARCHITECTURE.md §8 (config)
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the engine, API, and worker.

    Every field maps to an environment variable. Defaults are safe for local
    dev; production deployments override via Kubernetes secrets / Hostinger
    environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str = Field(
        default="postgresql://aerocloud:devpassword@localhost:5432/aerocloud",
        description="PostgreSQL connection URI with pgvector extension enabled",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URI for Celery broker + result backend",
    )
    gpu_device: str = Field(
        default="cuda:0",
        description="PyTorch device string for the Inner Loop worker",
    )
    model_cache_dir: str = Field(
        default="/var/cache/aerocloud/models",
        description="Filesystem path for cached BERT + nvdiffrast model files",
    )
    log_level: str = Field(
        default="INFO",
        description="Log level for structlog (DEBUG/INFO/WARNING/ERROR)",
    )
    seed: int = Field(
        default=42,
        description="Global deterministic seed for numpy + torch + random",
    )
    # Geometry cache budget (Phase 4 D-18). 384 MiB = 402653184 bytes.
    sdf_cache_max_bytes: int = Field(
        default=402_653_184,
        description="Per-worker bytes budget for the SDF LRU cache (D-18).",
        ge=1_048_576,  # minimum 1 MiB sanity floor
    )
    # MAT settings (Phase 7 D-01).
    mat_min_branch_radius: float = Field(
        default=3.0,
        description="Minimum inscribed-circle radius for MAT branch inclusion (Phase 7).",
        gt=0.0,
    )
    mat_cache_max_bytes: int = Field(
        default=128 * 1024 * 1024,  # 128 MiB
        description="Per-worker bytes budget for the MAT LRU cache (Phase 7).",
        ge=1_048_576,  # minimum 1 MiB sanity floor
    )


def load_settings() -> Settings:
    """Return a freshly instantiated :class:`Settings` object."""
    return Settings()


#: Module-level singleton — use `from aerocloud.config import settings` in production code.
#: Tests that need custom overrides should call `load_settings()` or patch directly.
settings: Settings = Settings()

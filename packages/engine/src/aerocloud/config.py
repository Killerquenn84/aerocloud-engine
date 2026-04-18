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
    # Semantic Vector Space settings (Phase 8).
    projection_method: str = Field(
        default="umap",
        description="2D projection method for semantic warm-start: 'umap' or 'tsne' (D-06)",
    )
    sinkhorn_eps_init: float = Field(
        default=0.1,
        description="Sinkhorn-Knopp initial epsilon for Optimal Transport (D-09)",
        gt=0.0,
    )
    sinkhorn_max_iter: int = Field(
        default=1000,
        description="Sinkhorn-Knopp maximum iterations before convergence failure",
        ge=1,
    )
    embedding_batch_size: int = Field(
        default=32,
        description="BERT encode batch size for sentence-transformers (D-03)",
        ge=1,
    )
    # Outer Loop / MAP-Elites settings (Phase 9 D-02, D-03, D-12, D-11, D-14).
    archive_bins_per_dim: int = Field(
        default=10,
        ge=2,
        le=50,
        description="Bins per behavioral dimension for MAP-Elites GridArchive (D-02)",
    )
    archive_sigma: float = Field(
        default=0.1,
        gt=0.0,
        description="GaussianEmitter perturbation std dev",
    )
    archive_batch_size: int = Field(
        default=16,
        ge=1,
        description="Solutions per ask() call",
    )
    archive_max_words: int = Field(
        default=200,
        ge=10,
        description="Max word count for fixed solution_dim",
    )
    novelty_k: int = Field(
        default=15,
        ge=1,
        description="k-NN neighbors for novelty search (D-12)",
    )
    flush_every_n: int = Field(
        default=100,
        ge=1,
        description="Batch flush interval to PostgreSQL (D-11)",
    )
    reeval_every_n: int = Field(
        default=200,
        ge=1,
        description="Re-evaluation interval for elites (D-14)",
    )


def load_settings() -> Settings:
    """Return a freshly instantiated :class:`Settings` object."""
    return Settings()


#: Module-level singleton — use `from aerocloud.config import settings` in production code.
#: Tests that need custom overrides should call `load_settings()` or patch directly.
settings: Settings = Settings()

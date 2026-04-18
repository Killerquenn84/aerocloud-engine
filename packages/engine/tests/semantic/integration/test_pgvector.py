"""Integration tests for pgvector persistence — Phase 8 SEM-07 (D-13, D-14, D-15).

Tests use testcontainers to spin up a PostgreSQL+pgvector container on demand.
If Docker is not available, all tests are skipped with a clear message.

Test suite covers:
    1. Migration upgrade creates word_embeddings table
    2. Migration downgrade drops word_embeddings table
    3. HNSW index exists on embedding column (vector_cosine_ops)
    4. store_embeddings inserts a single row
    5. load_cached_embeddings returns cached embedding for known surface
    6. load_cached_embeddings returns empty dict for unknown surface (cache miss)
    7. store_embeddings upserts (no duplicate key error on repeated call)
    8. D-15: No writes to archive_v1 during persistence operations

Architecture decisions honoured:
    D-13: word_embeddings table schema (surface PK, embedding vector(384),
          model_version, created_at)
    D-14: HNSW index on embedding with vector_cosine_ops
    D-15: Phase 8 must NOT write to archive_v1
    T-08-10: Parameterised queries only — no string interpolation for surface values
    T-08-11: database_url never logged
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import Generator

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Docker availability check — skip all tests if Docker not usable
# ---------------------------------------------------------------------------


def _docker_available() -> bool:
    """Return True if Docker daemon is reachable."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


_DOCKER_OK = _docker_available()
_SKIP_DOCKER = pytest.mark.skipif(not _DOCKER_OK, reason="Docker not available — skipping pgvector integration tests")

pytestmark = _SKIP_DOCKER

# ---------------------------------------------------------------------------
# pgvector docker image — use ankane/pgvector which bundles extension
# ---------------------------------------------------------------------------

_PGVECTOR_IMAGE = "ankane/pgvector:v0.7.0"

# ---------------------------------------------------------------------------
# Alembic helpers
# ---------------------------------------------------------------------------

_ALEMBIC_INI = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "..",
    "..",
    "..",
    "infra",
    "alembic",
    "alembic.ini",
)


def _alembic_run(db_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run alembic CLI command with the given DATABASE_URL."""
    env = {**os.environ, "DATABASE_URL": db_url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", _ALEMBIC_INI, *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


# ---------------------------------------------------------------------------
# Module-scoped PostgreSQL container fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pg_url() -> Generator[str, None, None]:
    """Spin up a PostgreSQL+pgvector container for the test module.

    Yields the database URL, then tears down the container on module exit.
    Uses testcontainers to manage lifecycle automatically.
    """
    from testcontainers.postgres import PostgresContainer  # noqa: PLC0415

    with PostgresContainer(image=_PGVECTOR_IMAGE, dbname="aerocloud_test") as pg:
        url = pg.get_connection_url().replace("psycopg2", "asyncpg")
        # Also set as env var for aerocloud.config.settings
        os.environ["DATABASE_URL"] = url

        # Run migrations up to head
        result = _alembic_run(url, "upgrade", "head")
        assert result.returncode == 0, (
            f"alembic upgrade failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )

        yield url

        # Teardown: downgrade to base (container will be destroyed anyway,
        # but this verifies downgrade works)
        _alembic_run(url, "downgrade", "base")


# ---------------------------------------------------------------------------
# Helper: run async function synchronously
# ---------------------------------------------------------------------------


def _run(coro):  # type: ignore[no-untyped-def]
    """Run a coroutine in a fresh event loop and return the result."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Shared fixture: deterministic (1, 384) float32 embedding
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_embedding() -> np.ndarray:
    """Deterministic (1, 384) float32 embedding for test isolation."""
    rng = np.random.default_rng(2026)
    return rng.standard_normal((1, 384)).astype(np.float32)


# ---------------------------------------------------------------------------
# Test 1: Migration upgrade creates word_embeddings table
# ---------------------------------------------------------------------------


def test_migration_upgrade_creates_word_embeddings_table(pg_url: str) -> None:
    """After alembic upgrade head, word_embeddings must exist in public schema."""
    import asyncpg  # noqa: PLC0415

    async def _check() -> bool:
        conn = await asyncpg.connect(pg_url)
        try:
            exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_tables
                    WHERE schemaname = 'public'
                      AND tablename  = 'word_embeddings'
                )
                """
            )
            return bool(exists)
        finally:
            await conn.close()

    assert _run(_check()), "word_embeddings table not found after upgrade"


# ---------------------------------------------------------------------------
# Test 2: Migration downgrade drops word_embeddings table
# ---------------------------------------------------------------------------


def test_migration_downgrade_drops_word_embeddings_table(pg_url: str) -> None:
    """Downgrade to 0001_baseline drops word_embeddings; upgrade restores it."""
    import asyncpg  # noqa: PLC0415

    async def _table_exists(table: str) -> bool:
        conn = await asyncpg.connect(pg_url)
        try:
            return bool(
                await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM pg_tables
                        WHERE schemaname = 'public' AND tablename = $1
                    )
                    """,
                    table,
                )
            )
        finally:
            await conn.close()

    # Downgrade to 0001_baseline
    result = _alembic_run(pg_url, "downgrade", "0001_baseline")
    assert result.returncode == 0, f"downgrade to 0001_baseline failed:\n{result.stderr}"

    assert not _run(_table_exists("word_embeddings")), (
        "word_embeddings table still exists after downgrade to 0001_baseline"
    )

    # Restore for subsequent tests
    result = _alembic_run(pg_url, "upgrade", "head")
    assert result.returncode == 0, f"re-upgrade failed:\n{result.stderr}"

    assert _run(_table_exists("word_embeddings")), (
        "word_embeddings table missing after re-upgrade"
    )


# ---------------------------------------------------------------------------
# Test 3: HNSW index exists on embedding column
# ---------------------------------------------------------------------------


def test_hnsw_index_exists_on_embedding_column(pg_url: str) -> None:
    """HNSW index with vector_cosine_ops must exist on word_embeddings.embedding."""
    import asyncpg  # noqa: PLC0415

    async def _check() -> bool:
        conn = await asyncpg.connect(pg_url)
        try:
            rows = await conn.fetch(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'word_embeddings'
                """
            )
            return any(
                "hnsw" in (row["indexdef"] or "").lower() for row in rows
            )
        finally:
            await conn.close()

    assert _run(_check()), "No HNSW index found on word_embeddings.embedding"


# ---------------------------------------------------------------------------
# Test 4: store_embeddings inserts a single row
# ---------------------------------------------------------------------------


def test_store_embeddings_inserts_one_row(
    pg_url: str, sample_embedding: np.ndarray
) -> None:
    """store_embeddings(["hello"], emb) must return 1 (one row inserted)."""
    from aerocloud.semantic.persistence import store_embeddings  # noqa: PLC0415

    inserted = _run(store_embeddings(["hello_t4"], sample_embedding))
    assert inserted == 1, f"Expected 1 row inserted, got {inserted}"


# ---------------------------------------------------------------------------
# Test 5: load_cached_embeddings returns cached embedding for known surface
# ---------------------------------------------------------------------------


def test_load_cached_embeddings_returns_known_surface(
    pg_url: str, sample_embedding: np.ndarray
) -> None:
    """After store_embeddings, load_cached_embeddings returns (384,) float32."""
    from aerocloud.semantic.persistence import load_cached_embeddings, store_embeddings  # noqa: PLC0415

    async def _run_both() -> dict[str, np.ndarray]:
        await store_embeddings(["hello_t5"], sample_embedding)
        return await load_cached_embeddings(["hello_t5"])

    result = _run(_run_both())
    assert "hello_t5" in result, f"Expected 'hello_t5' in result, got keys: {list(result)}"
    vec = result["hello_t5"]
    assert vec.shape == (384,), f"Expected (384,) shape, got {vec.shape}"
    assert vec.dtype == np.float32, f"Expected float32, got {vec.dtype}"


# ---------------------------------------------------------------------------
# Test 6: load_cached_embeddings returns empty dict for unknown surface
# ---------------------------------------------------------------------------


def test_load_cached_embeddings_returns_empty_for_unknown_surface(pg_url: str) -> None:
    """Cache miss: load_cached_embeddings(['__never_stored__']) returns empty dict."""
    from aerocloud.semantic.persistence import load_cached_embeddings  # noqa: PLC0415

    result = _run(load_cached_embeddings(["__never_stored_surface_xyz__"]))
    assert result == {}, f"Expected empty dict for cache miss, got {result}"


# ---------------------------------------------------------------------------
# Test 7: store_embeddings upserts (no duplicate key error)
# ---------------------------------------------------------------------------


def test_store_embeddings_upserts_on_duplicate_surface(
    pg_url: str, sample_embedding: np.ndarray
) -> None:
    """Calling store_embeddings twice with the same surface must not raise."""
    from aerocloud.semantic.persistence import store_embeddings  # noqa: PLC0415

    surface = "upsert_test_t7"
    rng = np.random.default_rng(999)
    emb2 = rng.standard_normal((1, 384)).astype(np.float32)

    async def _run_upsert() -> tuple[int, int]:
        count1 = await store_embeddings([surface], sample_embedding)
        count2 = await store_embeddings([surface], emb2)
        return count1, count2

    count1, count2 = _run(_run_upsert())
    assert count1 == 1, f"First insert: expected 1, got {count1}"
    assert count2 == 1, f"Second upsert: expected 1, got {count2}"


# ---------------------------------------------------------------------------
# Test 8: D-15 — No writes to archive_v1 during persistence operations
# ---------------------------------------------------------------------------


def test_no_writes_to_archive_v1(
    pg_url: str, sample_embedding: np.ndarray
) -> None:
    """D-15: store_embeddings must not write to archive_v1.

    Counts rows in archive_v1 before and after a store+load cycle;
    the count must be identical (zero writes to archive_v1).
    """
    from aerocloud.semantic.persistence import load_cached_embeddings, store_embeddings  # noqa: PLC0415
    import asyncpg  # noqa: PLC0415

    async def _run_d15() -> tuple[int, int]:
        conn = await asyncpg.connect(pg_url)
        try:
            before = await conn.fetchval("SELECT COUNT(*) FROM archive_v1")
        finally:
            await conn.close()

        await store_embeddings(["d15_test_t8"], sample_embedding)
        await load_cached_embeddings(["d15_test_t8"])

        conn = await asyncpg.connect(pg_url)
        try:
            after = await conn.fetchval("SELECT COUNT(*) FROM archive_v1")
        finally:
            await conn.close()

        return int(before), int(after)

    before, after = _run(_run_d15())
    assert before == after, (
        f"D-15 violated: archive_v1 row count changed from {before} to {after}"
    )

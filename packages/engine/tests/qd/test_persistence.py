"""Tests for archive persistence: flush_batch + load_all (Plan 09-03, Task 2).

TDD RED phase: all tests are written first and reference the NOT-YET-IMPLEMENTED
module `aerocloud.outer_loop.persistence`.

Behaviour specification (from 09-03-PLAN.md):
  - Test 1: params_to_bytes produces bytes; bytes_to_params roundtrips correctly
  - Test 2: flush_batch inserts entries with ON CONFLICT upsert
  - Test 3: flush_batch only updates when EXCLUDED.fitness > existing fitness
  - Test 4: load_all returns list of (bin_id, fitness, measures, solution) tuples
  - Test 5: empty archive loads correctly (no rows)
  - Test 6: safetensors serialization requires CPU contiguous tensor (Pitfall 6)

Security (T-09-05):
  - All SQL uses $N parameterized placeholders — no string interpolation.
  - DSN is never logged (T-09-07).

Mock strategy:
  - asyncpg.connect() is mocked via unittest.mock.AsyncMock.
  - No real PostgreSQL connection is made in these unit tests.
  - Integration tests with a real DB are deferred to Plan 05.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
import torch

from aerocloud.models.archive import BehaviorDescriptor
from aerocloud.outer_loop.models import QualityMetrics, QualityWeights
from aerocloud.outer_loop.persistence import (
    ArchiveFlushEntry,
    ArchivePersistence,
    bytes_to_params,
    params_to_bytes,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_DSN = "postgresql://user:pass@localhost:5432/aerocloud_test"

_SAMPLE_BD = BehaviorDescriptor(
    shape_fidelity=0.8,
    rotation_ratio=0.2,
    symmetry=0.6,
    semantic_clustering=0.7,
)

_SAMPLE_QUALITY = QualityMetrics(
    layout_coverage=0.75,
    layout_uniformity=0.6,
    space_saving=0.5,
    compactness=0.4,
    aspect_ratio=0.9,
    realized_adjacencies=0.3,
    distortion_score=0.8,
)


def _make_params(n_words: int = 5) -> torch.Tensor:
    """Return a small (n_words, 4) CPU float32 tensor."""
    return torch.randn(n_words, 4)


def _make_descriptor_vec() -> np.ndarray:
    """Return a 384-dim float32 numpy descriptor."""
    return np.random.default_rng(0).random(384).astype(np.float32)


def _make_flush_entry(bin_id: str = "bin_0001", fitness: float = 0.85) -> ArchiveFlushEntry:
    params = _make_params()
    return ArchiveFlushEntry(
        bin_id=bin_id,
        descriptor_vec=_make_descriptor_vec(),
        fitness=fitness,
        metadata={"layout_id": "test"},
        behavior_descriptor=_SAMPLE_BD,
        params_bytes=params_to_bytes(params),
        quality_metrics_json=_SAMPLE_QUALITY.model_dump(),
    )


# ---------------------------------------------------------------------------
# Test 1: params_to_bytes / bytes_to_params roundtrip
# ---------------------------------------------------------------------------


class TestParamsSerialization:
    """Test 1 — safetensors serialization helper functions."""

    def test_params_to_bytes_returns_bytes(self) -> None:
        """params_to_bytes must produce a bytes object, not a file path."""
        params = _make_params(n_words=10)
        result = params_to_bytes(params)
        assert isinstance(result, bytes), "params_to_bytes must return bytes"
        assert len(result) > 0, "Serialized bytes must not be empty"

    def test_bytes_to_params_roundtrip(self) -> None:
        """bytes_to_params(params_to_bytes(t)) must reproduce the original tensor."""
        params = _make_params(n_words=8)
        serialized = params_to_bytes(params)
        restored = bytes_to_params(serialized)
        # Shape must be preserved
        assert restored.shape == params.shape, (
            f"Shape mismatch: expected {params.shape}, got {restored.shape}"
        )
        # Values must be numerically close (float32 precision)
        assert torch.allclose(params.cpu(), restored.cpu(), atol=1e-6), (
            "Roundtrip values do not match"
        )

    def test_bytes_to_params_returns_tensor(self) -> None:
        """bytes_to_params must return a torch.Tensor."""
        params = _make_params()
        result = bytes_to_params(params_to_bytes(params))
        assert isinstance(result, torch.Tensor)

    def test_params_to_bytes_handles_non_contiguous(self) -> None:
        """params_to_bytes must work even when the input tensor is non-contiguous."""
        # Transpose creates a non-contiguous tensor
        params = _make_params(n_words=6).T  # shape (4, 6) — non-contiguous after T
        # We test with a valid (n, 4) that was sliced (non-contiguous)
        params_nc = _make_params(n_words=10)[::2]  # stride-2 slice → non-contiguous
        assert not params_nc.is_contiguous()
        result = params_to_bytes(params_nc)
        assert isinstance(result, bytes) and len(result) > 0

    def test_params_to_bytes_not_pickle(self) -> None:
        """Serialized bytes must NOT start with the pickle magic bytes (0x80 0x0N)."""
        params = _make_params()
        data = params_to_bytes(params)
        # pickle magic: first byte is 0x80
        assert data[0] != 0x80, "params_to_bytes must NOT use pickle"


# ---------------------------------------------------------------------------
# Test 2: flush_batch inserts with ON CONFLICT upsert
# ---------------------------------------------------------------------------


class TestFlushBatch:
    """Test 2 — flush_batch sends the correct upsert SQL via asyncpg."""

    def test_flush_batch_calls_execute(self) -> None:
        """flush_batch must call conn.execute at least once per entry."""
        entry = _make_flush_entry()
        persistence = ArchivePersistence(dsn=_SAMPLE_DSN)

        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_conn)

        with patch("asyncpg.connect", return_value=mock_conn):
            result = asyncio.get_event_loop().run_until_complete(
                persistence.flush_batch([entry])
            )

        mock_conn.execute.assert_called()
        assert isinstance(result, int), "flush_batch must return an int (row count)"

    def test_flush_batch_sql_contains_on_conflict(self) -> None:
        """The SQL sent to asyncpg must contain ON CONFLICT."""
        entry = _make_flush_entry()
        persistence = ArchivePersistence(dsn=_SAMPLE_DSN)

        executed_sqls: list[str] = []

        async def capture_execute(sql: str, *args: Any) -> None:  # noqa: ANN401
            executed_sqls.append(sql)

        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_conn.execute.side_effect = capture_execute

        mock_txn = AsyncMock()
        mock_txn.__aenter__ = AsyncMock(return_value=mock_txn)
        mock_txn.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_txn)

        with patch("asyncpg.connect", return_value=mock_conn):
            asyncio.get_event_loop().run_until_complete(persistence.flush_batch([entry]))

        assert len(executed_sqls) >= 1, "At least one SQL execute call expected"
        combined = "\n".join(executed_sqls)
        assert "ON CONFLICT" in combined, f"SQL must contain ON CONFLICT; got:\n{combined}"

    def test_flush_batch_sql_contains_bin_id(self) -> None:
        """The upsert SQL must reference bin_id as the conflict target."""
        entry = _make_flush_entry(bin_id="test_bin")
        persistence = ArchivePersistence(dsn=_SAMPLE_DSN)

        executed_sqls: list[str] = []

        async def capture_execute(sql: str, *args: Any) -> None:  # noqa: ANN401
            executed_sqls.append(sql)

        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_conn.execute.side_effect = capture_execute

        mock_txn = AsyncMock()
        mock_txn.__aenter__ = AsyncMock(return_value=mock_txn)
        mock_txn.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_txn)

        with patch("asyncpg.connect", return_value=mock_conn):
            asyncio.get_event_loop().run_until_complete(persistence.flush_batch([entry]))

        combined = "\n".join(executed_sqls)
        assert "bin_id" in combined, f"SQL must reference bin_id; got:\n{combined}"


# ---------------------------------------------------------------------------
# Test 3: flush_batch only updates when EXCLUDED.fitness > archive.fitness
# ---------------------------------------------------------------------------


class TestFlushBatchFitnessGuard:
    """Test 3 — fitness guard WHERE clause."""

    def test_flush_batch_sql_contains_fitness_guard(self) -> None:
        """SQL must contain WHERE EXCLUDED.fitness > archive_v1.fitness."""
        entry = _make_flush_entry(fitness=0.9)
        persistence = ArchivePersistence(dsn=_SAMPLE_DSN)

        executed_sqls: list[str] = []

        async def capture_execute(sql: str, *args: Any) -> None:  # noqa: ANN401
            executed_sqls.append(sql)

        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_conn.execute.side_effect = capture_execute

        mock_txn = AsyncMock()
        mock_txn.__aenter__ = AsyncMock(return_value=mock_txn)
        mock_txn.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_txn)

        with patch("asyncpg.connect", return_value=mock_conn):
            asyncio.get_event_loop().run_until_complete(persistence.flush_batch([entry]))

        combined = "\n".join(executed_sqls)
        assert "EXCLUDED.fitness" in combined, (
            f"SQL must include EXCLUDED.fitness fitness guard; got:\n{combined}"
        )
        assert "archive_v1.fitness" in combined, (
            f"SQL must reference archive_v1.fitness; got:\n{combined}"
        )

    def test_flush_batch_empty_list(self) -> None:
        """flush_batch with empty entries list should return 0 without SQL calls."""
        persistence = ArchivePersistence(dsn=_SAMPLE_DSN)

        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)

        mock_txn = AsyncMock()
        mock_txn.__aenter__ = AsyncMock(return_value=mock_txn)
        mock_txn.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_txn)

        with patch("asyncpg.connect", return_value=mock_conn):
            result = asyncio.get_event_loop().run_until_complete(
                persistence.flush_batch([])
            )

        assert result == 0, "flush_batch([]) must return 0"


# ---------------------------------------------------------------------------
# Test 4: load_all returns list of (bin_id, fitness, measures, solution) tuples
# ---------------------------------------------------------------------------


class TestLoadAll:
    """Test 4 — load_all returns correctly shaped tuples."""

    def test_load_all_returns_list_of_tuples(self) -> None:
        """load_all must return a list of 4-tuples."""
        params = _make_params(n_words=5)
        params_bytes = params_to_bytes(params)

        mock_rows = [
            {
                "bin_id": "bin_0001",
                "fitness": 0.85,
                "shape_fidelity": 0.8,
                "rotation_ratio": 0.2,
                "symmetry": 0.6,
                "semantic_clustering": 0.7,
                "params_blob": params_bytes,
            }
        ]

        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_conn.fetch = AsyncMock(return_value=mock_rows)

        persistence = ArchivePersistence(dsn=_SAMPLE_DSN)

        with patch("asyncpg.connect", return_value=mock_conn):
            result = asyncio.get_event_loop().run_until_complete(persistence.load_all())

        assert isinstance(result, list), "load_all must return a list"
        assert len(result) == 1
        bin_id, fitness, measures, solution = result[0]
        assert bin_id == "bin_0001"
        assert fitness == pytest.approx(0.85)
        assert isinstance(measures, np.ndarray)
        assert measures.shape == (4,), f"measures must be (4,), got {measures.shape}"
        assert isinstance(solution, np.ndarray)

    def test_load_all_measures_correct_values(self) -> None:
        """load_all must assemble measures_4d from the 4 BD scalar columns."""
        params = _make_params(n_words=3)
        params_bytes = params_to_bytes(params)

        mock_rows = [
            {
                "bin_id": "test",
                "fitness": 0.5,
                "shape_fidelity": 0.1,
                "rotation_ratio": 0.2,
                "symmetry": 0.3,
                "semantic_clustering": 0.4,
                "params_blob": params_bytes,
            }
        ]

        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_conn.fetch = AsyncMock(return_value=mock_rows)

        persistence = ArchivePersistence(dsn=_SAMPLE_DSN)

        with patch("asyncpg.connect", return_value=mock_conn):
            result = asyncio.get_event_loop().run_until_complete(persistence.load_all())

        _, _, measures, _ = result[0]
        np.testing.assert_allclose(measures, [0.1, 0.2, 0.3, 0.4], atol=1e-6)


# ---------------------------------------------------------------------------
# Test 5: empty archive loads correctly
# ---------------------------------------------------------------------------


class TestLoadAllEmpty:
    """Test 5 — load_all on an empty table returns []."""

    def test_load_all_empty_archive(self) -> None:
        """load_all with no DB rows must return an empty list."""
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_conn.fetch = AsyncMock(return_value=[])

        persistence = ArchivePersistence(dsn=_SAMPLE_DSN)

        with patch("asyncpg.connect", return_value=mock_conn):
            result = asyncio.get_event_loop().run_until_complete(persistence.load_all())

        assert result == []


# ---------------------------------------------------------------------------
# Test 6: safetensors serialization with non-contiguous tensors (Pitfall 6)
# ---------------------------------------------------------------------------


class TestSafetensorsContiguity:
    """Test 6 — safetensors requires CPU contiguous tensor (Pitfall 6)."""

    def test_params_to_bytes_contiguous_internally(self) -> None:
        """params_to_bytes must call .contiguous() internally to avoid safetensors error."""
        # Non-contiguous tensor (transposed): safetensors would fail without .contiguous()
        params_nc = _make_params(n_words=10)[::2]  # stride-2, non-contiguous
        assert not params_nc.is_contiguous()
        # If contiguous() is NOT called, safetensors raises RuntimeError.
        # If correctly implemented, this must succeed.
        result = params_to_bytes(params_nc)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_bytes_to_params_roundtrip_non_contiguous_source(self) -> None:
        """Full roundtrip starting from a non-contiguous source tensor."""
        params_nc = _make_params(n_words=12)[1::2]  # non-contiguous slice
        assert not params_nc.is_contiguous()
        serialized = params_to_bytes(params_nc)
        restored = bytes_to_params(serialized)
        # Restored must match the non-contiguous original
        assert restored.shape == params_nc.shape
        assert torch.allclose(params_nc.cpu().contiguous(), restored.cpu(), atol=1e-6)


# ---------------------------------------------------------------------------
# ArchiveFlushEntry model validation
# ---------------------------------------------------------------------------


class TestArchiveFlushEntry:
    """Structural validation of ArchiveFlushEntry."""

    def test_flush_entry_rejects_unknown_fields(self) -> None:
        """ArchiveFlushEntry must reject unknown fields (AeroCloudBase pattern)."""
        from pydantic import ValidationError

        params = _make_params()
        with pytest.raises(ValidationError):
            ArchiveFlushEntry(  # type: ignore[call-arg]
                bin_id="bin_x",
                descriptor_vec=_make_descriptor_vec(),
                fitness=0.5,
                metadata={},
                behavior_descriptor=_SAMPLE_BD,
                params_bytes=params_to_bytes(params),
                quality_metrics_json={},
                unknown_extra_field="should_fail",
            )

    def test_flush_entry_construction(self) -> None:
        """ArchiveFlushEntry can be constructed with correct fields."""
        params = _make_params()
        entry = ArchiveFlushEntry(
            bin_id="bin_y",
            descriptor_vec=_make_descriptor_vec(),
            fitness=0.7,
            metadata={"key": "value"},
            behavior_descriptor=_SAMPLE_BD,
            params_bytes=params_to_bytes(params),
            quality_metrics_json=_SAMPLE_QUALITY.model_dump(),
        )
        assert entry.bin_id == "bin_y"
        assert entry.fitness == pytest.approx(0.7)

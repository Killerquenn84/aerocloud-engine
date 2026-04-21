"""Unit tests for ReplayLogger (TDD RED phase).

Given: ReplayLogger asyncpg class persisting self-play data
When: Calling insert_run, insert_event, finalize_run, load_previous_descriptor_histogram
Then: Correct SQL with $N parameters, correct calls to asyncpg, no string interpolation

Security tests (T-10-02):
    - All SQL constants must use $N positional parameters
    - No f-string or %-string interpolation of data into SQL
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from aerocloud.self_play.models import SelfPlayEvent
from aerocloud.self_play.replay import (
    _FINALIZE_RUN_SQL,
    _INSERT_EVENT_SQL,
    _INSERT_RUN_SQL,
    _LOAD_PREV_HISTOGRAM_SQL,
    _STORE_HISTOGRAM_SQL,
    ReplayLogger,
)

# ---------------------------------------------------------------------------
# Test ReplayLogger.__init__
# ---------------------------------------------------------------------------


class TestReplayLoggerInit:
    """Tests for ReplayLogger initialization."""

    def test_init_stores_dsn(self) -> None:
        dsn = "postgres://user:pass@localhost:5432/testdb"
        logger = ReplayLogger(dsn=dsn)
        assert logger._dsn == dsn

    def test_dsn_not_exposed_via_repr(self) -> None:
        """DSN should not appear in repr (T-10-01: no info disclosure)."""
        dsn = "postgres://user:secret@localhost:5432/testdb"
        logger = ReplayLogger(dsn=dsn)
        # ReplayLogger has no custom __repr__; default shows class name + id, not dsn
        assert "secret" not in repr(logger)


# ---------------------------------------------------------------------------
# Test SQL security: parameterized queries (T-10-02)
# ---------------------------------------------------------------------------


class TestSQLParameterization:
    """Verify all SQL uses $N positional parameters, not string interpolation."""

    _INTERPOLATION_PATTERN = re.compile(
        r"(%s|%d|%f|f\"|\bformat\b|\+.*sql\b)",
        re.IGNORECASE,
    )

    def _has_no_string_interpolation(self, sql: str) -> bool:
        """Return True if SQL contains no evidence of string interpolation."""
        return self._INTERPOLATION_PATTERN.search(sql) is None

    def _has_positional_params(self, sql: str) -> bool:
        """Return True if SQL uses $N positional parameters."""
        return bool(re.search(r"\$\d+", sql))

    def test_insert_run_uses_positional_params(self) -> None:
        assert self._has_positional_params(_INSERT_RUN_SQL)
        assert self._has_no_string_interpolation(_INSERT_RUN_SQL)

    def test_insert_event_uses_positional_params(self) -> None:
        assert self._has_positional_params(_INSERT_EVENT_SQL)
        assert self._has_no_string_interpolation(_INSERT_EVENT_SQL)

    def test_finalize_run_uses_positional_params(self) -> None:
        assert self._has_positional_params(_FINALIZE_RUN_SQL)
        assert self._has_no_string_interpolation(_FINALIZE_RUN_SQL)

    def test_store_histogram_uses_positional_params(self) -> None:
        assert self._has_positional_params(_STORE_HISTOGRAM_SQL)
        assert self._has_no_string_interpolation(_STORE_HISTOGRAM_SQL)

    def test_load_histogram_has_no_params(self) -> None:
        """Load histogram has no user data — safe without params."""
        assert self._has_no_string_interpolation(_LOAD_PREV_HISTOGRAM_SQL)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_conn(fetchrow_result: Any = None) -> MagicMock:
    """Create a mock asyncpg connection with execute/fetchrow as AsyncMocks."""
    conn = MagicMock()
    conn.execute = AsyncMock(return_value=None)
    conn.fetchrow = AsyncMock(return_value=fetchrow_result)
    conn.close = AsyncMock(return_value=None)
    return conn


def _make_event(
    iteration: int = 1,
    parent_bin_ids: list[str] | None = None,
    mutation_type: str = "sigma_xy",
    fitness_before: float | None = 0.8,
    fitness_after: float = 0.85,
    accepted: bool = True,
    reject_reason: str = "",
) -> SelfPlayEvent:
    return SelfPlayEvent(
        iteration=iteration,
        parent_bin_ids=parent_bin_ids or ["bin-001"],
        mutation_type=mutation_type,
        fitness_before=fitness_before,
        fitness_after=fitness_after,
        accepted=accepted,
        reject_reason=reject_reason,
    )


# ---------------------------------------------------------------------------
# Test insert_run
# ---------------------------------------------------------------------------


class TestInsertRun:
    """Tests for ReplayLogger.insert_run."""

    @pytest.mark.asyncio
    async def test_insert_run_calls_execute(self) -> None:
        run_id = uuid.uuid4()
        config = {"n_iterations": 1000}
        mock_conn = _make_mock_conn()

        with patch("asyncpg.connect", new=AsyncMock(return_value=mock_conn)):
            logger = ReplayLogger(dsn="postgres://test")
            await logger.insert_run(run_id=run_id, config=config)

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        # First positional arg is the SQL string
        sql_called = call_args[0][0]
        assert "self_play_runs" in sql_called
        # run_id passed as string
        assert str(run_id) in call_args[0][1]

    @pytest.mark.asyncio
    async def test_insert_run_closes_connection(self) -> None:
        run_id = uuid.uuid4()
        mock_conn = _make_mock_conn()

        with patch("asyncpg.connect", new=AsyncMock(return_value=mock_conn)):
            logger = ReplayLogger(dsn="postgres://test")
            await logger.insert_run(run_id=run_id, config={})

        mock_conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert_run_closes_on_exception(self) -> None:
        """Connection must be closed even when execute raises."""
        run_id = uuid.uuid4()
        mock_conn = _make_mock_conn()
        mock_conn.execute = AsyncMock(side_effect=RuntimeError("db error"))

        with patch("asyncpg.connect", new=AsyncMock(return_value=mock_conn)):
            logger = ReplayLogger(dsn="postgres://test")
            with pytest.raises(RuntimeError):
                await logger.insert_run(run_id=run_id, config={})

        mock_conn.close.assert_called_once()


# ---------------------------------------------------------------------------
# Test insert_event
# ---------------------------------------------------------------------------


class TestInsertEvent:
    """Tests for ReplayLogger.insert_event."""

    @pytest.mark.asyncio
    async def test_insert_event_calls_execute(self) -> None:
        run_id = uuid.uuid4()
        event = _make_event()
        mock_conn = _make_mock_conn()

        with patch("asyncpg.connect", new=AsyncMock(return_value=mock_conn)):
            logger = ReplayLogger(dsn="postgres://test")
            await logger.insert_event(run_id=run_id, event=event)

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args[0]
        assert "self_play_events" in call_args[0]
        # run_id is first data arg
        assert str(run_id) == call_args[1]
        # iteration is second data arg
        assert event.iteration == call_args[2]

    @pytest.mark.asyncio
    async def test_insert_event_passes_all_fields(self) -> None:
        run_id = uuid.uuid4()
        event = _make_event(
            iteration=99,
            parent_bin_ids=["bin-A", "bin-B"],
            mutation_type="crossover",
            fitness_before=0.7,
            fitness_after=0.9,
            accepted=True,
            reject_reason="",
        )
        mock_conn = _make_mock_conn()

        with patch("asyncpg.connect", new=AsyncMock(return_value=mock_conn)):
            logger = ReplayLogger(dsn="postgres://test")
            await logger.insert_event(run_id=run_id, event=event)

        args = mock_conn.execute.call_args[0]
        # positional order: sql, run_id, iteration, parent_bin_ids, mutation_type,
        # fitness_before, fitness_after, accepted, reject_reason
        assert args[2] == 99
        assert args[3] == ["bin-A", "bin-B"]
        assert args[4] == "crossover"
        assert args[5] == pytest.approx(0.7)
        assert args[6] == pytest.approx(0.9)
        assert args[7] is True
        assert args[8] == ""

    @pytest.mark.asyncio
    async def test_insert_event_closes_connection(self) -> None:
        run_id = uuid.uuid4()
        mock_conn = _make_mock_conn()

        with patch("asyncpg.connect", new=AsyncMock(return_value=mock_conn)):
            logger = ReplayLogger(dsn="postgres://test")
            await logger.insert_event(run_id=run_id, event=_make_event())

        mock_conn.close.assert_called_once()


# ---------------------------------------------------------------------------
# Test finalize_run
# ---------------------------------------------------------------------------


class TestFinalizeRun:
    """Tests for ReplayLogger.finalize_run."""

    @pytest.mark.asyncio
    async def test_finalize_run_calls_execute(self) -> None:
        run_id = uuid.uuid4()
        mock_conn = _make_mock_conn()

        with patch("asyncpg.connect", new=AsyncMock(return_value=mock_conn)):
            logger = ReplayLogger(dsn="postgres://test")
            await logger.finalize_run(
                run_id=run_id,
                n_iterations=1000,
                n_accepted=500,
                n_rejected=500,
                kl_divergence=0.123,
            )

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args[0]
        assert "self_play_runs" in call_args[0]
        assert str(run_id) == call_args[1]
        assert call_args[2] == 1000
        assert call_args[3] == 500
        assert call_args[4] == 500
        assert call_args[5] == pytest.approx(0.123)

    @pytest.mark.asyncio
    async def test_finalize_run_kl_none_passed(self) -> None:
        run_id = uuid.uuid4()
        mock_conn = _make_mock_conn()

        with patch("asyncpg.connect", new=AsyncMock(return_value=mock_conn)):
            logger = ReplayLogger(dsn="postgres://test")
            await logger.finalize_run(
                run_id=run_id,
                n_iterations=500,
                n_accepted=250,
                n_rejected=250,
                kl_divergence=None,
            )

        call_args = mock_conn.execute.call_args[0]
        assert call_args[5] is None

    @pytest.mark.asyncio
    async def test_finalize_run_closes_connection(self) -> None:
        run_id = uuid.uuid4()
        mock_conn = _make_mock_conn()

        with patch("asyncpg.connect", new=AsyncMock(return_value=mock_conn)):
            logger = ReplayLogger(dsn="postgres://test")
            await logger.finalize_run(
                run_id=run_id,
                n_iterations=0,
                n_accepted=0,
                n_rejected=0,
                kl_divergence=None,
            )

        mock_conn.close.assert_called_once()


# ---------------------------------------------------------------------------
# Test load_previous_descriptor_histogram
# ---------------------------------------------------------------------------


class TestLoadPreviousDescriptorHistogram:
    """Tests for ReplayLogger.load_previous_descriptor_histogram."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_rows(self) -> None:
        """Returns None when fetchrow returns None (no prior run with histogram)."""
        mock_conn = _make_mock_conn(fetchrow_result=None)

        with patch("asyncpg.connect", new=AsyncMock(return_value=mock_conn)):
            logger = ReplayLogger(dsn="postgres://test")
            result = await logger.load_previous_descriptor_histogram()

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_histogram_column_null(self) -> None:
        """Returns None when row exists but histogram key is NULL."""
        mock_row = {"histogram": None}
        mock_conn = _make_mock_conn(fetchrow_result=mock_row)

        with patch("asyncpg.connect", new=AsyncMock(return_value=mock_conn)):
            logger = ReplayLogger(dsn="postgres://test")
            result = await logger.load_previous_descriptor_histogram()

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_ndarray_when_histogram_present(self) -> None:
        """Returns numpy array when histogram data found."""
        histogram_data = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        mock_row = {"histogram": json.dumps(histogram_data)}
        mock_conn = _make_mock_conn(fetchrow_result=mock_row)

        with patch("asyncpg.connect", new=AsyncMock(return_value=mock_conn)):
            logger = ReplayLogger(dsn="postgres://test")
            result = await logger.load_previous_descriptor_histogram()

        assert result is not None
        assert isinstance(result, np.ndarray)
        assert result.shape == (2, 3)

    @pytest.mark.asyncio
    async def test_closes_connection(self) -> None:
        mock_conn = _make_mock_conn(fetchrow_result=None)

        with patch("asyncpg.connect", new=AsyncMock(return_value=mock_conn)):
            logger = ReplayLogger(dsn="postgres://test")
            await logger.load_previous_descriptor_histogram()

        mock_conn.close.assert_called_once()

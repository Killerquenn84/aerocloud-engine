"""Sprint P26 — engine-level robustness E2E (scenarios 1, 2, 3, 4, 14).

These tests drive ``MockupEngine.render`` end-to-end through the validation
gate. They do NOT need a real PSD past the gate, because the gate is what
we're proving stops bad input.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pytest

from aerocloud_worker.mockup.engine import MockupEngine
from aerocloud_worker.mockup.exceptions import (
    InvalidDesignError,
    InvalidPSDError,
    PSDTooLargeError,
)


def test_corrupt_psd_rejected_before_parse(
    corrupt_psd_path: Path, valid_design_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    engine = MockupEngine(cache={})
    with caplog.at_level(logging.WARNING), pytest.raises(InvalidPSDError):
        engine.render(corrupt_psd_path, valid_design_path, task_id="t-corrupt")

    # Scenario 14: structured fail-log emitted with task_id.
    fail_records = [r for r in caplog.records if r.message == "mockup.validate.fail"]
    assert fail_records, "expected mockup.validate.fail log"
    rec = fail_records[0]
    assert getattr(rec, "task_id", None) == "t-corrupt"
    assert getattr(rec, "error_type", None) == "InvalidPSDError"


def test_huge_psd_rejected_before_parse(
    huge_psd_path: Path, valid_design_path: Path
) -> None:
    engine = MockupEngine(cache={})
    with pytest.raises(PSDTooLargeError):
        engine.render(huge_psd_path, valid_design_path)


def test_animated_design_rejected(
    minimal_valid_psd_path: Path,
    animated_gif_path: Path,
) -> None:
    engine = MockupEngine(cache={})
    with pytest.raises(InvalidDesignError):
        engine.render(minimal_valid_psd_path, animated_gif_path)


def test_render_start_log_emitted(
    corrupt_psd_path: Path,
    valid_design_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Scenario 14: a start-event is logged before validation runs."""
    engine = MockupEngine(cache={})
    with caplog.at_level(logging.INFO), pytest.raises(InvalidPSDError):
        engine.render(corrupt_psd_path, valid_design_path, task_id="t-start")

    starts = [r for r in caplog.records if r.message == "mockup.render.start"]
    assert starts, "expected mockup.render.start log"
    assert getattr(starts[0], "task_id", None) == "t-start"

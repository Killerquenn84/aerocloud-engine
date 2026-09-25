"""Release gate integration tests (PROD-23, D-27).

Orchestrates all release gate checks as a single pytest class:
- All unit/integration tests green (excluding load tests)
- mypy --strict clean across all engine source
- ruff check + ruff format clean
- Golden-image SSIM >= 0.95 for all 4 fixtures

Run selectively with:
    uv run pytest packages/engine/tests/integration/test_release_gate.py -m release_gate -v

This test is intentionally slow (it runs the full test suite + type check + lint).
It is excluded from the default test run via the ``release_gate`` marker.

References:
    - PROD-23: Release gate — final v1 exit criterion
    - D-27: all tests green + P99 within budget + SSIM > 0.95 + 3-KI review approved
    - CLAUDE.md §12: MVP Production-Hardening (85 items, 5 gates)
    - T-12-09-01: Release gate integrity — cannot be bypassed without git-tracked test
      modification; runs full suite including security validators.
"""

from __future__ import annotations

import subprocess

import pytest

# Root of the repository — used to construct absolute paths for subprocess calls.
# Using __file__ navigation is more reliable than os.getcwd() which can vary by
# CI working directory.
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent
# packages/engine/tests/integration → packages/engine → packages → repo root (3 levels up)
# Verify: repo root should contain pyproject.toml
_REPO_PYPROJECT = _REPO_ROOT / "pyproject.toml"


def _repo_root() -> Path:
    """Return the monorepo root directory.

    Walks up from this file until a directory containing pyproject.toml is found.
    Raises RuntimeError if not found within 10 levels (prevents infinite walk).
    """
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "pyproject.toml").exists() and (current / "packages").exists():
            return current
        current = current.parent
    raise RuntimeError(
        f"Could not locate monorepo root from {Path(__file__).resolve()}. "
        "Expected to find pyproject.toml + packages/ directory."
    )


# Resolve once at module import — fast, deterministic.
REPO_ROOT = _repo_root()


@pytest.mark.release_gate
class TestReleaseGate:
    """Full release gate validation suite for AeroCloud Engine v1.

    Each test method corresponds to one PROD-23 exit criterion.
    All must pass before tagging v1.0.0.
    """

    def test_all_unit_tests_green(self) -> None:
        """Assert all engine unit/integration/regression tests pass (excluding load tests).

        Runs the full pytest suite under packages/engine/tests/, excluding the
        load test directory (load tests require a live server — see test_load_concurrent.py).

        Timeout: 600s to allow for slow CI machines without CUDA.
        """
        result = subprocess.run(
            [
                "uv",
                "run",
                "pytest",
                "packages/engine/tests/",
                "-x",
                "--ignore=packages/engine/tests/load",
                "-q",
            ],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"Unit tests failed:\n{result.stdout}\n{result.stderr}"
        )

    def test_mypy_strict_clean(self) -> None:
        """Assert mypy --strict reports zero errors across all engine source.

        Covers: packages/engine/src/aerocloud/ and apps/api/src/aerocloud_api/
        and apps/worker/src/aerocloud_worker/.

        mypy is the primary type-safety gate for the engine core. A single
        untyped return or missing annotation is a blocker.

        Timeout: 300s (mypy caches on second run; first run can be slow).
        """
        result = subprocess.run(
            [
                "uv",
                "run",
                "mypy",
                "--strict",
                "packages/engine/src/aerocloud/",
                "apps/api/src/aerocloud_api/",
                "apps/worker/src/aerocloud_worker/",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"mypy errors:\n{result.stdout}\n{result.stderr}"

    def test_ruff_check_clean(self) -> None:
        """Assert ruff lint check reports zero violations across all source dirs.

        Configured in root pyproject.toml [tool.ruff.lint] — enforces:
        E/F/I/N/UP/B/A/C4/T20/RET/SIM/ARG/PTH/ERA/PL/RUF rule sets.

        Timeout: 120s.
        """
        result = subprocess.run(
            [
                "uv",
                "run",
                "ruff",
                "check",
                "packages/engine/src/",
                "apps/",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"ruff check errors:\n{result.stdout}\n{result.stderr}"

    def test_ruff_format_clean(self) -> None:
        """Assert ruff format --check reports no reformatting needed.

        Uses ruff as the sole formatter (no Black per CLAUDE.md — two formatters
        create friction). --check mode is non-destructive; fails if any file
        would be reformatted.

        Timeout: 120s.
        """
        result = subprocess.run(
            [
                "uv",
                "run",
                "ruff",
                "format",
                "--check",
                "packages/engine/src/",
                "apps/",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"ruff format violations:\n{result.stdout}\n{result.stderr}"
        )

    def test_golden_images_pass(self) -> None:
        """Assert golden-image SSIM >= 0.95 for all 4 fixtures (D-27).

        Runs the regression test suite which compares freshly-rendered output
        against committed golden PNGs using SSIM. All 4 fixtures (circle, square,
        star, crescent) must score >= 0.95.

        Skips gracefully if golden images have not been generated
        (test_golden_image.py handles individual skip per fixture).

        Timeout: 300s (CPU rendering — no CUDA required per PROJECT.md CPU fallback).
        """
        result = subprocess.run(
            [
                "uv",
                "run",
                "pytest",
                "packages/engine/tests/regression/test_golden_image.py",
                "-x",
                "-v",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"Golden image tests failed:\n{result.stdout}\n{result.stderr}"
        )

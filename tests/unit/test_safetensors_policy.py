"""Enforce safetensors policy — no `pickle.load` / `pickle.dump` in source.

This complements the regex scan in ``.github/workflows/ci-integrity.yml``.
Belt AND suspenders: test runs locally + in every CI Python job.

Rationale (Phase 1 CONTEXT.md D-06 + research/PITFALLS.md #16):
    Pickle deserialization is a remote code execution vector for untrusted
    model checkpoints. Use safetensors instead.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Source directories to scan
SCAN_ROOTS = [
    REPO_ROOT / "packages" / "engine" / "src",
    REPO_ROOT / "apps" / "api" / "src",
    REPO_ROOT / "apps" / "worker" / "src",
]

# Pickle patterns to reject
FORBIDDEN_PATTERNS = [
    re.compile(r"\bpickle\.(load|loads|dump|dumps)\b"),
    re.compile(r"^\s*import\s+pickle\b", re.MULTILINE),
    re.compile(r"^\s*from\s+pickle\s+import\b", re.MULTILINE),
]


def test_no_pickle_in_source() -> None:
    """Fail if any source file imports or calls pickle."""
    violations: list[tuple[Path, str]] = []
    for root in SCAN_ROOTS:
        if not root.is_dir():
            continue
        for py_file in root.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for pattern in FORBIDDEN_PATTERNS:
                match = pattern.search(content)
                if match:
                    violations.append((py_file.relative_to(REPO_ROOT), match.group(0)))

    assert not violations, (
        "Pickle usage detected in source — use safetensors instead:\n"
        + "\n".join(f"  {path}: {match}" for path, match in violations)
    )


def test_scan_roots_exist() -> None:
    """Smoke test: at least one of the scan roots must exist."""
    assert any(root.is_dir() for root in SCAN_ROOTS), "no source directories found"

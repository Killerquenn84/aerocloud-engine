---
phase: 09
slug: outer-loop-v1
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-18
---

# Phase 09 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + hypothesis |
| **Config file** | packages/engine/pyproject.toml [tool.pytest] |
| **Quick run command** | `uv run pytest packages/engine/tests/qd/ -x -q` |
| **Full suite command** | `uv run pytest packages/engine/tests/ -q --tb=short` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest packages/engine/tests/qd/ -x -q`
- **After every plan wave:** Run `uv run pytest packages/engine/tests/ -q --tb=short`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Wave 0 Requirements

- [ ] `packages/engine/tests/qd/` — test directory structure
- [ ] `packages/engine/tests/qd/conftest.py` — shared fixtures
- [ ] `ribs>=0.10.0` updated in pyproject.toml

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

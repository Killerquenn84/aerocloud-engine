---
phase: 05
slug: renderer-v1
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-12
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.0 + hypothesis 6.151.11 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` at repo root |
| **Quick run command** | `uv run pytest packages/engine/tests/renderer/ -x -q` |
| **Full suite command** | `uv run pytest packages/engine/tests/renderer/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest packages/engine/tests/renderer/ -x -q`
- **After every plan wave:** Run `uv run pytest packages/engine/tests/renderer/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | REND-03, REND-04 | — | N/A | unit | `uv run pytest packages/engine/tests/renderer/unit/test_sprites.py -x` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | REND-04 | — | N/A | unit | `uv run pytest packages/engine/tests/renderer/unit/test_font_registry.py -x` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 2 | REND-01, REND-02, REND-05 | — | N/A | unit | `uv run pytest packages/engine/tests/renderer/unit/test_affine.py packages/engine/tests/renderer/unit/test_compositing.py -x` | ❌ W0 | ⬜ pending |
| 05-03-01 | 03 | 3 | REND-06 | — | N/A | property + integration + determinism + memory | `uv run pytest packages/engine/tests/renderer/ -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/engine/tests/renderer/__init__.py` — test package init
- [ ] `packages/engine/tests/renderer/conftest.py` — shared fixtures (sprites, PlacementResult stub)
- [ ] `packages/engine/tests/renderer/unit/__init__.py` — unit test subpackage
- [ ] `packages/engine/tests/renderer/property/__init__.py` — property test subpackage
- [ ] `packages/engine/tests/renderer/integration/__init__.py` — integration test subpackage
- [ ] `packages/engine/tests/renderer/determinism/__init__.py` — determinism test subpackage
- [ ] `packages/engine/tests/renderer/memory/__init__.py` — memory test subpackage
- [ ] `psutil>=5.9.0` added to `packages/engine/pyproject.toml`

*All covered by Plan 05-01 Task 1.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

---
phase: 08
slug: semantic-vector-space
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-18
---

# Phase 08 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + hypothesis |
| **Config file** | packages/engine/pyproject.toml [tool.pytest] |
| **Quick run command** | `uv run pytest packages/engine/tests/semantic/ -x -q` |
| **Full suite command** | `uv run pytest packages/engine/tests/ -q --tb=short` |
| **Estimated runtime** | ~90 seconds (includes BERT model load) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest packages/engine/tests/semantic/ -x -q`
- **After every plan wave:** Run `uv run pytest packages/engine/tests/ -q --tb=short`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | SEM-01 | — | N/A | unit | `uv run pytest tests/semantic/unit/test_embeddings.py -x` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 1 | SEM-02 | — | N/A | unit | `uv run pytest tests/semantic/unit/test_warm_start.py -x` | ❌ W0 | ⬜ pending |
| 08-02-01 | 02 | 2 | SEM-03 | — | N/A | unit | `uv run pytest tests/semantic/unit/test_cosine.py -x` | ❌ W0 | ⬜ pending |
| 08-02-02 | 02 | 2 | SEM-04 | — | N/A | unit | `uv run pytest tests/semantic/unit/test_projection.py -x` | ❌ W0 | ⬜ pending |
| 08-03-01 | 03 | 3 | SEM-05,SEM-06 | — | N/A | unit | `uv run pytest tests/semantic/unit/test_sinkhorn.py -x` | ❌ W0 | ⬜ pending |
| 08-04-01 | 04 | 4 | SEM-07 | — | N/A | integration | `uv run pytest tests/semantic/integration/test_pgvector.py -x` | ❌ W0 | ⬜ pending |
| 08-05-01 | 05 | 5 | SEM-08 | — | N/A | integration | `uv run pytest tests/semantic/integration/test_warm_start_pipeline.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/engine/tests/semantic/` — test directory structure
- [ ] `packages/engine/tests/semantic/conftest.py` — shared fixtures (mock model, sample embeddings)
- [ ] `umap-learn>=0.5.0` added to pyproject.toml embeddings group
- [ ] `pgvector>=0.4.0` added to pyproject.toml embeddings group
- [ ] POT moved from nlp to embeddings group

*Existing infrastructure (pytest, hypothesis, mypy, ruff) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| BERT cold-start < 10s | SEM-02 | Hardware-dependent timing | Time `model.encode(["test"])` on VPS |
| pgvector HNSW recall ≥ 98% | SEM-07 | Requires populated DB | Insert 1000 vectors, query 100, measure recall |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

---
title: "Phase 1 Foundation — Discussion Log (3-AI audit trail)"
slug: 2026-04-07-phase-01-discussion-log
created: 2026-04-07
tags: [discussion, phase-1, foundation, audit-log]
source: mirrored from .planning/phases/01-foundation/01-DISCUSSION-LOG.md
---

# Phase 1: Foundation - Discussion Log (3-AI Consensus Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in `01-CONTEXT.md` — this log preserves the analysis.

**Date:** 2026-04-07
**Phase:** 01-foundation
**Mode:** assumptions + 3-AI consensus
**Participants:** Claude Code (orchestrator), Gemini CLI (researcher), Codex CLI (reviewer)

## Gray Areas Identified

1. Repository structure — how does Python engine coexist with existing TS wiki tooling?
2. uv workspace layout — single root pyproject.toml or per-package?
3. Docker base image choice + version pinning strategy
4. Determinism function location
5. CI pipeline tool + caching strategy
6. Font bundling (licensing, loading, memory)
7. Test directory layout
8. GPU smoke test gating

## 3-AI Discussion: Repository Structure (the biggest gray area)

### Claude Code Initial Position
Hybrid — keep TS wiki tools at root, add Python in `packages/engine/`. Minimal disruption to cron and wiki tooling.

### Gemini (Research)
Recommended Option B: Migration to `tools/wiki/`.
- Reason: cleaner polyglot monorepo
- `uv` ignores `package.json` — no technical conflict
- Global `set_seed()` in `packages/engine/src_py/aerocloud/utils/determinism.py`
- CI: separated jobs with paths-filter, `astral-sh/setup-uv` for caching
- Source quoted: "Ein sauberer Monorepo-Ansatz (Polyglot) profitiert davon, wenn der Root nur Orchestrierung enthält."

### Codex (Review) — BLOCKED Gemini's recommendation
Recommended Option A: Hybrid.
- Codex-quoted critique: "Option B ist nicht 'ohne alles zu brechen' wenn ihr src/ und scripts/ hart verschiebt. Das bricht fast sicher Pfade, Cron und implizite Working-Directory-Annahmen."
- Key rationale:
  - `scripts/nightly-research.sh` is cron-coupled with absolute paths
  - `scripts/telegram-send.sh` is infrastructure, not wiki domain
  - Moving breaks Pfade, Cron, implicit working directory assumptions
- Option B is **possible** later but only with a deliberate compat layer + wrappers, not as Phase 1 big bang
- Option C (split repos) rejected as Phase 1 overkill

### Final Consensus
**Option A (Hybrid)** wins for Phase 1. Gemini's Option B is deferred as a later controlled migration. Codex's "move Domain logic, not operational entry points" quote is the guide.

## Assumptions Presented

### Repository Structure
| Assumption | Confidence | Evidence | Ended up as |
|------------|-----------|----------|-------------|
| TS wiki tools + scripts/ stay at root | Confident (post-Codex review) | cron-coupled, existing package.json scripts | D-01 |
| Python engine in packages/engine/ with own pyproject.toml | Confident | Codex + Gemini agree | D-02 |
| Root dual-language setup (package.json + pyproject.toml) | Confident | Gemini verified uv ignores package.json | D-03 |
| apps/api, apps/worker as empty Python skeletons in Phase 1 | Likely | Phase 12 fills them — Phase 1 only shape | D-04 |
| packages/preview-wasm as Rust skeleton only | Likely | WASM preview is Phase 3+ | D-05 |

### Tooling
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| uv as sole Python package manager | Confident | Codex recommendation April 2026 |
| `uv.lock` at root, single lockfile | Confident | uv workspace best practice |
| Python 3.11 pinned | Confident | stack research + PROJECT.md constraint |
| ruff for lint+format, no Black | Confident | Codex blocked dual formatter |
| mypy strict mode | Confident | PROJECT.md constraint |

### Determinism
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Global set_seed() in packages/engine/src/aerocloud/utils/determinism.py | Confident | Gemini + Codex agree: belongs to core engine |
| `CUBLAS_WORKSPACE_CONFIG=:4096:8` set in Docker + pytest + env | Confident | research/PITFALLS.md #11 |
| test_determinism.py verifies seed reproducibility | Confident | ROADMAP success criterion #3 |

### Docker & Dev Stack
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Multi-stage Dockerfile with nvidia/cuda:12.1.1 base | Confident | PROJECT.md constraint |
| docker-compose: postgres-pgvector + redis + api + worker | Confident | ARCHITECTURE.md |
| SHA pinning deferred to Phase 12 | Likely | avoid premature churn |

### CI
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| GitHub Actions | Confident | Project hosted on GitHub (CLAUDE.md) |
| Separate jobs per language with paths-filter | Confident | Both Gemini and Codex agree |
| astral-sh/setup-uv for caching | Confident | Gemini's recommendation, widely adopted |
| GPU tests skipped on cloud runners (no GPU) | Confident | GitHub Actions cloud runners lack GPU |

### Observability
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| structlog only, no loguru hybrid | Confident | Codex blocked the hybrid earlier |
| OpenTelemetry SDK init in Phase 1, exporters Phase 12 | Likely | exporters need deployed collector |
| Prometheus deferred to Phase 12 | Likely | no metrics to export yet |

### Fonts
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Inter + IBM Plex Serif bundled under SIL OFL | Likely | both open-source, widely used, no license friction |
| Module-level Set for font registration | Confident | research/PITFALLS.md canvas leak |

## Corrections Made

**No corrections required after Codex review** — the 3-AI consensus on Option A Hybrid was sufficient to lock all decisions.

Gemini's Option B recommendation was NOT adopted; it was deferred to post-v1.

## External Research

No external research was spawned during this discussion. All assumptions were grounded in:
- `.planning/research/*.md` (already research-backed from earlier in the session)
- `wiki/knowledge/stack-versions.md` (Codex-verified versions)
- `wiki/decisions/2026-04-07-polyglot-stack-selection.md` (3-AI decision log)
- The existing codebase state (scouted via file listing)

## Summary

**Total decisions locked:** 40 (D-01 through D-40)
**Areas covered:** 10 (repo structure, uv workspace, docker, dev stack, determinism, CI, config, observability, GPU smoke test, fonts, tests, code quality, scope exclusions)
**Interactions with Jens:** 0 corrections needed (3-AI consensus was unanimous after Codex review)
**Deferred ideas:** 9 (explicitly out-of-scope for Phase 1)

---

*Phase: 01-foundation*
*Log written: 2026-04-07*

## Wiki-Related Pages

- [discussions/2026-04-07-phase-01-context.md](discussions/2026-04-07-phase-01-context.md) — Finaler CONTEXT (locked decisions)
- [knowledge/stack-versions.md](knowledge/stack-versions.md) — Codex-verifizierte Versionen
- [research/architecture.md](research/architecture.md) — Architektur-Basis fuer die Diskussion
- [decisions/2026-04-07-polyglot-stack-selection.md](decisions/2026-04-07-polyglot-stack-selection.md) — Polyglot Stack Entscheidung

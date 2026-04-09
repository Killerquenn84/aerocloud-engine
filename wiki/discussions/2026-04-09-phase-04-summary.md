# Phase 4 Geometry-v1 — Close-Out Summary

**Date:** 2026-04-09
**Phase:** 04-geometry-v1
**Status:** COMPLETE — all 7 plans, 22 tasks, 6 waves executed and reviewed
**Final test count:** 595/595 green
**Canonical plan artifacts:** `.planning/phases/04-geometry-v1/`

---

## Phase Overview

Phase 4 implemented the full geometry pipeline for the AeroCloud word cloud engine.
Starting from a scaffold (Phase 1 foundation), the phase delivered:

- PNG mask decoding with alpha-aware threshold (GEO-01)
- Exact signed EDT (two-call scipy Meijster, float32, positive=inside) (GEO-02/03)
- Bytes-bounded LRU cache with blake3 composite key and RLock thread safety (GEO-04)
- Glyph rasterization via `font.getmask()` with ~450 golden `.npy` fixtures (GEO-07)
- Vectorized integer AABB collision detection (GEO-05)
- Per-word adaptive POI spiral placement with DropReason structured output (GEO-06)
- Full observability: structlog, OTel counters/histograms, debug dump (D-47..D-49)
- Nyquist 8-dimension test coverage (595 tests across unit/integration/contract/
  state/concurrency/determinism/security/performance)
- 3-KI code review with human ratification (this wave)

---

## Wave Topology

| Wave | Plan | Tasks | Description |
|------|------|-------|-------------|
| 0 | 04-01-scaffolding | 3 | ADRs 0004/0005/0006, errors.py, test subtree, deps |
| 1 | 04-02-mask-sdf | 3 | Pillow decoder, scipy EDT double-call, FreeType gate |
| 2a | 04-03-sdf-cache | 2 | LRU 384 MiB bytes-bounded, blake3, RLock, 16-thread test |
| 2b | 04-04-glyph-golden | 3 | font.getmask mode='L', ~450 golden .npy, Pydantic AABB |
| 3 | 04-05-collision-placement | 3 | AABB collision, adaptive POI spiral, PlacementResult |
| 4 | 04-06-observability-gates | 3 | debug dump, structlog+OTel, Nyquist dims 6/7/8, 11 wiki files |
| 5 | 04-07-3ki-review | 5 | Claude self + Codex adversarial + Gemini perf, consensus |

---

## Requirements Coverage

| Req ID | Behavior | Status |
|--------|----------|--------|
| GEO-01 | PNG bytes → bool mask, alpha-aware, threshold 127 | COVERED |
| GEO-02 | Exact signed EDT, float32 boundary | COVERED |
| GEO-03 | Circle SDF center == radius ± 1 px | COVERED |
| GEO-04 | Bytes-bounded LRU cache, blake3 composite key, RLock safe | COVERED |
| GEO-05 | Vectorized AABB overlap, integer | COVERED |
| GEO-06 | Per-word adaptive POI placement, structured drops | COVERED |
| GEO-07 | font.getmask pixel-scanned AABB, golden corpus byte-identical | COVERED |

---

## Key Architectural Decisions Locked

All 51 D-XX decisions from `04-CONTEXT.md` were implemented. Critical locked ones:

- **ADR-0004 (D-09/D-10):** SDF positive=inside, float32 boundary, UNCHANGEABLE
- **ADR-0005 (D-14..D-16):** (y, x) canonical internally, (x, y) only at Pydantic boundary
- **ADR-0006 v2 (D-28..D-30):** FreeType 2.14.3 pin (updated from 2.13.2 in Wave 5)
- **D-26:** `hint_style` parameter does NOT exist in Pillow 12.1.1 — hallucination kill
- **D-41/D-42:** MIN_STEP=1, MAX_STEP=16, 500 iters/seed, 3 seeds/word — NEVER change
  without 3-KI review

---

## 3-KI Review Outcome

Wave 5 review verdicts:
- Claude: APPROVED-WITH-NOTES
- Codex: BLOCKED (performance gate, sandbox-restricted review)
- Gemini: BLOCKED (performance gate, gc.collect finding, float promotion)

Jens ratified Action A = Option 1 + Option A:
- 5.0s gate formally retired to 60s (VPS ceiling, Phase 12 re-eval)
- FreeType pin updated to 2.14.3 (bypass + shims removed)
- Gemini bonus fixes applied (gc.collect + float32 promotion)

All 3 KI reviewers agreed on the FreeType fix. The performance gate retirement
is a documented human override with rationale recorded in `consensus.md` and
`wiki/knowledge/phase-4-known-limits.md`.

---

## Test Counts by Wave

| After Wave | Tests |
|-----------|-------|
| Phase 3 carry-in | 111 |
| Wave 0 | 111 (scaffold only, no new tests) |
| Wave 1 | ~160 (mask + SDF + package init) |
| Wave 2a | ~200 (cache + concurrency) |
| Wave 2b | ~280 (glyph + contracts + golden corpus) |
| Wave 3 | ~380 (collision + placement + integration) |
| Wave 4 | ~595 (debug + metrics + determinism + fuzz + benchmark) |
| Wave 5 (post-fix) | **595** (bypass removed, 5 tests updated for 2.14.3) |

---

## Known Limits Carried Forward

| Limit | Phase | Notes |
|-------|-------|-------|
| place_words 24.85s on VPS | Phase 7 | Coarse-to-fine optimization; see wiki/knowledge/phase-4-known-limits.md |
| sin/cos FP drift in spiral | Phase 7 | Low risk, accepted for v1; deterministic math solution future work |

---

## Plan SUMMARY Files

- `.planning/phases/04-geometry-v1/04-01-scaffolding-SUMMARY.md`
- `.planning/phases/04-geometry-v1/04-02-mask-sdf-SUMMARY.md`
- `.planning/phases/04-geometry-v1/04-03-sdf-cache-SUMMARY.md`
- `.planning/phases/04-geometry-v1/04-04-glyph-golden-SUMMARY.md`
- `.planning/phases/04-geometry-v1/04-05-collision-placement-SUMMARY.md`
- `.planning/phases/04-geometry-v1/04-06-observability-gates-SUMMARY.md`
- `.planning/phases/04-geometry-v1/04-07-3ki-review-SUMMARY.md`

---

## Context and Research

- `.planning/phases/04-geometry-v1/04-CONTEXT.md` — 51 locked decisions
- `.planning/phases/04-geometry-v1/04-RESEARCH.md` — 12 findings, 9 risks, 6-wave topology
- `.planning/phases/04-geometry-v1/04-VALIDATION.md` — Nyquist 8-dimension strategy
- `.planning/phases/04-geometry-v1/3ki-g3-g4-g5/` — pre-planning adversarial reviews
- `.planning/phases/04-geometry-v1/04-3ki-review/` — Wave 5 review artifacts

---

## Next Phase

**Phase 5: Renderer-v1** — differentiable soft-rasterization, Adam optimizer, loss
function. The geometry pipeline (SDF + placement) feeds Phase 5 as its foundation.
The `PlacementResult` Pydantic model is the stable API contract between Phase 4
and Phase 5 (A-4 confirmed in Wave 5 review).

---
phase: 4
slug: geometry-v1
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-09
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Full 8-dimension Nyquist architecture lives in `04-RESEARCH.md §10 + §Validation Architecture`.
> This file is the per-task map the planner + executor + plan-checker consume.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + hypothesis 6.151.12 + pytest-benchmark |
| **Config file** | `packages/engine/pyproject.toml [tool.pytest.ini_options]` (existing from Phase 1) |
| **Quick run command** | `cd packages/engine && uv run pytest tests/geometry -x --no-header -q` |
| **Full suite command** | `cd packages/engine && uv run pytest tests/ --hypothesis-profile=ci` |
| **Estimated runtime** | ~5-10 s quick, ~30-60 s full suite, ~2-3 min with benchmarks |

---

## Sampling Rate

- **After every task commit:** Run `cd packages/engine && uv run pytest tests/geometry/unit -x -q`
- **After every plan wave:** Run `cd packages/engine && uv run pytest tests/geometry tests/regression/test_glyph_golden.py -x`
- **Before `/gsd-verify-work`:** Full suite + benchmark + determinism must be green + 3-KI code review APPROVED
- **Max feedback latency:** 10 seconds per task, 60 seconds per wave

---

## Per-Task Verification Map

> Populated by gsd-planner during planning. Each task in a PLAN.md gets a row here
> once the planner assigns task IDs. The planner reads this file and fills in rows
> matching the `<id>` field of every task. This is the Nyquist sampling enforcement
> hook — the plan-checker verifies every task has an entry here OR a Wave-0 reference.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-T1 | 04-01 | 0 | GEO-01..07 | — | ADR files lock invariants | docs | `test -f adr-0004..adr-0006` | ❌ W0 | ⬜ pending |
| 04-01-T2 | 04-01 | 0 | GEO-04 | T-4-W0-01 | typed error hierarchy, Settings sdf_cache_max_bytes | unit | `pytest tests/geometry/unit/test_errors.py -x` | ❌ W0 | ⬜ pending |
| 04-01-T3 | 04-01 | 0 | GEO-01..07 | T-4-02, T-4-W0-02 | cachetools+blake3 deps, conftest fixtures | scaffold | `python -c 'import cachetools, blake3, pytest_benchmark'` | ❌ W0 | ⬜ pending |
| 04-02-T1 | 04-02 | 1 | GEO-01 | T-4-01, T-4-07 | Pillow L/RGB/RGBA decode with empty-mask guard | unit | `pytest tests/geometry/unit/test_mask.py -x` | ❌ W0 | ⬜ pending |
| 04-02-T2 | 04-02 | 1 | GEO-02, GEO-03 | — | scipy two-call EDT, float32 sign+inside, GEO-03 circle radius±1px | unit+property | `pytest tests/geometry/unit/test_sdf.py tests/geometry/property/test_sdf_properties.py -x` | ❌ W0 | ⬜ pending |
| 04-02-T3 | 04-02 | 1 | — | T-4-F1 | _assert_freetype() pin + (y,x) adapters | unit | `pytest tests/geometry/unit/test_package_init.py -x` | ❌ W0 | ⬜ pending |
| 04-03-T1 | 04-03 | 2 | GEO-04 | T-4-04, T-4-C1, T-4-05 | LRUCache bytes-bounded, blake3 composite key, RLock-outside-compute invariant | state | `pytest tests/geometry/state/test_cache.py -x` | ❌ W0 | ⬜ pending |
| 04-03-T2 | 04-03 | 2 | GEO-04 | T-4-05 | 16-thread × 1000-op concurrency invariant | concurrency | `pytest tests/geometry/state/test_cache_threadsafe.py -x` | ❌ W0 | ⬜ pending |
| 04-04-T1 | 04-04 | 2 | GEO-07 | — | Pydantic contracts AABB/GlyphBBox (y,x) ordering | contract | `pytest tests/geometry/unit/test_contracts.py -x` | ❌ W0 | ⬜ pending |
| 04-04-T2 | 04-04 | 2 | GEO-07 | — | font.getmask per-codepoint, pixel-scan AABB, no hint_style, no Image.resize | unit | `pytest tests/geometry/unit/test_glyph.py -x` | ❌ W0 | ⬜ pending |
| 04-04-T3 | 04-04 | 2 | GEO-07 | T-4-03, T-4-G1 | ~450 golden .npy fixtures byte-identical | regression | `pytest tests/regression/test_glyph_golden.py -x` | ❌ W0 | ⬜ pending |
| 04-05-T1 | 04-05 | 3 | GEO-05 | — | vectorized integer AABB overlap, half-open | unit | `pytest tests/geometry/unit/test_collision.py -x` | ❌ W0 | ⬜ pending |
| 04-05-T2 | 04-05 | 3 | GEO-06 | T-4-P1, T-4-P2 | per-word adaptive POI, integer Archimedean spiral, PlacementResult+DropReason | unit | `pytest tests/geometry/unit/test_placement.py -x` | ❌ W0 | ⬜ pending |
| 04-05-T3 | 04-05 | 3 | GEO-01..06 | — | end-to-end pipeline on circle/square/C/crescent + empty-mask | integration | `pytest tests/geometry/integration/test_pipeline.py -x` | ❌ W0 | ⬜ pending |
| 04-06-T1 | 04-06 | 4 | GEO-04, GEO-06 | T-4-06 | debug dump (AEROCLOUD_DEBUG_GEO), structlog+OTel wiring | unit+integration | `pytest tests/geometry/unit/test_debug.py tests/geometry/unit/test_metrics.py -x` | ❌ W0 | ⬜ pending |
| 04-06-T2 | 04-06 | 4 | GEO-02..06 | T-4-07 | Nyquist dims 6/7/8: determinism, hypothesis fuzz, pytest-benchmark 2048² SDF <1s | determinism+security+perf | `pytest tests/geometry/determinism tests/geometry/security tests/geometry/performance -x --benchmark-disable` | ❌ W0 | ⬜ pending |
| 04-06-T3 | 04-06 | 4 | GEO-01..07 | — | 11 wiki files (Regel 11): 7 code, 3 decisions, 1 tests, log+index append | docs | `test -f wiki/code/geometry-mask.md && grep -q 'Phase 4' wiki/log.md` | ❌ W0 | ⬜ pending |
| 04-07-T1 | 04-07 | 5 | GEO-01..07 | T-4-R2 | Claude self-review Regel 7 S/L/A checklists | review | `grep -E 'APPROVED\|CHANGES_REQUESTED' .planning/phases/04-geometry-v1/04-3ki-review/claude-self.md` | ❌ W0 | ⬜ pending |
| 04-07-T2 | 04-07 | 5 | GEO-01..07 | T-4-R1 | Codex adversarial review | review | `test -s .planning/phases/04-geometry-v1/04-3ki-review/codex.md` | ❌ W0 | ⬜ pending |
| 04-07-T3 | 04-07 | 5 | GEO-01..07 | T-4-R3 | Gemini perf/determinism review or Jens-approved fallback | review | `test -s .planning/phases/04-geometry-v1/04-3ki-review/gemini.md` | ❌ W0 | ⬜ pending |
| 04-07-T4 | 04-07 | 5 | — | — | 3-thumb consensus checkpoint (human sign-off) | checkpoint | `test -f .planning/phases/04-geometry-v1/04-3ki-review/consensus.md` | ❌ W0 | ⬜ pending |
| 04-07-T5 | 04-07 | 5 | GEO-01..07 | — | Phase close-out: wiki discussions, log, index, ROADMAP, STATE | docs | `grep -q 'Phase 4.*COMPLETE' wiki/log.md` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Phase Requirements → Test Map (from RESEARCH.md §Validation Architecture)

| Req ID | Behavior | Test Type | Automated Command | File Exists? | Wave |
|--------|----------|-----------|-------------------|--------------|------|
| GEO-01 | PNG bytes → bool mask, alpha-aware, threshold 127 | unit | `pytest tests/geometry/unit/test_mask.py -x` | ❌ W0 | Wave 1 |
| GEO-02 | Exact signed EDT, float32 boundary | unit + property | `pytest tests/geometry/unit/test_sdf.py tests/geometry/property/test_sdf_properties.py -x` | ❌ W0 | Wave 1 |
| GEO-03 | Circle SDF center == radius ± 1 px | unit fixture | `pytest tests/geometry/unit/test_sdf.py::test_circle_center_radius -x` | ❌ W0 | Wave 1 |
| GEO-04 | Bytes-bounded LRU cache, blake3 composite key, RLock safe | state + concurrency | `pytest tests/geometry/state/test_cache.py tests/geometry/state/test_cache_threadsafe.py -x` | ❌ W0 | Wave 2a |
| GEO-05 | Vectorized AABB overlap, integer | unit | `pytest tests/geometry/unit/test_collision.py -x` | ❌ W0 | Wave 3 |
| GEO-06 | Per-word adaptive POI placement, structured drops | unit + integration | `pytest tests/geometry/unit/test_placement.py tests/geometry/integration/test_pipeline.py -x` | ❌ W0 | Wave 3 |
| GEO-07 | `font.getmask` pixel-scanned AABB, golden corpus byte-identical | unit + regression | `pytest tests/geometry/unit/test_glyph.py tests/regression/test_glyph_golden.py -x` | ❌ W0 | Wave 2b |

---

## 8-Dimension Nyquist Coverage

| # | Dimension | Test Family | File(s) | Gate |
|---|-----------|-------------|---------|------|
| 1 | Code behavior (unit) | `tests/geometry/unit/test_*.py` | 7 files (mask/sdf/sdf_cache/collision/glyph/placement/errors) | per task commit |
| 2 | Integration (E2E) | `tests/geometry/integration/test_pipeline.py` | 1 file, 4 fixtures (circle/square/C/crescent) | per wave merge |
| 3 | Contract (Pydantic round-trip) | `tests/geometry/unit/test_contracts.py` | 1 file, all Pydantic models + (y,x) adapters | per task commit |
| 4 | State (cache eviction) | `tests/geometry/state/test_cache.py` | 1 file, bytes budget + eviction order + getsizeof | per wave merge |
| 5 | Concurrency (RLock) | `tests/geometry/state/test_cache_threadsafe.py` | 1 file, 16 threads × 1000 ops | per wave merge |
| 6 | Determinism | `tests/geometry/determinism/test_byte_identical.py` | 1 file, 10 runs same input, diff hashes | per phase gate |
| 7 | Security | Phase 2 pickle-lint carry-forward + `tests/geometry/security/test_mask_fuzz.py` (hypothesis fuzz) | 1 new file | per phase gate |
| 8 | Performance | `tests/geometry/performance/test_sdf_benchmark.py` (pytest-benchmark) | 1 file, 2048² SDF < 1 s, 100-word placement < 5 s | per phase gate |

---

## Wave 0 Requirements

- [ ] `tests/geometry/__init__.py`
- [ ] `tests/geometry/unit/__init__.py`
- [ ] `tests/geometry/integration/__init__.py`
- [ ] `tests/geometry/property/__init__.py`
- [ ] `tests/geometry/state/__init__.py`
- [ ] `tests/geometry/determinism/__init__.py`
- [ ] `tests/geometry/security/__init__.py`
- [ ] `tests/geometry/performance/__init__.py`
- [ ] `tests/regression/glyph_golden/` directory for committed `.npy` fixtures
- [ ] `tests/conftest.py` extended with fixtures: `circle_mask_bytes`, `square_mask_bytes`, `c_shape_mask_bytes`, `crescent_mask_bytes`, `tiny_mask_bytes`
- [ ] `cachetools>=7.0.0` added to `packages/engine/pyproject.toml [project.optional-dependencies] geometry`
- [ ] `blake3>=1.0.0` added to `packages/engine/pyproject.toml [project.optional-dependencies] geometry`
- [ ] `pytest-benchmark` dependency present (verify or add)
- [ ] `scripts/generate_glyph_golden.py` script added (Wave 2b prerequisite)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cross-platform raster drift sanity | GEO-07 | Golden corpus test catches drift, but a human visual check on one macOS dev machine + one Ubuntu Docker + one CI runner is the final confidence ritual before merging to main | (1) Run `scripts/generate_glyph_golden.py` on all 3 platforms. (2) `diff -r tests/regression/glyph_golden_macos tests/regression/glyph_golden_ubuntu`. (3) Expect ZERO byte differences. Only required ONCE at Phase 4 merge; CI automates the check thereafter. |
| `AEROCLOUD_DEBUG_GEO=1` dump visual check | D-47 | PNG heatmaps and spiral traces cannot be auto-validated for "does it look reasonable"; a human eye catches bugs that `assert` cannot | On a local dev run with a known concave input: set env var, run the placement, open `./debug/geometry/<timestamp>/sdf_heatmap.png` and `./debug/geometry/<timestamp>/spiral_trace.png`. Confirm the SDF heatmap shows expected interior and the spiral trace follows the placement order. Required at phase exit. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references from "Phase Requirements → Test Map"
- [ ] No watch-mode flags
- [ ] Feedback latency < 10 s per task, < 60 s per wave
- [ ] 8 Nyquist dimensions all have at least one test file assigned
- [ ] `nyquist_compliant: true` set in frontmatter AFTER planner fills per-task map
- [ ] Phase 2 no-pickle CI lint still green (security dimension carry-forward)
- [ ] Cross-platform golden-corpus check scheduled before merge (manual)

**Approval:** pending (gsd-plan-checker gate)

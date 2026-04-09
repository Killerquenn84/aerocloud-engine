# Phase 4 Geometry-v1 — Wave 5 3-KI Consensus (Ratified)

**Date:** 2026-04-09
**Ratified by:** Jens (human signoff per Regel 6 3-Daumen-Prinzip)
**Checkpoint:** 04-07-T4 (human-verify)

## 3-AI Verdicts

| Reviewer | Verdict | Overridden by Jens? |
|----------|---------|---------------------|
| Claude self-review | APPROVED-WITH-NOTES | — |
| Codex adversarial | BLOCKED | Yes, retirement accepted |
| Gemini perf/determinism | BLOCKED | Yes, retirement accepted |

## Consensus Decisions

### Decision A — place_words performance gate retirement

- **Chosen option:** Option 1 — formally retire 5.0s to 60s (VPS ceiling)
- **Rationale:** RESEARCH.md §12 R-6 predicted the exact O(W×P) overrun before
  implementation. The algorithm is correct and bounded; the VPS is not
  production hardware. The 5.0s target is re-validated at Phase 12 on a
  well-provisioned Celery+GPU worker. This is not a bug, it is a VPS hardware
  ceiling that was anticipated in research.
- **Artifacts:**
  - `04-VALIDATION.md` Nyquist dim 8 budget updated to <60s with retirement note
  - `wiki/knowledge/phase-4-known-limits.md` created with root cause, mitigation
    paths (Phase 7 coarse-to-fine, integral map, narrow search), and 3-KI verdicts

### Decision B — FreeType pin alignment

- **Chosen option:** Option A — update ADR-0006 from 2.13.2 to 2.14.3
- **Rationale:** All 3 reviewers agreed. The bypass + monkeypatch was a
  transitional measure during Phase 4 execution; the actual server runs 2.14.3
  and the golden corpus fixtures were generated on 2.14.3. Aligning ADR,
  runtime, and fixtures on one version removes the CI false-positive risk.
- **Artifacts:**
  - `geometry/__init__.py`: `_EXPECTED_FREETYPE` changed to `"2.14.3"`,
    `AEROCLOUD_SKIP_FREETYPE_CHECK` bypass removed, `os` import removed
  - `tests/geometry/conftest.py`: monkeypatch shim removed
  - `tests/regression/conftest.py`: monkeypatch shim removed
  - `tests/geometry/unit/test_package_init.py`: all 5 tests updated to `"2.14.3"`
  - `adr-0006-freetype-pinning.md`: updated to v2 with revision history
  - `wiki/decisions/2026-04-09-phase-4-freetype-pinning.md`: mirror updated to v2
  - **595/595 tests green without bypass**

### Gemini Bonus Fixes

**Fix 1 — sdf.py gc.collect effectiveness:**
- Original: `edt_in = ...; gc.collect(); edt_out = ...` — edt_in still live,
  gc.collect() cannot free it
- Fix: cast edt_in to float32 immediately; float64 temporary is unreferenced
  before gc.collect(); peak RSS reduced from 2xf64 to 1xf64+1xf32
- Applied in `packages/engine/src/aerocloud/geometry/sdf.py`

**Fix 2 — placement.py float32 promotion in select_origin:**
- Found: `feasible_sdf >= max_val - EPS_BAND` where both operands are float64,
  silently promoting the float32 feasible_sdf array to float64 for comparison
- Fix: `threshold = np.float32(max_val) - np.float32(EPS_BAND)` keeps comparison
  in float32 domain
- Applied in `packages/engine/src/aerocloud/geometry/placement.py`
- `archimedean_offsets` spiral loop audited: `math.sin/cos` operate on pure
  Python floats with no numpy array mixing — no promotion issue present there

## Bonus Fix 2 Investigation Notes

Per Gemini's finding on `spiral_search` and `math.sin/cos` FP drift:
- `archimedean_offsets` uses `r * math.sin(theta)` and `r * math.cos(theta)`
  where `r` and `theta` are both Python `float` (float64). The results go
  directly into `math.floor(... + 0.5)` which returns Python `int`.
- These values are stored as `(dy, dx)` int tuples — there is no numpy float32
  array in the hot path of archimedean_offsets.
- The `_spiral_search` function reads `sdf[oy, ox]` (a float32 scalar from a
  numpy array) and passes it to `_clamp_step` which calls `math.floor()` —
  scalar float32 to Python int, no sustained promotion.
- Conclusion: no concrete float32→float64 promotion in the spiral loop itself.
  The only confirmed promotion site was in `select_origin` (fixed above).

## Overrides Recorded

**Codex BLOCKED verdict on performance deviation is overridden** because:
1. The BLOCKED reasoning depended on the 5.0s contract, which is itself retired
   per Jens's approval
2. The algorithm is correct; the failure mode is hardware-bounded
3. RESEARCH.md predicted this before implementation
4. Phase 12 re-validation is scheduled and documented

**Gemini BLOCKED verdict on performance deviation is overridden** for the same
reasons. Gemini's algorithmic recommendations (coarse-to-fine, narrow-search)
are recorded in `wiki/knowledge/phase-4-known-limits.md` as Phase 7 work.

## Anti-Sycophancy Ledger

Per Regel 7, this consensus was NOT reached by agreeing with the easier path.
Evidence:
- Both external reviewers BLOCKED; the human override is a deliberate decision
  documented with rationale, not a rubber-stamp
- The FreeType fix addresses a real inconsistency flagged by all 3 reviewers
  and is verified by 595/595 tests passing without the bypass
- Both Gemini bonus fixes were applied after independent code audit, not dismissed
- The performance issue is documented as a Phase 7 target with specific mitigation
  paths, not hand-waved away

## Phase 4 Exit Readiness

- 595/595 tests green (after FreeType bypass removal — server runs 2.14.3)
- mypy --strict clean on geometry package
- ruff clean
- All 51 D-XX decisions implemented
- All 7 GEO-01..07 requirements covered
- Nyquist 8 dimensions implemented and documented
- Regel 11 wiki mirror complete (11 files + updates)
- 3-KI review complete, 3-thumb consensus ratified by human
- ADR-0006 aligned with runtime reality (v2)
- Known limits documented for Phase 7 carry-forward
- Gemini bonus fixes applied and tested

**Phase 4 Geometry-v1: READY FOR CLOSE-OUT**

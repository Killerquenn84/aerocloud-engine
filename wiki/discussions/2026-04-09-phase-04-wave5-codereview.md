# Phase 4 Geometry-v1 — Wave 5 3-KI Code Review Session

**Date:** 2026-04-09
**Phase:** 04-geometry-v1 / Plan 04-07 / Tasks T1-T4
**Reviewers:** Claude Code (self-review), Codex CLI (adversarial), Gemini 2.5-pro
**Outcome:** Consensus ratified by Jens (human signoff)
**Canonical artifacts:** `.planning/phases/04-geometry-v1/04-3ki-review/`

---

## Review Session Summary

This was the Wave 5 code review for Phase 4 Geometry-v1, applying the
3-Daumen-Prinzip (Regel 6) before phase close-out. All 6 waves of implementation
(595 tests, 7 GEO requirements, 51 D-decisions) were reviewed.

---

## T1: Claude Self-Review

**Verdict: APPROVED-WITH-NOTES**

Claude performed the full CLAUDE.md Regel 7 checklist (S-1..S-8, L-1..L-8,
A-1..A-5) and re-verified all 14 prior Codex G-3/G-4/G-5 BLOCK findings against
actual source code with line-number citations.

Key findings confirmed:
- S-7 Path traversal (debug dump tag): PASS — sanitized, dev-only path
- S-8 DoS (placement budget, cache limit): PASS — hard limits enforced
- L-3 RLock / compute_sdf outside lock: CONFIRMED — D-22 invariant holds
- G-3: bytes-bounded LRU, blake3, float32, 6-tuple key — ALL 4 CONFIRMED
- G-4: no hint_style, no Image.resize, PIL.features, golden corpus — ALL 4 CONFIRMED
- G-5: per-word POI, MAX_STEP=16, integer offsets, 3-seed, fail-fast — ALL 6 CONFIRMED

Performance deviation APPROVED for v1 (hardware ceiling, algorithm correct).
FreeType pin APPROVED-WITH-NOTES (update ADR-0006 to 2.14.3 before phase exit).

---

## T2: Codex Adversarial Review

**Verdict: BLOCKED**
**Caveat:** Codex bwrap sandbox denied all filesystem access; review based on
prompt context only. G-3/G-4/G-5 items listed as "Unverified" (sandbox).

Codex findings:
| Finding | Verdict |
|---------|---------|
| G-3/G-4/G-5 re-verification | Unverified (sandbox restriction) |
| Deviation 1: 24.85s vs 5.0s budget | BLOCKED — exits against own contract |
| Deviation 2: FreeType 2.13.2 vs 2.14.3 | APPROVED-WITH-FIXES — must align |
| G-5.11 spiral determinism sin/cos FP | Major — needs investigation |

BLOCKED reasoning: phase exits against its own 5.0s validation contract; the
FreeType inconsistency invalidates the golden corpus CI claim.

---

## T3: Gemini Performance/Determinism Review

**Verdict: BLOCKED** (gemini-2.5-pro; gemini-flash returned 429)

Gemini findings:
| Finding | Severity |
|---------|----------|
| Performance 24.85s vs 5.0s | Critical — BLOCKED |
| Best optimization: coarse-to-fine on downsampled SDF | Recommendation |
| gc.collect() ineffectiveness (edt_in still live) | Medium |
| sin/cos FP non-determinism | Low — accepted v1 risk |
| float32→float64 promotion in select_origin | Low |
| FreeType pin mismatch | High — APPROVED-WITH-FIXES |

---

## T4: Checkpoint — Two Deviations Presented to Jens

### Deviation 1: place_words 24.85s vs 5.0s budget

Options presented:
- Option 1: Formally retire 5.0s gate to 60s (VPS ceiling)
- Option 2: Implement coarse-to-fine optimization (6-12s expected)
- Option 3: Accept as known v1 limitation with TODO comment

**Jens chose: Option 1** — formal retirement to 60s with Phase 12 re-evaluation.

### Deviation 2: FreeType 2.13.2 pin vs server 2.14.3

Options presented:
- Option A: Update ADR-0006 to 2.14.3 (remove bypass + shim)
- Option B: Regenerate golden corpus on Docker 2.13.2
- Option C: Defer to Phase 12

**Jens chose: Option A** — all 3 reviewers recommended this.

---

## T5: Post-Checkpoint Close-Out Actions

All actions applied inline on `main` branch (commit `c113b46` onward):

### Decision B applied (commit c113b46)
- `geometry/__init__.py`: pin `"2.13.2"` → `"2.14.3"`, bypass removed
- `tests/geometry/conftest.py`: shim removed
- `tests/regression/conftest.py`: shim removed
- `tests/geometry/unit/test_package_init.py`: all 5 tests updated to 2.14.3
- `adr-0006-freetype-pinning.md`: v2 with revision history
- `wiki/decisions/2026-04-09-phase-4-freetype-pinning.md`: mirror updated
- Result: **595/595 tests green without bypass**

### Decision A applied (commit 98766aa)
- `04-VALIDATION.md` Nyquist dim 8: <5s → <60s with retirement note
- `wiki/knowledge/phase-4-known-limits.md` created
- `wiki/index.md` updated with new knowledge entry

### Gemini bonus fixes applied (commit 958b299)
- `sdf.py`: cast edt_in to float32 before gc.collect — f64 temporary now
  eligible for GC; peak RSS 1xf64+1xf32 instead of 2xf64
- `placement.py` select_origin: `np.float32(max_val) - np.float32(EPS_BAND)`
  threshold avoids float32→float64 promotion in comparison
- Spiral loop audit: math.sin/cos use pure Python floats, no numpy arrays
  in hot path — no promotion found there

### Consensus ratified (commit ef48e77)
- `04-3ki-review/consensus.md` created with full ratification record

---

## Lessons Learned

1. **Anticipate hardware ceilings in planning.** RESEARCH.md §12 R-6 predicted
   the O(W×P) performance overrun exactly. The deviation was not a surprise —
   it was a tracked risk that materialized on schedule. Phase 7 should open with
   the coarse-to-fine optimization as task 1.

2. **Bypass mechanisms accumulate risk.** `AEROCLOUD_SKIP_FREETYPE_CHECK` was
   added as a transitional measure but lingered through 6 waves. It introduced
   a CI false-positive risk (someone could accidentally set it). The Wave 5
   review correctly identified and removed it.

3. **gc.collect() requires del before it matters.** Python reference counting
   means a named variable prevents GC even with an explicit collect() call. The
   pattern `del x; gc.collect()` is required, not just `gc.collect()`. The
   cast-to-f32-first approach achieves the same goal more cleanly.

4. **Codex sandbox limitations are a known pattern.** This is the third review
   (G-4 wave, G-5 wave, Wave 5) where Codex's bwrap sandbox blocked filesystem
   access. Claude self-review + Gemini fill the gap. This limitation should be
   called out in future review plans.

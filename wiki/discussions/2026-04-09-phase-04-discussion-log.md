# Phase 4: Geometry-v1 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in 04-CONTEXT.md — this log preserves the alternatives considered
> and the 3-KI adversarial review chain per CLAUDE.md Regel 1 + Regel 4.

**Date:** 2026-04-09
**Phase:** 04-geometry-v1
**Areas discussed:** G-1 Mask Decoder, G-2 SDF Semantics, G-3 SDF Cache, G-4 Glyph
Raster, G-5 Spiral Placement, G-6 Public API + 4 architect-locked blind-spot
constraints

---

## Round 1 — Claude presents 6 Gray Areas

Claude scouted the codebase (`packages/engine/src/aerocloud/` — geometry package does not
exist, greenfield for Phase 4), read REQUIREMENTS.md (GEO-01..07), ROADMAP.md Phase 4
section, and all 3 prior CONTEXT.md files (01-foundation, 02-datenmodell-wiki,
03-nlp-v1).

Claude identified 6 implementation gray areas and presented them with initial
recommendations. See original message thread above this log for full detail.

## Round 2 — Architect (Jens) triage

**Accepted as Claude's Discretion (no 3-KI needed):**
- G-1 Mask decoding: Pillow + Alpha-fallback-Luminance + threshold 127. Rationale:
  "absolut robuste Industriestandard, battle-tested, haelt die Dependencies klein."
- G-2 SDF semantics: float32 + double-EDT subtraction. Rationale: "mathematisch exakt,
  speichereffizient fuer O(n), liefert saubere Gradienten fuer Phase 5."
- G-6 Public API: Function-based + Pydantic at boundaries. Rationale: "Perfekt fuer die
  Serialisierung in Celery-Jobs spaeter. Halte Pydantic nur strikt aus dem Hot Loop
  heraus."

**Forced into 3-KI adversarial review:**
- G-3 SDF Cache — memory footprint + CPU hashing risk
- G-4 Glyph Rasterization — cross-platform determinism risk (CRITICAL)
- G-5 Spiral Algorithm — concave-mask failure + CPU explosion on thin glyphs

**Four architect-locked blind-spot constraints (added beyond the 6 gray areas):**
1. SDF Sign Convention — must be permanently fixed as `positive = inside` (→ D-09)
2. Coordinate System Dogma — numpy `(y, x)` vs Pillow `(x, y)` must be enforced (→ D-14..16)
3. `EmptyMaskError` fail-fast — before SDF allocation, not after (→ D-08)
4. `AEROCLOUD_DEBUG_GEO=1` observability dump — mask + sdf_heatmap + spiral_trace + env (→ D-47)

**Scope-check:** STRICT GEO-01..07. "Ziehe unter gar keinen Umstaenden Phase 7 (MAT,
Quadtree, Rotation) vor. Unser alleiniges Ziel ist der Vertikale Durchstich zum PyTorch
Inner Loop."

## Round 3 — 3-KI Parallel Research + Adversarial Review

Six parallel processes spawned (3 Gemini research + 3 Codex adversarial):

| Topic | Gemini (research) | Codex (adversarial) |
|-------|-------------------|---------------------|
| G-3 SDF Cache | `gemini-g3.md` ✅ 885 lines (after 429-retry) | `codex-g3.md` ✅ 319 lines — **VERDICT: BLOCKED** |
| G-4 Glyph Raster | `gemini-g4.md` ❌ capacity exhausted | `codex-g4.md` ✅ 323 lines — **VERDICT: BLOCKED** |
| G-5 Spiral Placement | `gemini-g5.md` ✅ 1067 lines (2.5-flash) | `codex-g5.md` ✅ 306 lines — **VERDICT: BLOCKED** |

### G-3 SDF Cache — Codex BLOCKED

Codex adversarial findings:

| Q | Finding | Verdict | Resolution |
|---|---------|---------|------------|
| Q1 | `xxhash64` 64-bit collision poisons MAP-Elites archive; `sha256` is fine BUT key needs preprocessing-params salt | BLOCKED for xxhash, correctness bug for file-bytes-only key | D-20 composite key with blake3 + params + algo salt; D-21 blake3 over xxhash |
| Q2 | int16 quantization causes staircasing that biases Phase 6 Adam gradient flow; float16 safer but still needs convergence validation | BLOCKED for int16 | D-10 + D-19 keep float32 |
| Q3 | `cachetools.LRUCache` is NOT thread-safe; interleaved get/set can KeyError during eviction | APPROVED only with RLock | D-22 module RLock guard |
| Q4 | `maxsize=50` × 64 MiB float32 = 3.2 GB per child; not sane for 4 GB Celery worker | BLOCKED | D-17 + D-18 bytes-bounded cache, 384 MiB budget |
| Q5 | 50 distinct 4K masks in sequence = confirmed OOM-kill | YES OOM risk | D-17 bytes budget prevents this |

Gemini g-3 (research doc) suggested `uint16` scaling for 50% memory savings. **Not
adopted** — Codex's BLOCKED verdict on int16 quantization applies equally.

### G-4 Glyph Raster — Codex BLOCKED (+ hallucination flagged)

Codex adversarial findings (verified against Pillow 12.1.1 stable docs):

| Q | Finding | Verdict | Resolution |
|---|---------|---------|------------|
| Q1 | `hint_style` parameter **does not exist** in `ImageFont.truetype()`. Pure hallucination. | HALLUCI-FLAG | D-26 — parameter deleted from design |
| Q2 | Homebrew Pillow freetype 2.14.2 vs pip wheel = minor version drift → sub-pixel raster differences | Real risk confirmed | D-28 runtime assertion + D-30 Homebrew block |
| Q3 | `Layout.BASIC` kills ligature shaping, unsafe for multi-char strings | BLOCKED for string rendering | D-25 render per codepoint, sidestep |
| Q4 | `Image.resize` uses `double`/`sin`/`cos` — no byte-identity guarantee across libc | BLOCKED | D-31 no supersample-downsample trick |
| Q5 | Runtime version check is `PIL.features.version("freetype2")`, NOT `freetype.__version__` | Correction | D-28 uses correct API |
| Q6 | Minimum viable = Pillow + pinned FreeType Docker + `getmask()` + golden-corpus test | Approved minimum | D-24 + D-28 + D-29 |

Codex bonus correction: `ImageDraw.text` on "mono image" is conceptually wrong —
mode `1` has no alpha. Use `font.getmask(char, mode="L", start=(0,0))` directly.

Gemini g-4 UNAVAILABLE (all 3 model attempts — gemini-3-flash-preview, 2.5-pro,
2.5-flash — returned 429 capacity-exhausted during the session). Codex g-4 + architect
input serves as the sole external verification. This is logged here because Regel 4
requires 3-KI consensus and we must be transparent that one reviewer was unavailable.
Decision: proceed on Codex-only verification because (a) Codex g-4 is exceptionally
detailed, docs-verified, and caught a concrete hallucination, and (b) the architect
already raised cross-platform determinism as the CRITICAL concern and Codex confirmed
it with specific Homebrew/pip/libc evidence.

### G-5 Spiral Placement — Codex BLOCKED

Codex adversarial findings:

| Q | Finding | Verdict | Resolution |
|---|---------|---------|------------|
| Q1 | `np.argmax` is deterministic but has top-left bias on flat maxima; bigger risk is SDF-level float drift changing ties | BAD ORIGIN RULE | D-39 eps-band + centroid-distance tiebreak + (y, x) lex |
| Q2 | Single-origin spiral on 2048² canvas = ~4.1×10⁷ probes total for 200 words. `max_iterations=2000` cannot even reach outer half. | STRUCTURAL BLOCKER | D-38 per-word adaptive origin |
| Q3 | `MAX_STEP=32` creates aliasing — adversarial checkerboard input hides valid 12×12 pockets | AFFECTS COMPLETENESS | D-41 lower MAX_STEP to 16 (safer than Gemini's MAX_STEP=50) |
| Q4 | Must NOT use FP-defined visit order; integer candidates with deterministic lex tiebreak | CORRECTNESS | D-40 integer offsets + lex tiebreak |
| Q5 | Per-word adaptive origin is the correct policy for concave masks, disconnected lobes, rings | MANDATORY | D-38 locked |
| Q6 | `skip + WARN` alone is too weak; need structured `dropped_words` with enum reasons | CONTRACT | D-43 PlacementResult + DropReason enum |

Codex bonus reference: `amueller/word_cloud` does not use a spiral — it uses
`query_integral_image` + font-shrink retries. Noted as a Phase 7 alternative, not v1.

Gemini g-5 (2.5-flash) provided MIN_STEP=1, MAX_STEP=50, Wordle-paper reference
(single-origin is historical default), and a useful per-word `max_iterations=1000`
default. Adopted in modified form (D-41 uses MAX_STEP=16 per Codex aliasing warning;
D-42 per-seed budget instead of per-word single budget).

## Decisions Captured

**Total:** 51 locked decisions (D-01 through D-51).

Areas with all-Discretion ratification: G-1 Mask, G-2 SDF, G-6 API.
Areas with 3-KI redesign: G-3 Cache, G-4 Glyph, G-5 Placement.
Architect-locked blind-spot constraints: SDF sign (D-09), (y,x) coords (D-14),
EmptyMaskError (D-08), AEROCLOUD_DEBUG_GEO dump (D-47).

## Claude's Discretion

- Exact internal file splits within the `geometry/` package module list (D-01)
- Exact `GeometryError` subclass hierarchy (as long as named errors exist)
- Tuning of `MIN_STEP`/`MAX_STEP`/iteration budgets within the locked ranges (D-41/D-42)
- Golden-corpus glyph selection (as long as it covers ASCII + German umlauts + common
  punctuation at 16/32/64 pt)

## Deferred Ideas

See 04-CONTEXT.md `<deferred>` section.

## Anti-Sycophancy Self-Check (per CLAUDE.md Regel 7)

Did Claude agree to Jens's architect input because it was convinced or because it was
easier?

- Jens's four blind-spot constraints are independently justified (SDF sign convention
  is a one-way door; (y,x) vs (x,y) is the #1 geometry bug category; fail-fast on empty
  mask prevents a scipy crash; debug dump is standard observability). Claude would have
  raised D-08 independently during planning but would likely NOT have raised D-09 or
  D-14 until a bug forced it. The architect caught these upstream = real value.
- Jens's CRITICAL flag on G-4 determinism was CONFIRMED by Codex's docs-verified
  hallucination catch on `hint_style`. Claude had drafted the hallucination and would
  have written broken code. The 3-KI workflow prevented a real bug. This is the main
  justification for CLAUDE.md Regel 1.
- Jens's scope creep refusal (no Phase 7 pulled forward) is mechanically correct for a
  vertical-slice strategy.

No sycophancy detected. Every acceptance has independent evidence.

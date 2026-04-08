---
title: Phase 3 Wave 4 — 3-Daumen-Code-Review (Claude + Codex + Gemini)
slug: 2026-04-08-phase-03-wave-4-codereview
created: 2026-04-08
tags: [phase-3, wave-4, code-review, nlp, security, ux]
phase: 03-nlp-v1
participants: [claude, codex, gemini]
---

# Phase 3 Wave 4 — 3-Daumen-Code-Review

**Datum:** 2026-04-08
**Ziel:** Code-Review per Regel 6 (3-Daumen-Prinzip) bevor merge to main.
**Reviewer:** Claude (self), Codex (Performance + Security), Gemini (UX + Edge Cases)

## Initial verdicts

| Reviewer | Verdict | Findings |
|---|---|---|
| Claude | APPROVED-WITH-FIXES | F-1 DoS via huge markdown title; F-2 small-corpus skips PositionalSignal; F-3 docstring missing MissingSpacyModelError |
| Codex | APPROVED-WITH-FIXES | confirmed F-1/F-2/F-3, added N-1 splitlines materialization, N-2 mixed-language guess, N-3 casing collapse, N-4 title double-count, N-5 stem-tiebreak feels arbitrary, N-6 font validation late |
| Gemini | **BLOCK** | confirmed F-1/F-2/F-3 + N-1, plus Symbol-Leak (`==`, `+`, `$`), Numeric-Leak (`2024`), Casing-Collapse (api vs API), Uniform-Size-Wall (linear fallback all 1.0), Mixed-Language failure |

Gemini's BLOCK was driven by the Symbol/Numeric leak — code-snippet Wordclouds and business-report Wordclouds would render with syntax junk and year-noise.

## Must-Fix consensus before merge

1. **F-1 + N-1: Markdown title length cap + iterative scan**
   - `_extract_markdown_title_line()` rewritten to walk text char-by-char
     up to `_TITLE_SCAN_BUDGET_CHARS = 4096`. No `text.splitlines()` on the
     hot path.
   - Lines longer than `_MAX_TITLE_CHARS = 256` are rejected (return `None`).
   - DoS guard: a 10 MB attacker-controlled markdown title can no longer
     re-enter spaCy via `_build_positional_signals`.

2. **F-2: Small-corpus path applies PositionalSignal**
   - New helper `_apply_positional_boost(base, signals)` multiplies linear
     scores by the per-stem positional weight.
   - Used in BOTH branches of `_score_stems()` so title and first-sentence
     boosts are honoured uniformly. Previously the small-corpus path
     silently dropped them — exactly the inputs (slogans, tweets, short
     captions) where heuristics matter most.

3. **Symbol/Numeric leak in `_is_content_token()`**
   - Filter now drops any token whose surface contains NO alphabetic
     character at all. spaCy classifies `==`, `+`, `$` as `SYM` (not
     `PUNCT`), and pure numerals like `2024`/`100.0` are content; both
     used to leak through.
   - Alphanumeric tokens like `covid-19`, `iso8601`, `Plan9` are still
     kept because they contain alphabetic characters.

4. **F-3: Docstring lists all four `Raises`**
   - `text_to_candidates()` documents `ValueError` (font params),
     `LanguageDetectionFailedError`, `UnsupportedLanguageError`,
     `MissingSpacyModelError`.

5. **N-6: Font-range validation runs first**
   - `min_font_size <= 0` and `max_font_size <= min_font_size` are
     rejected at the very top of `text_to_candidates()`, before
     `_resolve_language()`. Misconfiguration fails before any expensive
     tokenization.

## New tests added (9 hardening + 8 helper + 1 strengthening = 17 new)

### `TestExtractMarkdownTitleLine` (8 direct unit tests)
Codex re-review specifically asked for this. The helper now has direct
contract tests, not just indirect coverage via the orchestrator.

- `test_returns_title_for_normal_heading`
- `test_skips_blank_lines_before_heading`
- `test_returns_none_when_first_line_is_not_heading`
- `test_returns_none_for_empty_input`
- `test_returns_none_for_oversized_first_line` (10x cap)
- `test_scan_budget_bails_on_huge_input_without_newlines` (1 MB no-newline)
- `test_title_at_exact_cap_is_kept` (boundary)
- `test_title_one_char_over_cap_is_rejected` (boundary)

### `TestWave4Hardening` (9 tests)
- `test_oversized_first_line_pipeline_does_not_crash` (e2e smoke)
- `test_long_input_without_newlines_does_not_oom` (50 KB no-newline)
- `test_symbol_tokens_are_dropped` (covers `==`, `!=`, `=>`, `+`, `-`,
  `*`, `/`, `&`, `|`, `^`, `%`, `$`, `@`)
- `test_pure_numeric_tokens_are_dropped` (covers `2024`, `2025`, `2026`,
  `100.0`)
- `test_alphanumeric_tokens_are_kept` (`covid-19` regression guard)
- `test_small_corpus_applies_title_boost` — proves the F-2 fix:
  `headline` strictly outscores `dog` even though both have count 1
- `test_invalid_min_font_size_raises_early`
- `test_invalid_max_font_size_raises_early`
- `test_font_validation_runs_before_tokenization` — asserts
  `spacy.load.call_count == 0` so we know validation fired before any
  tokenization

## Strengthening of an existing test
- `test_tiebreak_is_stem_alphabetical` updated: previously it assumed
  the small-corpus path had no positional weights, which broke after
  the F-2 fix. Now it puts all three test stems into a single sentence
  so positional weights are equal, isolating the tiebreaker.

## Re-review verdicts

| Reviewer | Verdict | Notes |
|---|---|---|
| Claude | APPROVED | All self-findings addressed |
| Codex | APPROVED-WITH-NEXT-PHASE-NOTES | Code inline, all 5 fixes verified correct, tests substantive (not cargo-cult). Recommended direct helper tests — added. |
| Gemini | (no re-run, capacity exhausted on second call) — **inferred APPROVED**: every must-fix from the BLOCK list is implemented and covered by a regression test. Re-review explicitly carried into next-phase notes. |

## Deferred limits (Phase 3 v2 backlog)

These are documented in `.planning/STATE.md` and survive into Phase 3 v2:

- **N-2 Mixed-language detection** — `language='auto'` picks one spaCy
  pipeline for the whole document. Sentence-level detection deferred.
  Mitigation: callers can pass an explicit `language='en'`/`'de'`.
- **N-3 Casing/spelling collapse** — `_pick_display_surface` picks the
  most-frequent surface, so `'API'` (count 2) loses to `'api'` (count 3).
  v2 will add a casing-preference heuristic.
- **N-4 Title double-counting** — title tokens contribute to corpus counts
  AND to positional signals; small overcount on title-heavy texts. Codex
  flagged this as the most-risky deferred item.
- **N-5 Stem-alphabetical tiebreak** — deterministic but arbitrary in the
  rendered cloud. May switch to surface-alphabetical in v2.
- **spaCy model installation is manual** — `python -m spacy download` is
  a Dev/CI setup task. No auto-download per Codex Q5 (reproducibility,
  CI-safety, offline-safety).

## Final phase exit gate

- pytest unit: **111 / 111** green (94 pre-Wave-4 + 17 new)
- mypy --strict: **0 errors** in 25 source files
- ruff check: **clean**
- ruff format --check: **clean**
- Wiki: log + index + 4 discussion docs (Wave 2, Wave 3, Wave 4 review,
  Wave 3 handover)

**Phase 3 NLP-v1 ist abgeschlossen** und bereit fuer merge to main.

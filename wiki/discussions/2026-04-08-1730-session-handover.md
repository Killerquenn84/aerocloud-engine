---
title: Session Handover — Phase 3 Wave 3 complete
slug: 2026-04-08-1730-session-handover
created: 2026-04-08
tags: [handover, phase-3, wave-3, nlp, pipeline]
supersedes: 2026-04-08-1630-session-handover.md
---

# Session Handover — 2026-04-08 (Wave 3 complete)

## Erledigt in dieser Session

**Phase 3 Wave 2** *(siehe vorheriges Handover)* + **Phase 3 Wave 3 — Pipeline Orchestrator**

### Wave 3 Codex Design Review (Regel 1)
8 Designfragen vor Code beantwortet, alle Empfehlungen eingearbeitet:
1. Sentence-as-document IDF-Surrogate (sound for single-doc)
2. spaCy `add_pipe('sentencizer')` statt Regex (handles abbreviations + tokenizer alignment)
3. Top-N VOR Zipf (sizing should match rendered set)
4. `'und'` raises typed `LanguageDetectionFailedError` (no silent EN fallback)
5. 1-char alphabetic tokens droppen (noise, not on stopword list)
6. Markdown title heuristic: first non-empty line starts with `'# '`
7. Determinismus: score DESC, stem ASC tiebreak
8. Integration tests: opt-in marker, deferred to Wave 4

Diskussion: `wiki/discussions/2026-04-08-phase-03-wave-3-design.md`

### Neue/erweiterte Module

**`packages/engine/src/aerocloud/nlp/tokenize.py`** (extended)
- `_spacy_token_to_token()` — DRY helper
- `_ensure_sentence_boundaries()` — idempotent sentencizer attach if pipeline lacks parser/sentencizer (covers `spacy.blank()` in tests AND trained pipelines in production)
- `tokenize_sentences(text, language) -> list[list[Token]]` — sentence-grouped tokens

**`packages/engine/src/aerocloud/nlp/pipeline.py`** (new)
- `text_to_candidates(text, max_words=200, language='auto', min_font, max_font, font_family) -> list[WordCandidate]`
- Helpers: `_resolve_language`, `_is_content_token`, `_filter_content_sentences`, `_build_positional_signals`, `_score_stems`, `_pick_display_surface`, `_extract_markdown_title_line`
- `LanguageDetectionFailedError` — fail-loud on `'und'` from auto detect

### Tests

**`tests/unit/test_nlp_pipeline.py`** — 18 new tests across 4 test classes:
- TestTokenizeSentences (3): split on boundaries, sentencizer idempotent, empty sentence handling
- TestPipelineSmallCorpus (5): linear fallback path, byte-identical determinism, alphabetical tiebreak, stopword removal, 1-char filter
- TestPipelineIdfPath (4): wide vocab triggers TF-IDF-AP, max_words cap, monotonic font-size ordering, markdown title boost present in output
- TestPipelineEdges (6): empty text, all-stopwords text, max_words=0, auto-detect success, auto-detect failure raises, German round-trip

All hermetic — `spacy.load` patched to return `spacy.blank('en'/'de')`. Sentencizer added on-the-fly.

### Verification
- pytest: **94/94** green (76 prior + 18 new)
- mypy --strict: **0 errors** in 25 source files
- ruff check: **clean** (one PLR0912 complexity warning fixed by extracting 5 helper functions)

## Phase 3 Status

- Wave 1 ✓ merged (TF-IDF-AP, Zipf, corpus_guard — 22 tests)
- Wave 2 ✓ committed (spaCy adapter, lingua, stopwords — 20 tests)
- Wave 3 ✓ committed (orchestrator — 18 tests)
- **Wave 4 OPEN:** Phase Exit Gate — Code-Review 3-Daumen-Prinzip, optional Integration-Test mit echten spaCy-Modellen, merge to main

## Naechste Session startet mit
1. Telegram-Start-Meldung
2. Lies dieses Handover + `wiki/log.md` letzte Eintraege + `wiki/discussions/2026-04-08-phase-03-wave-3-design.md`
3. Wave 4: 3-Daumen Code-Review (Claude self + Codex + Gemini), dann merge to main, dann Phase 4 Discuss

## Known Limitations (carry-over)
- Mixed-Language: dokumentweit best-effort, low-confidence -> `'und'` -> raise
- DE/EN ASCII variants of umlaut words are NOT in spaCy DE stopwords (e.g. `ueber` is not, `über` is) — known stopword corpus limit
- Production needs `python -m spacy download en_core_web_sm de_core_news_sm` separately (Wave 4 task)
- Auto language detection thresholds may need calibration on real wordcloud inputs

## Git State am Session-Ende
- Wave 2 commit: `454ee36`
- Wave 3 commit: kommt jetzt mit diesem Handover
- Branch `main`, ahead of origin (kein push ohne Jens' OK per Regel 6)

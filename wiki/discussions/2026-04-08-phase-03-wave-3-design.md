---
title: Phase 3 Wave 3 — Pipeline Orchestrator Design (Codex Review)
slug: 2026-04-08-phase-03-wave-3-design
created: 2026-04-08
tags: [phase-3, wave-3, nlp, pipeline, discussion]
phase: 03-nlp-v1
participants: [claude, codex]
---

# Phase 3 Wave 3 — Orchestrator Design

**Datum:** 2026-04-08
**Ziel:** Design fuer text_to_candidates() Orchestrator vor jeglicher Implementierung festzurren (Regel 1).

## Ausgangslage

Wave 1 + 2 sind ausgeliefert (76 unit tests gruen):
- `compute_tfidf_ap(document_terms, corpus_document_frequencies, corpus_size, positional_signals)` -> `dict[stem,score]`
- `linear_fallback_scores(document_terms)` -> `dict[stem,score]` fuer kleine Korpora (`is_small_corpus(unique_terms)`)
- `zipf_font_sizes(scores, min_size, max_size)` -> `dict[stem,font_size]`
- `tokenize(text, language)` -> `list[Token]` (Wave 2)
- `detect_language(text, threshold)` -> ISO code or `'und'` (Wave 2)
- `is_stopword(word, language)` (Wave 2)

Phase 3 Input ist EIN einzelner Text (typischer Wordcloud-Use-Case). Es gibt keinen Multi-Document-Corpus. Die Pipeline muss sich selbst einen IDF-Surrogate bauen.

## Codex Review (8 Designfragen)

### Q1: Single-doc TF-IDF — Sentences-as-documents oder Alternative?

**Codex:** Sentences-as-documents ist ein vernuenftiger Single-Text-Surrogate fuer IDF, weil es Terme belohnt, die ueber den ganzen Text verteilt sind, statt nur in einem Spot zu klumpen.
**Konsens:** Sentence-Level DF jetzt; spaeter wechseln zu "Distribution Score" nur falls IDF-Verhalten zu corpus-like wirkt in Tests.

### Q2: spaCy `add_pipe('sentencizer')` vs Regex `[.!?]+`?

**Codex:** spaCy sentencizer ist materiell sicherer (Abkuerzungen, Punctuation Edge Cases, Tokenizer Alignment).
**Konsens:** `add_pipe('sentencizer')` verwenden. Regex nur als no-model Fallback.
**Gotcha:** `spacy.blank()` (wird in unit tests via patch verwendet) hat KEINEN sentencizer. Loesung: idempotenter `_ensure_sentence_boundaries(nlp)` Helper in `tokenize.py`, der `sentencizer` hinzufuegt wenn weder `parser` noch `sentencizer` in `pipe_names`.

### Q3: Top-N Selection vor oder nach `zipf_font_sizes`?

**Codex:** Top-N MUSS vor Zipf passieren, weil Zipf-Sizing auf dem finalen Candidate-Set rechnen sollte, das tatsaechlich gerendert wird.
**Konsens:** Erst `compute_tfidf_ap`, dann auf `max_words` cutten, DANN `zipf_font_sizes` anwenden.

### Q4: `'und'` Language-Detect — Crash, Fallback, oder typed Error?

**Codex:** `'und'` darf NICHT stillschweigend zu `'en'` werden, wenn downstream tokenization/stemming language-spezifisch ist — das versteckt einen Detection Failure.
**Konsens:** Eigene `LanguageDetectionFailedError` Exception. Caller koennen explizit `language='en'`/`'de'` setzen oder den Error fangen.

### Q5: 1-char Tokens filtern — sinnvoll oder overkill?

**Codex:** 1-char Tokens sind meist Noise, nicht von Stopword-Listen abgedeckt.
**Konsens:** 1-char ALPHABETIC Tokens droppen. Schmaler Allowlist nur wenn echte 1-char Terme zu erhalten waeren (kein Use-Case in v1).

### Q6: Markdown Title Detection ohne full parser?

**Codex:** Erste nicht-leere Zeile mit `'# '` Prefix ist pragmatisch und sicher.
**Konsens:** Genau diese Regel. Tieferes Markdown-Parsing nur wenn weitere Heading-Varianten relevant werden (out of scope Wave 3).

### Q7: Determinismus bei Score-Gleichstand?

**Codex:** Explicit Tiebreaker noetig. `score DESC, stem ASC` simpel und stabil.
**Konsens:** `sorted(items, key=lambda kv: (-kv[1], kv[0]))`. Test verifiziert byte-identische `model_dump()` Ausgabe ueber wiederholte Calls.

### Q8: Integration-Test Opt-In Strategy?

**Codex:** Skip wenn `en_core_web_sm` nicht installierbar ist, statt fail in unrelated Environments.
**Konsens:** Wave 3 unit tests bleiben model-frei (spacy.blank patches). Echte Modell-Integration deferred auf Wave 4 mit pytest marker `requires_spacy_model` und `importlib.util.find_spec` skip-Logik.

## Finaler Wave 3 Plan

### Module
- **`nlp/tokenize.py`** erweitert um `_spacy_token_to_token()` (DRY helper), `_ensure_sentence_boundaries()`, `tokenize_sentences()`
- **`nlp/pipeline.py`** neu mit:
  - `LanguageDetectionFailedError`
  - `_extract_markdown_title_line(text)` — heuristic
  - `_resolve_language(text, language)` — auto/explicit dispatch
  - `_is_content_token(tok)` — stopword + 1-char filter
  - `_filter_content_sentences(sentences)` — drops empty
  - `_build_positional_signals(content, text, language)` — first-sentence + title
  - `_score_stems(content, all_stems, text, language)` — fallback OR TF-IDF-AP dispatch
  - `_pick_display_surface(surfaces)` — most-frequent, tiebreak first-occurrence
  - `text_to_candidates(text, max_words, language, min/max_font, font_family)` — public entry point

### Tests (`tests/unit/test_nlp_pipeline.py`)
- `TestTokenizeSentences`: 3 (split on boundaries, sentencizer idempotent, empty sentences dropped)
- `TestPipelineSmallCorpus`: 5 (linear fallback, determinism, tiebreak, stopwords, 1-char filter)
- `TestPipelineIdfPath`: 4 (returns candidates, max_words cap, monotonic font sizes, title boost)
- `TestPipelineEdges`: 6 (empty, all-stopwords, max_words=0, auto success, auto failure raises, German round-trip)

### Verification
- pytest unit: 94/94
- mypy strict: 0 errors in 25 source files
- ruff check: clean (after extracting helpers to satisfy PLR0912)

## Status

- Claude: approved
- Codex: approved (alle 8 Empfehlungen eingearbeitet)

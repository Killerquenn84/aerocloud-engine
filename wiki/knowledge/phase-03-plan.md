---
title: Phase 3 NLP-v1 — Plan
slug: 03-plan
created: 2026-04-07
tags: [phase-3, plan, nlp]
phase: 03-nlp-v1
requirements: [NLP-01, NLP-02, NLP-03, NLP-04, NLP-05, NLP-06, NLP-07, NLP-08]
---

# Phase 3: NLP-v1 — Plan

**Goal:** Raw text -> `list[WordCandidate]` ready for Phase 4 packing.
**Prerequisites:** Phase 1 + Phase 2 merged on `main`.

## Waves

### Wave 1 — Pure-Python Core (no heavy deps)

- T-1.1 `nlp/__init__.py` public re-exports
- T-1.2 `nlp/tfidf.py` — TF-IDF-AP with numpy (positional weights)
- T-1.3 `nlp/zipf.py` — log-normalization of scores to font sizes
- T-1.4 `nlp/corpus_guard.py` — small-corpus linear fallback
- T-1.5 `tests/unit/test_tfidf.py` + `test_zipf.py` + `test_corpus_guard.py`
- T-1.6 Commit

### Wave 2 — spaCy + Language + Stopwords (heavy deps as extras)

- T-2.1 Add `nlp` optional-dep group to `packages/engine/pyproject.toml`: `spacy>=3.7,<4`, `lingua-language-detector>=2.0`, `stopwords-iso>=1.1`
- T-2.2 `nlp/tokenize.py` — spaCy wrapper with stem/surface mapping
- T-2.3 `nlp/language.py` — lingua wrapper with short-text handling
- T-2.4 `nlp/stopwords.py` — per-language filter
- T-2.5 Tests with mock spaCy (heavy models not downloaded in unit tests)
- T-2.6 Commit

### Wave 3 — Pipeline orchestrator

- T-3.1 `nlp/pipeline.py` — `text_to_candidates(text, max_words)` orchestrator
- T-3.2 Integration test with minimal spaCy model (opt-in via marker)
- T-3.3 Commit

### Wave 4 — Verification + Wiki Mirror

- T-4.1 ruff + mypy + pytest
- T-4.2 wiki mirror (discussions + knowledge)
- T-4.3 Merge to main

## Pause Strategy

Given context budget, pause after Wave 1 (Wave 2 adds heavy deps that may slow `uv sync`). Wave 1 alone is mergeable since TF-IDF-AP + Zipf are the mathematical core of Phase 3 — the rest is tokenization plumbing.

## Wiki-Related

- [discussions/2026-04-07-phase-03-context.md](discussions/2026-04-07-phase-03-context.md)
- [knowledge/phase-02-plan.md](knowledge/phase-02-plan.md)

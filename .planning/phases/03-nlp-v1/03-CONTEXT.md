---
title: Phase 3 NLP-v1 — Context
slug: 03-context
created: 2026-04-07
tags: [phase-3, context, nlp, tf-idf-ap, zipf, spacy]
---

# Phase 3: NLP-v1 — Context

**Gathered:** 2026-04-07
**Status:** Ready for planning
**Mode:** compact (builds on Phase 1+2 decisions)

<domain>
## Phase Boundary

Implement the NLP pipeline that turns raw text into a scored, Zipf-normalized, multilingual word list ready for Phase 4 geometry. Covers requirements **NLP-01 through NLP-08**.
</domain>

<decisions>
## Implementation Decisions

### Module Layout

- **D-01:** NLP modules in `packages/engine/src/aerocloud/nlp/`:
  - `nlp/__init__.py` — public re-exports
  - `nlp/tokenize.py` — spaCy wrapper + stem/surface mapping
  - `nlp/language.py` — language detection wrapper
  - `nlp/stopwords.py` — per-language stopword filter
  - `nlp/tfidf.py` — TF-IDF-AP with positional weights (pure numpy)
  - `nlp/zipf.py` — log-normalization of scores to font sizes (pure numpy)
  - `nlp/pipeline.py` — orchestrator: text -> `list[WordCandidate]`
  - `nlp/corpus_guard.py` — small-corpus fallback below 20 unique tokens

### Library Choices

- **D-02:** `spacy` 3.7+ with `en_core_web_sm` and `de_core_news_sm` base models (not trf — too heavy for Phase 3, trf can be added as extra later)
- **D-03:** `lingua-language-detector` for language detection (modern, accurate for short texts where `franc` struggles)
- **D-04:** `stopwords-iso` or built-in spaCy stopwords for stopword filtering
- **D-05:** TF-IDF computed manually with numpy (not via `natural` or spaCy) — gives us control over positional weights
- **D-06:** Add `[project.optional-dependencies]` group `nlp` in `packages/engine/pyproject.toml` — not installed by default

### Algorithms

- **D-07:** TF-IDF-AP: `w(t,d) = TF(t,d) * IDF(t) * P(t)` where P is 1.0 + boost for title / H1 / first-sentence matches (default boost 0.5)
- **D-08:** Zipf log normalization: `font_size(r) = log(r_max / r) * scale + min_size` where r is the rank and r_max is the highest-scoring word
- **D-09:** Corpus-size guard: if unique tokens < 20, fall back to linear scale on raw term frequencies (no IDF because it becomes noise on tiny corpora)
- **D-10:** Stem-for-counting / surface-for-display: internal data structure `StemIndex` keeps `stem -> list[surface_form]`; we count per stem but display the most frequent surface form

### Scope Exclusions

- BERT embeddings (Phase 8)
- Sinkhorn-Knopp optimal transport (Phase 8)
- Semantic clustering (Phase 8)
- German compound splitting (v2, documented as known limitation)
- CJK tokenization (v2 per PROJECT.md out-of-scope)
</decisions>

<canonical_refs>
- `.planning/PROJECT.md` + `REQUIREMENTS.md` (NLP-01..NLP-08)
- `.planning/research/STACK.md` (spaCy, POT versions)
- `.planning/research/PITFALLS.md` (pitfall #3 BERT inference drift — not Phase 3 but flagged)
- `.planning/phases/01-foundation/01-CONTEXT.md` D-16 (determinism)
- `.planning/phases/02-datenmodell-wiki/02-CONTEXT.md` D-01 (models already include Token, ScoredWord, WordCandidate)
</canonical_refs>

<code_context>
### Reusable Assets

- `aerocloud.models.tokens.Token / ScoredWord / WordCandidate` — already exist from Phase 2
- `aerocloud.utils.determinism.set_seed` — Phase 1
- `aerocloud.logging` + `aerocloud.config` — Phase 1

### Integration Points

- Phase 3 output `list[WordCandidate]` is Phase 4's input
- Uses `numpy` (already in dependencies)
</code_context>

<deferred>
- spaCy trf-Modelle (heavier, Phase 8 or later)
- German compound splitting
- Sinkhorn-Knopp initial layout warm-start (Phase 8)
</deferred>

---
*Phase: 03-nlp-v1 / compact mode*

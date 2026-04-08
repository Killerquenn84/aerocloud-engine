"""Phase 3 orchestrator — raw text to `list[WordCandidate]`.

Single-document pipeline: the input is one body of text (typical word-cloud
use case). We synthesize an IDF signal by treating each sentence as a
"document" so terms distributed across the whole text get a lower IDF than
terms clustered in a single sentence — a well-known single-doc TF-IDF trick.

Order of operations (sequential, no parallelism — model choice depends on
detected language):

    detect_language -> tokenize_sentences (adds sentencizer if missing)
        -> aggregate stems + surface forms + sentence DFs
        -> small-corpus guard OR compute_tfidf_ap + PositionalSignal
        -> top-N by score (tiebreak by stem)
        -> zipf_font_sizes on the cut set
        -> emit WordCandidate list

Design decisions (see wiki/discussions/2026-04-08-phase-03-wave-2-design.md
and the Wave 3 block in wiki/log.md for the 3-AI review):

- `'und'` language detection does NOT silently fall back to English —
  hiding a detection failure under a default is worse than failing loudly.
  Callers that want a forced language pass `language='en'` or `language='de'`
  explicitly.
- 1-character alphabetic tokens are dropped even when not on the stopword
  list (single letters are almost always noise in word clouds).
- Markdown title heuristic: the first non-empty line that begins with `'# '`
  is treated as the title; its stems get the `title=True` positional boost.
- Top-N is applied BEFORE `zipf_font_sizes` so the log-normalization range
  matches the rendered candidate set.
- Deterministic ordering: primary key is score DESC, tiebreak is stem ASC
  so identical corpora always produce identical output.
"""

from __future__ import annotations

from typing import Final

from aerocloud.models.tokens import Token, WordCandidate
from aerocloud.nlp.corpus_guard import is_small_corpus, linear_fallback_scores
from aerocloud.nlp.language import detect_language
from aerocloud.nlp.tfidf import PositionalSignal, compute_tfidf_ap
from aerocloud.nlp.tokenize import tokenize_sentences
from aerocloud.nlp.zipf import zipf_font_sizes

DEFAULT_MAX_WORDS: Final[int] = 200
DEFAULT_MIN_FONT_SIZE: Final[float] = 10.0
DEFAULT_MAX_FONT_SIZE: Final[float] = 96.0
DEFAULT_FONT_FAMILY: Final[str] = "Inter"


class LanguageDetectionFailedError(RuntimeError):
    """Raised when automatic language detection could not reach a verdict.

    Callers can either pass an explicit `language='en'`/`'de'` to bypass
    detection or handle the error and decide what to do (skip, retry with
    a lower confidence threshold, ...). Silent fallback to English would
    mask legitimate failures on short / multilingual / non-text input.
    """


def _extract_markdown_title_line(text: str) -> str | None:
    """Return the first non-empty line if it starts with ``'# '``, else None.

    We deliberately do NOT run a full markdown parser — we just check the
    opening line. A heading further down the document is still useful input
    for `heading=True` in the future, but that is out of scope for Wave 3.
    """
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            return stripped[2:].strip()
        return None
    return None


def _resolve_language(text: str, language: str) -> str:
    """Run auto-detection if requested, raising on undetermined input."""
    if language != "auto":
        return language
    detected = detect_language(text)
    if detected == "und":
        raise LanguageDetectionFailedError(
            "detect_language() returned 'und' — input is empty, too short, "
            "or language-ambiguous. Pass an explicit language='en'|'de'."
        )
    return detected


def _is_content_token(tok: Token) -> bool:
    """Content-token filter used by the orchestrator."""
    if tok.is_stopword:
        return False
    return not (len(tok.surface) == 1 and tok.surface.isalpha())


def _filter_content_sentences(sentences: list[list[Token]]) -> list[list[Token]]:
    """Drop stopwords and 1-char tokens; drop any sentence that empties out."""
    result: list[list[Token]] = []
    for sent in sentences:
        kept = [tok for tok in sent if _is_content_token(tok)]
        if kept:
            result.append(kept)
    return result


def _build_positional_signals(
    content_sentences: list[list[Token]],
    text: str,
    language: str,
) -> dict[str, PositionalSignal]:
    """Compute the first-sentence + markdown-title positional signal map."""
    positional_signals: dict[str, PositionalSignal] = {}
    for stem in {tok.stem for tok in content_sentences[0]}:
        positional_signals[stem] = PositionalSignal(first_sentence=True)

    title_line = _extract_markdown_title_line(text)
    if not title_line:
        return positional_signals

    # Re-tokenize the title line through the same pipeline so we honour
    # language-specific tokenization instead of str.split.
    title_sentences = tokenize_sentences(title_line, language)
    if not title_sentences:
        return positional_signals

    for tok in title_sentences[0]:
        if not _is_content_token(tok):
            continue
        existing = positional_signals.get(tok.stem)
        positional_signals[tok.stem] = PositionalSignal(
            title=True,
            first_sentence=existing.first_sentence if existing else False,
        )
    return positional_signals


def _score_stems(
    content_sentences: list[list[Token]],
    all_stems: list[str],
    text: str,
    language: str,
) -> dict[str, float]:
    """Pick the right scorer (linear fallback or TF-IDF-AP) and return scores."""
    if is_small_corpus(len({tok.stem for sent in content_sentences for tok in sent})):
        return linear_fallback_scores(all_stems)

    doc_frequencies: dict[str, int] = {}
    for sent in content_sentences:
        for stem in {tok.stem for tok in sent}:
            doc_frequencies[stem] = doc_frequencies.get(stem, 0) + 1

    positional_signals = _build_positional_signals(content_sentences, text, language)
    return compute_tfidf_ap(
        document_terms=all_stems,
        corpus_document_frequencies=doc_frequencies,
        corpus_size=len(content_sentences),
        positional_signals=positional_signals,
    )


def _pick_display_surface(surfaces: list[str]) -> str:
    """Pick the most frequent surface form, tiebreaking on first occurrence.

    ``surfaces`` is iteration-ordered as the stems were seen, so when two
    surface forms occur equally often the earliest one wins.
    """
    counts: dict[str, int] = {}
    order: dict[str, int] = {}
    for index, surface in enumerate(surfaces):
        counts[surface] = counts.get(surface, 0) + 1
        if surface not in order:
            order[surface] = index
    # Sort by count DESC, then by first-seen index ASC. The first entry wins.
    best = min(counts.items(), key=lambda kv: (-kv[1], order[kv[0]]))
    return best[0]


def text_to_candidates(
    text: str,
    max_words: int = DEFAULT_MAX_WORDS,
    language: str = "auto",
    min_font_size: float = DEFAULT_MIN_FONT_SIZE,
    max_font_size: float = DEFAULT_MAX_FONT_SIZE,
    font_family: str = DEFAULT_FONT_FAMILY,
) -> list[WordCandidate]:
    """Orchestrate the Phase 3 NLP pipeline.

    Args:
        text: Raw input text. Markdown-style headings are detected heuristically.
        max_words: Hard cap on the number of returned candidates.
        language: ISO 639-1 code (``'en'`` / ``'de'``) or ``'auto'`` to run
            lingua detection first. ``'auto'`` raises
            `LanguageDetectionFailedError` on undetermined input.
        min_font_size: Smallest font size passed to `zipf_font_sizes`.
        max_font_size: Largest font size passed to `zipf_font_sizes`.
        font_family: Font family recorded on every emitted `WordCandidate`.

    Returns:
        Up to `max_words` `WordCandidate` instances, deterministically ordered
        by score DESC then stem ASC.
    """
    if max_words <= 0:
        return []

    resolved_language = _resolve_language(text, language)

    sentences = tokenize_sentences(text, resolved_language)
    content_sentences = _filter_content_sentences(sentences)
    if not content_sentences:
        return []

    all_stems: list[str] = []
    surfaces_by_stem: dict[str, list[str]] = {}
    for sent in content_sentences:
        for tok in sent:
            all_stems.append(tok.stem)
            surfaces_by_stem.setdefault(tok.stem, []).append(tok.surface)

    scores = _score_stems(content_sentences, all_stems, text, resolved_language)
    positive_scores = {stem: score for stem, score in scores.items() if score > 0}
    if not positive_scores:
        return []

    # Deterministic: score DESC, stem ASC as tiebreak.
    ranked = sorted(positive_scores.items(), key=lambda kv: (-kv[1], kv[0]))[:max_words]
    font_sizes = zipf_font_sizes(dict(ranked), min_size=min_font_size, max_size=max_font_size)

    return [
        WordCandidate(
            surface=_pick_display_surface(surfaces_by_stem[stem]),
            stem=stem,
            score=score,
            font_size=font_sizes[stem],
            font_family=font_family,
        )
        for stem, score in ranked
        if stem in font_sizes
    ]

"""TF-IDF with Adaptive Positional (TF-IDF-AP) scoring.

The "AP" extension multiplies the classical TF-IDF score by a positional
weight derived from where in the document the term appears (title, first
sentence, etc.). Blueprint Teil 1.3 claims +12.9% semantic precision over
raw TF-IDF for Chinese document clustering.

References:
    - raw/sources/AeroCloud-Blueprint.md Teil 1.3
    - .planning/phases/03-nlp-v1/03-CONTEXT.md D-07
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

_DEFAULT_POSITIONAL_BOOST = 0.5


@dataclass(frozen=True)
class PositionalSignal:
    """Positional boosts for a single term.

    Each boost is additive on top of the base weight of 1.0. A term that
    appears in both the title and the first sentence with default boost 0.5
    yields a positional weight of ``1.0 + 0.5 + 0.5 = 2.0``.
    """

    title: bool = False
    heading: bool = False
    first_sentence: bool = False
    emphasis: bool = False
    boost: float = _DEFAULT_POSITIONAL_BOOST

    def weight(self) -> float:
        """Return the final positional multiplier ``>= 1.0``."""
        base = 1.0
        hits = sum([self.title, self.heading, self.first_sentence, self.emphasis])
        return base + hits * self.boost


@dataclass(frozen=True)
class _TermStats:
    term: str
    count: int
    total_terms: int
    doc_count: int
    corpus_size: int
    positional: PositionalSignal = field(default_factory=PositionalSignal)

    def tf(self) -> float:
        if self.total_terms == 0:
            return 0.0
        return self.count / self.total_terms

    def idf(self) -> float:
        # Classical smoothed IDF: log((N + 1) / (df + 1)) + 1
        if self.corpus_size == 0:
            return 1.0
        return math.log((self.corpus_size + 1) / (self.doc_count + 1)) + 1.0

    def score(self) -> float:
        return self.tf() * self.idf() * self.positional.weight()


def compute_tfidf_ap(
    document_terms: list[str],
    corpus_document_frequencies: dict[str, int],
    corpus_size: int,
    positional_signals: dict[str, PositionalSignal] | None = None,
) -> dict[str, float]:
    """Return TF-IDF-AP scores for every unique term in ``document_terms``.

    Args:
        document_terms: Ordered list of stemmed tokens in a single document.
            Order is ignored for counting but preserved for callers that may
            want it.
        corpus_document_frequencies: ``stem -> number of documents containing it``
            computed over the full corpus used for IDF.
        corpus_size: Total number of documents in the corpus.
        positional_signals: Optional ``stem -> PositionalSignal`` map for the
            AP extension. Missing stems get default ``PositionalSignal()``.

    Returns:
        ``stem -> score`` dict. Scores are non-negative floats.
    """
    if not document_terms:
        return {}

    counts: dict[str, int] = {}
    for term in document_terms:
        counts[term] = counts.get(term, 0) + 1

    total_terms = len(document_terms)
    signals = positional_signals or {}

    scores: dict[str, float] = {}
    for term, count in counts.items():
        stats = _TermStats(
            term=term,
            count=count,
            total_terms=total_terms,
            doc_count=corpus_document_frequencies.get(term, 0),
            corpus_size=corpus_size,
            positional=signals.get(term, PositionalSignal()),
        )
        scores[term] = stats.score()

    return scores

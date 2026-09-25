"""Small-corpus fallback — IDF becomes noise below a threshold.

For corpora with fewer than 20 unique tokens, the IDF term destabilizes
the ranking (everything looks rare). We fall back to a linear scale of
raw term frequencies in that regime.

References:
    - .planning/research/PITFALLS.md pitfall M-1 (Zipf division-by-zero on small corpora)
    - .planning/phases/03-nlp-v1/03-CONTEXT.md D-09
"""

from __future__ import annotations

CORPUS_GUARD_THRESHOLD = 20


def is_small_corpus(unique_terms: int) -> bool:
    """Return True if the corpus is too small for reliable IDF."""
    return unique_terms < CORPUS_GUARD_THRESHOLD


def linear_fallback_scores(document_terms: list[str]) -> dict[str, float]:
    """Return ``stem -> normalized frequency`` for small corpora.

    The result is normalized so the most frequent term has score 1.0.
    """
    if not document_terms:
        return {}

    counts: dict[str, int] = {}
    for term in document_terms:
        counts[term] = counts.get(term, 0) + 1

    max_count = max(counts.values())
    if max_count == 0:
        return {}

    return {term: count / max_count for term, count in counts.items()}

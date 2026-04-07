"""AeroCloud NLP pipeline — Phase 3.

Phase 3 Wave 1 delivers the pure-Python mathematical core:

    >>> from aerocloud.nlp import compute_tfidf_ap, zipf_font_sizes, corpus_guard

Wave 2+ adds spaCy tokenization, language detection, and stopword filtering
as optional ``[nlp]`` dependencies.
"""

from __future__ import annotations

from aerocloud.nlp.corpus_guard import CORPUS_GUARD_THRESHOLD, is_small_corpus
from aerocloud.nlp.tfidf import PositionalSignal, compute_tfidf_ap
from aerocloud.nlp.zipf import zipf_font_sizes

__all__ = [
    "CORPUS_GUARD_THRESHOLD",
    "PositionalSignal",
    "compute_tfidf_ap",
    "is_small_corpus",
    "zipf_font_sizes",
]

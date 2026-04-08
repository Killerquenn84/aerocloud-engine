"""AeroCloud NLP pipeline — Phase 3.

Wave 1 delivers the pure-Python mathematical core (TF-IDF-AP + Zipf + corpus
guard). Wave 2 adds spaCy tokenization, lingua-based language detection, and
per-language stopword filtering — all gated behind the optional ``nlp`` extra::

    >>> from aerocloud.nlp import tokenize, detect_language, is_stopword
"""

from __future__ import annotations

from aerocloud.nlp.corpus_guard import CORPUS_GUARD_THRESHOLD, is_small_corpus
from aerocloud.nlp.language import detect_language, reset_detector
from aerocloud.nlp.pipeline import (
    DEFAULT_FONT_FAMILY,
    DEFAULT_MAX_FONT_SIZE,
    DEFAULT_MAX_WORDS,
    DEFAULT_MIN_FONT_SIZE,
    LanguageDetectionFailedError,
    text_to_candidates,
)
from aerocloud.nlp.stopwords import get_stopwords, is_stopword
from aerocloud.nlp.tfidf import PositionalSignal, compute_tfidf_ap
from aerocloud.nlp.tokenize import (
    SUPPORTED_LANGUAGES,
    MissingSpacyModelError,
    UnsupportedLanguageError,
    clear_registry,
    get_nlp,
    tokenize,
    tokenize_sentences,
)
from aerocloud.nlp.zipf import zipf_font_sizes

__all__ = [
    "CORPUS_GUARD_THRESHOLD",
    "DEFAULT_FONT_FAMILY",
    "DEFAULT_MAX_FONT_SIZE",
    "DEFAULT_MAX_WORDS",
    "DEFAULT_MIN_FONT_SIZE",
    "SUPPORTED_LANGUAGES",
    "LanguageDetectionFailedError",
    "MissingSpacyModelError",
    "PositionalSignal",
    "UnsupportedLanguageError",
    "clear_registry",
    "compute_tfidf_ap",
    "detect_language",
    "get_nlp",
    "get_stopwords",
    "is_small_corpus",
    "is_stopword",
    "reset_detector",
    "text_to_candidates",
    "tokenize",
    "tokenize_sentences",
    "zipf_font_sizes",
]

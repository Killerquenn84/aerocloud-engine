"""Per-language stopword filter backed by spaCy's builtin word lists.

Design decision (see wiki/discussions/2026-04-08-phase-03-wave-2-design.md):
we deliberately do NOT use the `stopwordsiso` PyPI package — its last release
was 2020-09-02 and it is marked `Development Status :: 3 - Alpha`. spaCy already
ships curated stopword lists per language (`spacy.lang.{en,de}.stop_words`),
pinned to a specific spaCy version, which gives us the reproducibility we need
without adding a dead dependency.

Wave 2 scope is English + German. Adding a new language is a one-liner in
`_STOPWORDS_BY_LANGUAGE`.
"""

from __future__ import annotations

from typing import Final

from spacy.lang.de.stop_words import STOP_WORDS as _DE_STOP_WORDS
from spacy.lang.en.stop_words import STOP_WORDS as _EN_STOP_WORDS

_EMPTY: Final[frozenset[str]] = frozenset()
_STOPWORDS_BY_LANGUAGE: Final[dict[str, frozenset[str]]] = {
    "en": frozenset(_EN_STOP_WORDS),
    "de": frozenset(_DE_STOP_WORDS),
}


def get_stopwords(language: str) -> frozenset[str]:
    """Return the stopword set for `language`, or an empty set if unknown.

    Unknown languages return an empty set instead of raising so that
    `tokenize()` never crashes on them — the caller decides whether empty
    stopwords are acceptable for its use-case.
    """
    return _STOPWORDS_BY_LANGUAGE.get(language, _EMPTY)


def is_stopword(word: str, language: str) -> bool:
    """Check whether `word` is a stopword in `language`.

    Case-insensitive: `"The"` and `"the"` are both treated as stopwords in
    English. spaCy's lists are already lowercase, so we lowercase the input.
    """
    return word.lower() in get_stopwords(language)

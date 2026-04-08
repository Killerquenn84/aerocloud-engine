"""spaCy tokenization adapter with thread-safe model registry.

Wave 2 of Phase 3. The public API is deliberately tiny: `tokenize(text, language)`
returns a list of `aerocloud.models.tokens.Token`. Models are lazy-loaded per
language into a module-level registry protected by an `RLock` (Celery workers
may call this concurrently from Phase 10 onwards).

Design decisions (see wiki/discussions/2026-04-08-phase-03-wave-2-design.md):
- Fail-fast on missing models via `MissingSpacyModelError` — no auto-download,
  because auto-download breaks CI, offline mode, and reproducibility.
- Stem fallback: `token.lemma_` if non-empty, otherwise `token.text.lower()`.
  `spacy.blank()` pipelines (used in unit tests) return empty lemmas, so the
  fallback keeps tests hermetic.
- All spaCy objects are kept behind an opaque `Any` boundary inside this module;
  callers only see `Token` / `list[Token]` which are fully typed.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any, Final

from aerocloud.models.tokens import Token
from aerocloud.nlp.stopwords import is_stopword

if TYPE_CHECKING:  # pragma: no cover - import only for type-checking clarity
    pass

SUPPORTED_LANGUAGES: Final[frozenset[str]] = frozenset({"en", "de"})
_DEFAULT_MODEL_BY_LANG: Final[dict[str, str]] = {
    "en": "en_core_web_sm",
    "de": "de_core_news_sm",
}

_registry: dict[str, Any] = {}
_registry_lock = threading.RLock()


class MissingSpacyModelError(RuntimeError):
    """Raised when a requested spaCy model is not installed.

    Install via (example for English):

        python -m spacy download en_core_web_sm
    """


class UnsupportedLanguageError(ValueError):
    """Raised for languages outside the Wave 2 scope (`en`, `de`)."""


def clear_registry() -> None:
    """Drop every cached pipeline. Test-only helper.

    Production code must not call this — it defeats the point of the cache.
    """
    with _registry_lock:
        _registry.clear()


def get_nlp(language: str) -> Any:
    """Return a cached spaCy `Language` for `language`, loading on first use.

    Thread-safe: concurrent cache misses are serialized by an RLock, and the
    double-check avoids re-loading once a competing thread has populated the
    entry. `spacy.load` is imported lazily so that a missing `nlp` extra only
    errors out at the first call site, not at module import time.
    """
    if language not in SUPPORTED_LANGUAGES:
        raise UnsupportedLanguageError(
            f"Wave 2 scope is {sorted(SUPPORTED_LANGUAGES)}; got {language!r}"
        )

    cached = _registry.get(language)
    if cached is not None:
        return cached

    with _registry_lock:
        cached = _registry.get(language)
        if cached is not None:
            return cached

        import spacy  # noqa: PLC0415 - lazy import keeps `nlp` extra optional

        model_name = _DEFAULT_MODEL_BY_LANG[language]
        try:
            nlp = spacy.load(model_name)
        except OSError as exc:
            raise MissingSpacyModelError(
                f"spaCy model {model_name!r} is not installed. "
                f"Run: python -m spacy download {model_name}"
            ) from exc
        _registry[language] = nlp
        return nlp


def _spacy_token_to_token(spacy_token: Any, language: str) -> Token | None:
    """Convert a spaCy `Token` to our `Token` model, or return None to drop."""
    if spacy_token.is_space or spacy_token.is_punct:
        return None
    surface = spacy_token.text
    # `spacy.blank(...)` pipelines emit empty lemmas. Fall back to the
    # lowercased surface so tests using blank pipelines still get usable
    # stems and stem-based counting stays correct.
    lemma = spacy_token.lemma_ or surface.lower()
    stem = lemma.lower()
    return Token(
        surface=surface,
        stem=stem,
        language=language,
        is_stopword=is_stopword(stem, language),
    )


def _ensure_sentence_boundaries(nlp: Any) -> None:
    """Attach a sentencizer if the pipeline cannot already produce sentences.

    `spacy.load('..._sm')` ships with a trained parser that already segments
    sentences, but `spacy.blank()` pipelines (used in unit tests) do not.
    We idempotently add a `sentencizer` in that case so `doc.sents` is always
    walkable regardless of how the pipeline was loaded.
    """
    if "parser" in nlp.pipe_names or "sentencizer" in nlp.pipe_names:
        return
    nlp.add_pipe("sentencizer")


def tokenize(text: str, language: str) -> list[Token]:
    """Tokenize `text` with the cached pipeline for `language`.

    Returns a list of `Token` with surface form, stem (lemma or lowercased
    surface), ISO language code, and stopword flag. Whitespace-only and
    punctuation tokens are dropped — only tokens that carry lexical content
    are returned, so downstream TF-IDF-AP scoring sees a clean stream.
    """
    nlp = get_nlp(language)
    doc = nlp(text)
    tokens: list[Token] = []
    for spacy_token in doc:
        token = _spacy_token_to_token(spacy_token, language)
        if token is not None:
            tokens.append(token)
    return tokens


def tokenize_sentences(text: str, language: str) -> list[list[Token]]:
    """Return sentence-grouped tokens for single-document IDF computation.

    The pipeline orchestrator uses this to treat sentences as "documents" for
    TF-IDF — a stem that appears in many sentences gets a lower IDF than one
    that clusters in a single sentence. The sentencizer is added lazily if
    the loaded pipeline cannot segment sentences on its own.
    """
    nlp = get_nlp(language)
    _ensure_sentence_boundaries(nlp)
    doc = nlp(text)
    sentences: list[list[Token]] = []
    for sent in doc.sents:
        sent_tokens: list[Token] = []
        for spacy_token in sent:
            token = _spacy_token_to_token(spacy_token, language)
            if token is not None:
                sent_tokens.append(token)
        if sent_tokens:
            sentences.append(sent_tokens)
    return sentences

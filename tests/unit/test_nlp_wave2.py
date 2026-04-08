"""Unit tests for Phase 3 Wave 2 — tokenize, language, stopwords.

Hermetic policy:
- `tokenize()` tests patch `spacy.load` to return a real `spacy.blank(...)`
  pipeline. This gives us an authentic `Doc`/`Token` object graph (so we
  exercise the real `is_space` / `is_punct` / `lemma_` attributes) without
  requiring the ~50 MB `*_core_*_sm` models to be installed.
- `detect_language()` tests use the real lingua library because its
  models are bundled as Rust wheels and cost ~50 ms to build once.
- Nothing in this file touches the network.
"""

from __future__ import annotations

import threading
from unittest.mock import patch

import pytest
import spacy

from aerocloud.nlp import (
    MissingSpacyModelError,
    UnsupportedLanguageError,
    clear_registry,
    detect_language,
    get_nlp,
    get_stopwords,
    is_stopword,
    reset_detector,
    tokenize,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_caches() -> None:
    """Wipe the tokenize registry and language detector singleton between tests."""
    clear_registry()
    reset_detector()


@pytest.fixture
def blank_en_loader():
    """Patch ``spacy.load`` so the English pipeline becomes ``spacy.blank('en')``."""
    with patch("spacy.load", side_effect=lambda _name: spacy.blank("en")) as loader:
        yield loader


@pytest.fixture
def blank_de_loader():
    """Patch ``spacy.load`` so the German pipeline becomes ``spacy.blank('de')``."""
    with patch("spacy.load", side_effect=lambda _name: spacy.blank("de")) as loader:
        yield loader


# ---------------------------------------------------------------------------
# stopwords.py
# ---------------------------------------------------------------------------


class TestStopwords:
    def test_english_stopword_hit(self) -> None:
        assert is_stopword("the", "en") is True
        assert is_stopword("The", "en") is True  # case-insensitive

    def test_english_content_word(self) -> None:
        assert is_stopword("fox", "en") is False

    def test_german_stopword_hit(self) -> None:
        assert is_stopword("der", "de") is True
        assert is_stopword("Und", "de") is True

    def test_german_content_word(self) -> None:
        assert is_stopword("hund", "de") is False

    def test_unknown_language_returns_empty(self) -> None:
        assert is_stopword("anything", "xx") is False
        assert get_stopwords("xx") == frozenset()

    def test_nonempty_lists(self) -> None:
        # Guard against accidental version drift that empties the lists.
        assert len(get_stopwords("en")) >= 100
        assert len(get_stopwords("de")) >= 100


# ---------------------------------------------------------------------------
# tokenize.py
# ---------------------------------------------------------------------------


class TestTokenize:
    def test_rejects_unsupported_language(self) -> None:
        with pytest.raises(UnsupportedLanguageError):
            get_nlp("fr")

    def test_missing_model_raises_typed_error(self) -> None:
        with patch("spacy.load", side_effect=OSError("not found")):
            with pytest.raises(MissingSpacyModelError) as exc:
                get_nlp("en")
            assert "en_core_web_sm" in str(exc.value)

    def test_returns_tokens_for_english_text(self, blank_en_loader) -> None:
        tokens = tokenize("The quick brown fox jumps.", "en")
        surfaces = [t.surface for t in tokens]
        assert surfaces == ["The", "quick", "brown", "fox", "jumps"]  # punct dropped
        assert all(t.language == "en" for t in tokens)

    def test_stopword_flag_is_set(self, blank_en_loader) -> None:
        tokens = tokenize("The fox", "en")
        by_surface = {t.surface: t for t in tokens}
        assert by_surface["The"].is_stopword is True
        assert by_surface["fox"].is_stopword is False

    def test_stem_falls_back_to_lowercased_surface(self, blank_en_loader) -> None:
        # spacy.blank() returns empty lemmas — the fallback must kick in so
        # downstream TF-IDF-AP counting still has a stable key.
        tokens = tokenize("Fox", "en")
        assert tokens[0].stem == "fox"

    def test_drops_whitespace_and_punctuation(self, blank_en_loader) -> None:
        tokens = tokenize("  fox , jumps !  ", "en")
        surfaces = [t.surface for t in tokens]
        assert surfaces == ["fox", "jumps"]

    def test_german_pipeline(self, blank_de_loader) -> None:
        tokens = tokenize("Der Hund bellt.", "de")
        surfaces = [t.surface for t in tokens]
        assert surfaces == ["Der", "Hund", "bellt"]
        by_surface = {t.surface: t for t in tokens}
        assert by_surface["Der"].is_stopword is True
        assert by_surface["Hund"].is_stopword is False

    def test_registry_caches_instance(self, blank_en_loader) -> None:
        first = get_nlp("en")
        second = get_nlp("en")
        assert first is second
        # spacy.load was called exactly once despite two get_nlp calls.
        assert blank_en_loader.call_count == 1

    def test_clear_registry_forces_reload(self, blank_en_loader) -> None:
        get_nlp("en")
        clear_registry()
        get_nlp("en")
        assert blank_en_loader.call_count == 2

    def test_registry_is_thread_safe(self, blank_en_loader) -> None:
        # 10 threads race on a cold cache. With RLock + double-check, spacy.load
        # must run at most once.
        results: list[object] = []
        barrier = threading.Barrier(10)

        def worker() -> None:
            barrier.wait()
            results.append(get_nlp("en"))

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 10
        # All callers see the same cached instance.
        assert all(r is results[0] for r in results)
        assert blank_en_loader.call_count == 1


# ---------------------------------------------------------------------------
# language.py
# ---------------------------------------------------------------------------


class TestDetectLanguage:
    def test_detects_english(self) -> None:
        assert detect_language("The quick brown fox jumps over the lazy dog.") == "en"

    def test_detects_german(self) -> None:
        assert (
            detect_language("Der schnelle braune Fuchs springt ueber den faulen Hund.") == "de"
        )

    def test_empty_string_is_undetermined(self) -> None:
        assert detect_language("") == "und"
        assert detect_language("   ") == "und"

    def test_high_threshold_falls_back_to_undetermined(self) -> None:
        # "fox" alone is too short/ambiguous for a confident EN/DE decision
        # when we crank the threshold. The fallback keeps callers from acting
        # on noise.
        assert detect_language("fox", confidence_threshold=0.99) == "und"

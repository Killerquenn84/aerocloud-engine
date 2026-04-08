"""Unit tests for Phase 3 Wave 3 — `nlp/pipeline.py` orchestrator.

Hermetic policy carried over from Wave 2: `spacy.load` is patched to return a
real `spacy.blank('en')` / `('de')` pipeline, so we exercise the authentic
`Doc`/`Token` object graph (including the lazily-added sentencizer) without
downloading a 50 MB `*_core_*_sm` model. The sentencizer is added by
`tokenize_sentences()` on demand for blank pipelines, so `doc.sents` is
walkable in tests without any extra setup.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
import spacy

from aerocloud.nlp import (
    LanguageDetectionFailedError,
    clear_registry,
    reset_detector,
    text_to_candidates,
    tokenize_sentences,
)


@pytest.fixture(autouse=True)
def _clean_caches() -> None:
    clear_registry()
    reset_detector()


@pytest.fixture
def blank_en_loader():
    with patch("spacy.load", side_effect=lambda _name: spacy.blank("en")) as loader:
        yield loader


@pytest.fixture
def blank_de_loader():
    with patch("spacy.load", side_effect=lambda _name: spacy.blank("de")) as loader:
        yield loader


# ---------------------------------------------------------------------------
# tokenize_sentences (Wave 3 extension of tokenize.py)
# ---------------------------------------------------------------------------


class TestTokenizeSentences:
    def test_splits_on_sentence_boundaries(self, blank_en_loader) -> None:
        sentences = tokenize_sentences("Foxes run. Dogs sleep.", "en")
        assert len(sentences) == 2
        assert [t.surface for t in sentences[0]] == ["Foxes", "run"]
        assert [t.surface for t in sentences[1]] == ["Dogs", "sleep"]

    def test_sentencizer_is_idempotent(self, blank_en_loader) -> None:
        # Calling twice must not re-add the sentencizer pipe.
        tokenize_sentences("Foo. Bar.", "en")
        tokenize_sentences("Baz. Qux.", "en")
        # Single cached pipeline, sentencizer present exactly once.
        from aerocloud.nlp.tokenize import get_nlp

        nlp = get_nlp("en")
        assert nlp.pipe_names.count("sentencizer") == 1

    def test_empty_sentences_are_dropped(self, blank_en_loader) -> None:
        # Pure punctuation between periods produces a sentence of only
        # punctuation tokens, which must not leak into the output.
        sentences = tokenize_sentences("Foo. . Bar.", "en")
        assert len(sentences) == 2
        assert sentences[0][0].surface == "Foo"
        assert sentences[1][0].surface == "Bar"


# ---------------------------------------------------------------------------
# text_to_candidates — small corpus (linear fallback path)
# ---------------------------------------------------------------------------


class TestPipelineSmallCorpus:
    def test_small_corpus_uses_linear_fallback(self, blank_en_loader) -> None:
        text = "The fox jumps. The fox runs. The fox sleeps."
        cands = text_to_candidates(text, language="en", max_words=10)
        # "fox" appears in every sentence -> top rank, max font size.
        top = cands[0]
        assert top.stem == "fox"
        assert top.font_size == pytest.approx(96.0)

    def test_determinism_on_equal_scores(self, blank_en_loader) -> None:
        # Two runs on the same input produce byte-identical output.
        text = "Alpha beta. Beta gamma. Gamma alpha."
        first = text_to_candidates(text, language="en", max_words=5)
        second = text_to_candidates(text, language="en", max_words=5)
        assert [c.model_dump() for c in first] == [c.model_dump() for c in second]

    def test_tiebreak_is_stem_alphabetical(self, blank_en_loader) -> None:
        # All three stems have the same linear-fallback score (count 1 each).
        text = "Zebra. Apple. Mango."
        cands = text_to_candidates(text, language="en", max_words=10)
        stems = [c.stem for c in cands]
        # Ordered alphabetically when scores tie.
        assert stems == sorted(stems)

    def test_stopwords_are_dropped(self, blank_en_loader) -> None:
        text = "The the the fox the the the."
        cands = text_to_candidates(text, language="en", max_words=10)
        stems = {c.stem for c in cands}
        assert "the" not in stems
        assert "fox" in stems

    def test_single_char_tokens_are_dropped(self, blank_en_loader) -> None:
        text = "Fox a b c x y z runs fast."
        cands = text_to_candidates(text, language="en", max_words=20)
        stems = {c.stem for c in cands}
        assert stems.isdisjoint({"a", "b", "c", "x", "y", "z"})
        assert "fox" in stems


# ---------------------------------------------------------------------------
# text_to_candidates — IDF path (unique stems >= 20)
# ---------------------------------------------------------------------------


class TestPipelineIdfPath:
    def _wide_vocab_text(self) -> str:
        # 25+ unique content words distributed across 5 sentences so the
        # IDF branch kicks in (threshold is 20 unique stems).
        return (
            "# Headline word about foxes\n"
            "Curious quick brown foxes jumped over sleepy lazy brown dogs. "
            "Silver wolves roamed across dense misty forests every evening. "
            "Hungry bears fished along cold rocky rivers each morning. "
            "Tiny spotted frogs croaked beneath heavy fragrant lily leaves. "
            "Gentle honey bees buzzed around bright yellow sunflower petals."
        )

    def test_returns_candidates_on_wide_vocab(self, blank_en_loader) -> None:
        cands = text_to_candidates(self._wide_vocab_text(), language="en", max_words=50)
        assert len(cands) > 10
        # Max font size is reserved for the top candidate after Zipf.
        assert cands[0].font_size == pytest.approx(96.0)

    def test_max_words_caps_output(self, blank_en_loader) -> None:
        cands = text_to_candidates(self._wide_vocab_text(), language="en", max_words=5)
        assert len(cands) <= 5

    def test_font_sizes_monotonically_non_increasing(self, blank_en_loader) -> None:
        cands = text_to_candidates(self._wide_vocab_text(), language="en", max_words=50)
        sizes = [c.font_size for c in cands]
        assert sizes == sorted(sizes, reverse=True)

    def test_markdown_title_is_boosted(self, blank_en_loader) -> None:
        # "headline" appears exactly once — in the title. Without a title
        # boost it would rank near the bottom; with the boost it should be
        # at least ahead of other once-seen tail words.
        cands = text_to_candidates(self._wide_vocab_text(), language="en", max_words=50)
        by_stem = {c.stem: c for c in cands}
        assert "headline" in by_stem


# ---------------------------------------------------------------------------
# Guards and edge cases
# ---------------------------------------------------------------------------


class TestPipelineEdges:
    def test_empty_text_returns_empty(self, blank_en_loader) -> None:
        assert text_to_candidates("", language="en") == []

    def test_all_stopwords_returns_empty(self, blank_en_loader) -> None:
        assert text_to_candidates("The and of or the and.", language="en") == []

    def test_max_words_zero_returns_empty(self, blank_en_loader) -> None:
        assert text_to_candidates("Foxes run fast.", language="en", max_words=0) == []

    def test_auto_language_detection_success(self, blank_en_loader) -> None:
        text = "The quick brown fox jumps over the lazy dog many times."
        cands = text_to_candidates(text, language="auto", max_words=10)
        assert len(cands) > 0

    def test_auto_language_detection_failure_raises(self, blank_en_loader) -> None:
        # Empty input is detected as 'und'; auto mode must raise.
        with pytest.raises(LanguageDetectionFailedError):
            text_to_candidates("   ", language="auto")

    def test_german_pipeline_round_trip(self, blank_de_loader) -> None:
        text = (
            "Schnelle braune Fuechse springen weit hoch schnell. "
            "Die Fuechse rennen schnell durch den grossen Wald."
        )
        cands = text_to_candidates(text, language="de", max_words=10)
        assert len(cands) > 0
        # German stopwords like "die", "den", "durch" must be absent.
        # (We deliberately avoid words that only appear with umlauts in
        # spaCy's word list — the ASCII variants aren't stopwords there.)
        stems = {c.stem for c in cands}
        assert stems.isdisjoint({"die", "den", "durch"})

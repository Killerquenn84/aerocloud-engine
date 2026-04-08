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
from aerocloud.nlp.pipeline import (
    _MAX_TITLE_CHARS,
    _TITLE_SCAN_BUDGET_CHARS,
    _extract_markdown_title_line,
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
        # All three stems live in the SAME sentence so they share the same
        # positional weight (first_sentence boost) AND have equal counts in
        # the linear fallback. The remaining tiebreak must be alphabetical.
        text = "Zebra apple mango."
        cands = text_to_candidates(text, language="en", max_words=10)
        stems = [c.stem for c in cands]
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


# ---------------------------------------------------------------------------
# Wave 4 hardening — fixes from the 3-AI code review
# ---------------------------------------------------------------------------


class TestExtractMarkdownTitleLine:
    """Direct unit tests for the title extractor (Codex re-review request).

    The previous oversized-title test was indirect — it only proved the
    pipeline did not crash. These tests pin the helper's contract directly.
    """

    def test_returns_title_for_normal_heading(self) -> None:
        assert _extract_markdown_title_line("# fox news\n\nbody") == "fox news"

    def test_skips_blank_lines_before_heading(self) -> None:
        assert _extract_markdown_title_line("\n  \n# real title\nbody") == "real title"

    def test_returns_none_when_first_line_is_not_heading(self) -> None:
        assert _extract_markdown_title_line("plain text\n# would-be heading") is None

    def test_returns_none_for_empty_input(self) -> None:
        assert _extract_markdown_title_line("") is None

    def test_returns_none_for_oversized_first_line(self) -> None:
        # First non-empty line longer than _MAX_TITLE_CHARS must be rejected
        # without ever tokenizing it. We deliberately go ten times over the
        # cap so a future increase still triggers the guard.
        oversized = "# " + ("foo " * (_MAX_TITLE_CHARS * 10))
        assert _extract_markdown_title_line(oversized) is None

    def test_scan_budget_bails_on_huge_input_without_newlines(self) -> None:
        # 1 MB string with no newlines and no leading heading. We must NOT
        # walk the whole string — the scan budget bounds the work.
        huge = "x" * (_TITLE_SCAN_BUDGET_CHARS * 256)
        assert _extract_markdown_title_line(huge) is None

    def test_title_at_exact_cap_is_kept(self) -> None:
        # The cap counts the FULL line including the "# " prefix. A line of
        # exactly _MAX_TITLE_CHARS characters must still be accepted.
        body = "y" * (_MAX_TITLE_CHARS - 2)
        assert _extract_markdown_title_line(f"# {body}\nbody") == body

    def test_title_one_char_over_cap_is_rejected(self) -> None:
        body = "y" * (_MAX_TITLE_CHARS - 1)  # full line is _MAX_TITLE_CHARS + 1
        assert _extract_markdown_title_line(f"# {body}\nbody") is None


class TestWave4Hardening:
    def test_oversized_first_line_pipeline_does_not_crash(self, blank_en_loader) -> None:
        # End-to-end smoke: 10 KB markdown title + body must not crash and
        # must still emit candidates from the body. Direct semantic proof
        # that the title was rejected lives in
        # TestExtractMarkdownTitleLine.test_returns_none_for_oversized_first_line.
        oversized = "# " + ("foo " * 5000)
        body = "\n\nReal sentence one. Real sentence two."
        text = oversized + body
        cands = text_to_candidates(text, language="en", max_words=20)
        assert len(cands) > 0

    def test_long_input_without_newlines_does_not_oom(self, blank_en_loader) -> None:
        # 50 KB single line with no newlines — splitlines() would have
        # materialized the whole list. Our scan-budget walker bails fast.
        text = "fox " * 12500  # ~50 KB
        cands = text_to_candidates(text, language="en", max_words=5)
        assert len(cands) >= 1
        assert cands[0].stem == "fox"

    def test_symbol_tokens_are_dropped(self, blank_en_loader) -> None:
        # Code-snippet syntax leaks under spaCy's SYM category and used to
        # pass the punctuation filter. Now it must be excluded.
        text = "fox runs == != => + - * / & | ^ % $ # @ . fast."
        cands = text_to_candidates(text, language="en", max_words=20)
        stems = {c.stem for c in cands}
        forbidden = {"==", "!=", "=>", "+", "-", "*", "/", "&", "|", "^", "%", "$", "@"}
        assert stems.isdisjoint(forbidden)
        assert "fox" in stems

    def test_pure_numeric_tokens_are_dropped(self, blank_en_loader) -> None:
        # Year numbers in business reports flooded the cloud before. Now
        # tokens that contain no alphabetic character at all are dropped.
        text = "Revenue 2024 grew. Revenue 2025 stable. Revenue 2026 forecast."
        cands = text_to_candidates(text, language="en", max_words=20)
        stems = {c.stem for c in cands}
        assert stems.isdisjoint({"2024", "2025", "2026", "100.0"})
        assert "revenue" in stems

    def test_alphanumeric_tokens_are_kept(self, blank_en_loader) -> None:
        # Tokens like "covid-19" or "iso8601" must NOT be dropped — they
        # contain alphabetic characters and are real content.
        text = "covid-19 spread fast. covid-19 tracking matters."
        cands = text_to_candidates(text, language="en", max_words=20)
        stems = {c.stem for c in cands}
        assert "covid-19" in stems

    def test_small_corpus_applies_title_boost(self, blank_en_loader) -> None:
        # All content words appear exactly once, so the linear-fallback path
        # gives them equal base scores. The only thing that can break the tie
        # is the positional boost. With the F-2 fix the title stem ('headline')
        # gets title=True AND first_sentence=True (weight 2.0) while the body
        # stems get weight 1.0 — so 'headline' must strictly outscore 'dog'.
        # Without the fix the small-corpus path would skip positional signals
        # entirely and 'headline' would tie with the rest.
        text = "# headline.\n\ndog runs. cat flies."
        cands = text_to_candidates(text, language="en", max_words=10)
        by_stem = {c.stem: c for c in cands}
        assert "headline" in by_stem
        assert by_stem["headline"].score > by_stem["dog"].score

    def test_invalid_min_font_size_raises_early(self, blank_en_loader) -> None:
        with pytest.raises(ValueError, match="min_font_size"):
            text_to_candidates("fox runs.", language="en", min_font_size=0)

    def test_invalid_max_font_size_raises_early(self, blank_en_loader) -> None:
        with pytest.raises(ValueError, match="max_font_size"):
            text_to_candidates("fox runs.", language="en", min_font_size=20, max_font_size=10)

    def test_font_validation_runs_before_tokenization(self, blank_en_loader) -> None:
        # If the font params are invalid, we must NOT have called spacy.load
        # at all — validation is at the very top of the function.
        with pytest.raises(ValueError):
            text_to_candidates("fox runs.", language="en", min_font_size=-1)
        assert blank_en_loader.call_count == 0

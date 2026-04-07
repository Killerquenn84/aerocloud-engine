"""Tests for Phase 3 Wave 1 NLP core: TF-IDF-AP, Zipf, corpus guard."""

from __future__ import annotations

import math

import pytest

from aerocloud.nlp import (
    CORPUS_GUARD_THRESHOLD,
    PositionalSignal,
    compute_tfidf_ap,
    is_small_corpus,
    zipf_font_sizes,
)
from aerocloud.nlp.corpus_guard import linear_fallback_scores

# ---------- TF-IDF-AP ----------


def test_tfidf_empty_document() -> None:
    assert compute_tfidf_ap([], {}, 0) == {}


def test_tfidf_single_term_single_doc() -> None:
    scores = compute_tfidf_ap(["hello"], {"hello": 1}, 1)
    assert "hello" in scores
    assert scores["hello"] > 0


def test_tfidf_common_vs_rare_term() -> None:
    doc = ["the", "the", "the", "quantum"]
    df = {"the": 100, "quantum": 1}
    scores = compute_tfidf_ap(doc, df, 100)
    # "quantum" is rare in corpus -> higher IDF -> higher score despite lower TF
    assert scores["quantum"] > scores["the"]


def test_positional_signal_default_weight() -> None:
    sig = PositionalSignal()
    assert sig.weight() == 1.0


def test_positional_signal_title_boost() -> None:
    sig = PositionalSignal(title=True)
    assert sig.weight() == pytest.approx(1.5)


def test_positional_signal_multiple_boosts() -> None:
    sig = PositionalSignal(title=True, first_sentence=True, emphasis=True)
    assert sig.weight() == pytest.approx(2.5)


def test_tfidf_ap_positional_boost() -> None:
    doc = ["apple", "banana"]
    df = {"apple": 1, "banana": 1}
    signals = {"apple": PositionalSignal(title=True)}
    scores = compute_tfidf_ap(doc, df, 1, positional_signals=signals)
    # Apple has title boost -> higher score
    assert scores["apple"] > scores["banana"]


def test_tfidf_non_negative() -> None:
    doc = ["a", "b", "c", "a"]
    df = {"a": 5, "b": 3, "c": 1}
    scores = compute_tfidf_ap(doc, df, 10)
    for score in scores.values():
        assert score >= 0


# ---------- Zipf ----------


def test_zipf_empty() -> None:
    assert zipf_font_sizes({}) == {}


def test_zipf_all_zero_scores_filtered() -> None:
    assert zipf_font_sizes({"a": 0.0, "b": 0.0}) == {}


def test_zipf_negative_scores_filtered() -> None:
    result = zipf_font_sizes({"a": -1.0, "b": 0.5})
    assert "a" not in result
    assert "b" in result


def test_zipf_top_word_gets_max_size() -> None:
    scores = {"big": 10.0, "medium": 5.0, "small": 1.0}
    sizes = zipf_font_sizes(scores, min_size=10.0, max_size=96.0)
    assert sizes["big"] == pytest.approx(96.0)
    assert sizes["small"] == pytest.approx(10.0)
    # Medium is between
    assert 10.0 < sizes["medium"] < 96.0


def test_zipf_equal_scores_get_same_size() -> None:
    scores = {"a": 1.0, "b": 1.0, "c": 1.0}
    sizes = zipf_font_sizes(scores)
    assert sizes["a"] == sizes["b"] == sizes["c"]


def test_zipf_log_distribution() -> None:
    # Geometric sequence -> linear rank distribution in log space
    scores = {"a": 100.0, "b": 10.0, "c": 1.0}
    sizes = zipf_font_sizes(scores, min_size=10.0, max_size=100.0)
    # log(100/100) = 0, log(100/10) = 1*ln(10), log(100/1) = 2*ln(10)
    # -> fractions 0, 0.5, 1.0 -> sizes 100, 55, 10
    assert sizes["a"] == pytest.approx(100.0)
    assert sizes["b"] == pytest.approx(55.0, rel=0.01)
    assert sizes["c"] == pytest.approx(10.0)


def test_zipf_validates_min_size_positive() -> None:
    with pytest.raises(ValueError, match="min_size"):
        zipf_font_sizes({"a": 1.0}, min_size=0.0)


def test_zipf_validates_max_greater_than_min() -> None:
    with pytest.raises(ValueError, match="max_size"):
        zipf_font_sizes({"a": 1.0}, min_size=10.0, max_size=5.0)


# ---------- Corpus Guard ----------


def test_corpus_guard_threshold() -> None:
    assert CORPUS_GUARD_THRESHOLD == 20


def test_is_small_corpus_below_threshold() -> None:
    assert is_small_corpus(19) is True
    assert is_small_corpus(0) is True


def test_is_small_corpus_at_threshold() -> None:
    assert is_small_corpus(20) is False
    assert is_small_corpus(100) is False


def test_linear_fallback_empty() -> None:
    assert linear_fallback_scores([]) == {}


def test_linear_fallback_normalizes_to_one() -> None:
    scores = linear_fallback_scores(["a", "a", "a", "b", "c"])
    assert scores["a"] == pytest.approx(1.0)
    assert scores["b"] == pytest.approx(1 / 3)
    assert scores["c"] == pytest.approx(1 / 3)


def test_linear_fallback_no_nan_on_single_term() -> None:
    scores = linear_fallback_scores(["only"])
    assert scores["only"] == pytest.approx(1.0)
    assert not math.isnan(scores["only"])

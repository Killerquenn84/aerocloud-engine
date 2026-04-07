"""Round-trip serialization tests for all Pydantic models."""

from __future__ import annotations

from datetime import UTC, datetime

from aerocloud.models import (
    AeroCloudBase,
    BehaviorDescriptor,
    LayoutScore,
    MapElitesEntry,
    PlacedWord,
    RenderError,
    RenderRequest,
    RenderResult,
    ScoredWord,
    Shape,
    ShapeMetadata,
    Token,
    WordCandidate,
)


def _roundtrip(model: AeroCloudBase) -> None:
    # Use JSON round-trip (model_dump_json -> model_validate_json) because
    # strict mode rejects coerced datetime strings in model_validate(dict),
    # but model_validate_json natively handles ISO-8601 strings.
    payload = model.model_dump_json()
    cls = type(model)
    restored = cls.model_validate_json(payload)
    assert restored == model


def test_token_roundtrip() -> None:
    t = Token(surface="Hello", stem="hello", language="en", is_stopword=False)
    _roundtrip(t)


def test_scored_word_roundtrip() -> None:
    w = ScoredWord(
        surface="quick", stem="quick", tf=0.5, idf=1.2, positional_weight=1.1, score=0.66
    )
    _roundtrip(w)


def test_word_candidate_roundtrip() -> None:
    c = WordCandidate(surface="brown", stem="brown", score=0.8, font_size=42.0)
    _roundtrip(c)


def test_shape_roundtrip() -> None:
    meta = ShapeMetadata(width=1024, height=1024, bbox_area_pixels=500_000, fill_ratio=0.47)
    s = Shape(shape_hash="a" * 64, metadata=meta)
    _roundtrip(s)


def test_placed_word_roundtrip() -> None:
    pw = PlacedWord(surface="fox", font_family="Inter", font_size=24.0, x=100.0, y=200.0)
    _roundtrip(pw)


def test_layout_score_roundtrip() -> None:
    ls = LayoutScore(
        layout_coverage=0.9,
        layout_uniformity=0.85,
        space_saving=0.7,
        compactness=1.2,
        aspect_ratio=1.618,
        fidelity=0.95,
    )
    _roundtrip(ls)


def test_map_elites_entry_roundtrip() -> None:
    now = datetime.now(UTC)
    desc = BehaviorDescriptor(
        shape_fidelity=0.9, rotation_ratio=0.2, symmetry=0.7, semantic_clustering=0.5
    )
    e = MapElitesEntry(
        bin_id="0x1234", descriptor=desc, fitness=0.88, created_at=now, updated_at=now
    )
    _roundtrip(e)


def test_render_request_roundtrip() -> None:
    req = RenderRequest(text="The quick brown fox", shape_b64="aGVsbG8=")
    _roundtrip(req)


def test_render_result_roundtrip() -> None:
    score = LayoutScore(
        layout_coverage=0.9,
        layout_uniformity=0.85,
        space_saving=0.7,
        compactness=1.2,
        aspect_ratio=1.618,
        fidelity=0.95,
    )
    pw = PlacedWord(surface="fox", font_family="Inter", font_size=24.0, x=100.0, y=200.0)
    res = RenderResult(
        reproducibility_id="sha256:abc",
        placed_words=[pw],
        score=score,
        png_b64="iVBORw0KGgo=",
        elapsed_ms=123,
    )
    _roundtrip(res)


def test_render_error_roundtrip() -> None:
    err = RenderError(
        error_code="INVALID_INPUT", message="text too short", details={"field": "text"}
    )
    _roundtrip(err)


def test_models_are_frozen() -> None:
    t = Token(surface="a", stem="a", language="en")
    try:
        t.surface = "b"  # type: ignore[misc]
    except (AttributeError, TypeError, Exception):
        # Pydantic 2 raises ValidationError; covered by broad except
        return
    raise AssertionError("frozen model allowed mutation")


def test_models_forbid_extra() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Token.model_validate({"surface": "x", "stem": "x", "language": "en", "extra": "nope"})

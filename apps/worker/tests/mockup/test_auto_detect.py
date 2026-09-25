"""Sprint P24 — Auto-detect BDD scenarios 1-8.

Scenarios that need a contrived multi-smart-object PSD are tested by mocking
``_collect_all_smart_objects`` — psd-tools cannot easily synthesise PSDs with
multiple Smart Objects with controlled names. Scenarios with a real-world
fixture (3, 4) drive the end-to-end auto-detect path against the actual
on-disk PSDs.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable
from unittest.mock import patch

import pytest
from psd_tools import PSDImage

from aerocloud_worker.mockup import (
    AmbiguousLayerError,
    DEFAULT_LAYER_PRIORITY,
    NoSmartObjectError,
    SmartObjectInfo,
    locate_smart_object,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _so_info(name: str, index: int = 0) -> SmartObjectInfo:
    """Build a dummy SmartObjectInfo for auto-detect isolation tests."""
    return SmartObjectInfo(
        layer_name=name,
        transform_box=(0.0, 0.0, 100.0, 0.0, 100.0, 100.0, 0.0, 100.0),
        bbox=(0, 0, 100, 100),
        layer_index=index,
    )


def _patch_candidates(candidates: Iterable[SmartObjectInfo]):
    """Patch the collector so the auto-detect logic runs in isolation."""
    return patch(
        "aerocloud_worker.mockup.smart_object._collect_all_smart_objects",
        return_value=list(candidates),
    )


# ---------------------------------------------------------------------------
# Sanity: priority constant matches the spec.
# ---------------------------------------------------------------------------


def test_default_layer_priority_matches_spec() -> None:
    assert DEFAULT_LAYER_PRIORITY == [
        "WORDCLOUD",
        "Replace me",
        "Your artwork here",
    ]


# ---------------------------------------------------------------------------
# Scenario 1: Engine findet "WORDCLOUD" ohne explizite Angabe
# ---------------------------------------------------------------------------


def test_scenario_1_wordcloud_auto_detected() -> None:
    """No real fixture with a 'WORDCLOUD' layer exists yet — auto-detect logic
    is verified in isolation by mocking the collector."""
    candidates = [_so_info("WORDCLOUD", 1), _so_info("Background-Texture", 0)]
    psd = object()  # type: ignore[assignment]
    with _patch_candidates(candidates):
        info = locate_smart_object(psd, layer_name=None)  # type: ignore[arg-type]
    assert info.layer_name == "WORDCLOUD"


# ---------------------------------------------------------------------------
# Scenario 2: Explizit > Auto-Detect
# ---------------------------------------------------------------------------


def test_scenario_2_explicit_layer_name_wins_over_wordcloud(
    poster_frame_psd: Path,
) -> None:
    """Even when auto-detect would pick something else, an explicit
    layer_name short-circuits the priority list. We use the real
    poster-frame PSD (has 'Replace me') and force explicit selection."""
    psd = PSDImage.open(poster_frame_psd)
    info = locate_smart_object(psd, layer_name="Replace me")
    assert info.layer_name == "Replace me"


# ---------------------------------------------------------------------------
# Scenario 3: Fallback "Replace me" — real fixture
# ---------------------------------------------------------------------------


def test_scenario_3_auto_detect_replace_me_on_real_fixture(
    poster_frame_psd: Path,
) -> None:
    psd = PSDImage.open(poster_frame_psd)
    info = locate_smart_object(psd, layer_name=None)
    assert info.layer_name == "Replace me"
    # Sanity: bbox matches what Phase-A spike recorded.
    assert info.bbox == (532, 326, 1766, 2050)


# ---------------------------------------------------------------------------
# Scenario 4: Fallback "Your artwork here" — real fixture
# ---------------------------------------------------------------------------


_PHOTO_FRAME_FIXTURE = (
    Path(__file__).resolve().parents[6] / "tests" / "fixtures" / "photo-frame-008.psd"
)


@pytest.fixture(scope="session")
def photo_frame_psd() -> Path:
    if not _PHOTO_FRAME_FIXTURE.exists():
        pytest.skip(
            f"Fixture missing: {_PHOTO_FRAME_FIXTURE}. See tests/fixtures/README.md"
        )
    return _PHOTO_FRAME_FIXTURE


def test_scenario_4_auto_detect_your_artwork_here_on_real_fixture(
    photo_frame_psd: Path,
) -> None:
    psd = PSDImage.open(photo_frame_psd)
    info = locate_smart_object(psd, layer_name=None)
    assert info.layer_name == "Your artwork here"


# ---------------------------------------------------------------------------
# Scenario 5: Pattern-Match *_Design
# ---------------------------------------------------------------------------


def test_scenario_5_pattern_match_design_suffix() -> None:
    candidates = [
        _so_info("Picture Design", 1),
        _so_info("Picture Target", 2),
        _so_info("Background", 0),
    ]
    # "Picture Target" is also a smart object but doesn't end in "Design".
    psd = object()
    with _patch_candidates(candidates):
        info = locate_smart_object(psd, layer_name=None)  # type: ignore[arg-type]
    assert info.layer_name == "Picture Design"


def test_scenario_5b_pattern_match_design_contains_when_no_suffix() -> None:
    """Coverage for the contains-Design fallback (single match)."""
    candidates = [
        _so_info("My-Design-Stub", 1),
        _so_info("Generic Smart Object", 0),
    ]
    psd = object()
    with _patch_candidates(candidates):
        info = locate_smart_object(psd, layer_name=None)  # type: ignore[arg-type]
    assert info.layer_name == "My-Design-Stub"


# ---------------------------------------------------------------------------
# Scenario 6: Genau 1 Smart Object → nimm es
# ---------------------------------------------------------------------------


def test_scenario_6_single_smart_object_auto_picked() -> None:
    candidates = [_so_info("FooBar", 0)]
    psd = object()
    with _patch_candidates(candidates):
        info = locate_smart_object(psd, layer_name=None)  # type: ignore[arg-type]
    assert info.layer_name == "FooBar"


# ---------------------------------------------------------------------------
# Scenario 7: Ambiguous → AmbiguousLayerError
# ---------------------------------------------------------------------------


def test_scenario_7_ambiguous_raises_with_candidate_list() -> None:
    candidates = [
        _so_info("Frame-A", 0),
        _so_info("Frame-B", 1),
        _so_info("Frame-C", 2),
    ]
    psd = object()
    with _patch_candidates(candidates), pytest.raises(AmbiguousLayerError) as exc:
        locate_smart_object(psd, layer_name=None)  # type: ignore[arg-type]
    assert exc.value.candidates == ["Frame-A", "Frame-B", "Frame-C"]
    msg = str(exc.value)
    assert "specify layer_name explicitly" in msg.lower()


def test_scenario_7b_multiple_design_matches_also_ambiguous() -> None:
    """Two layers ending in 'Design' → contains-Design also has >1 match → ambiguous."""
    candidates = [
        _so_info("Front Design", 0),
        _so_info("Back Design", 1),
        _so_info("Sleeves Design", 2),
    ]
    psd = object()
    with _patch_candidates(candidates), pytest.raises(AmbiguousLayerError):
        locate_smart_object(psd, layer_name=None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Scenario 8: Keine Smart Objects → NoSmartObjectError
# ---------------------------------------------------------------------------


def test_scenario_8_no_smart_objects_raises() -> None:
    psd = object()
    # Patch _collect to return empty AND _all_layer_names to a stable value.
    with _patch_candidates([]), patch(
        "aerocloud_worker.mockup.smart_object._all_layer_names",
        return_value=["Background", "Shadow"],
    ), pytest.raises(NoSmartObjectError) as exc:
        locate_smart_object(psd, layer_name=None)  # type: ignore[arg-type]
    assert "no smart-object" in str(exc.value).lower()

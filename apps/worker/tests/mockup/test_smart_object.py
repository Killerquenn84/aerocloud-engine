"""BDD scenarios 1-4: locate_smart_object behaviour.

Scenario 1 (default name "WORDCLOUD") is skipped because the real-world
poster-frame fixture uses "Replace me" — the spec explicitly allows skipping
when the fixture doesn't carry the default name. Scenario 2 covers the
custom-name path with the real fixture, which is the production-relevant case.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from psd_tools import PSDImage

from aerocloud_worker.mockup import (
    NoSmartObjectError,
    SmartObjectInfo,
    locate_smart_object,
)


def test_scenario_1_default_layer_name_wordcloud_is_skipped() -> None:
    """Default-name path requires a fixture with a layer literally named
    'WORDCLOUD'. None exists yet — guarded by skip per Phase-A spec."""
    pytest.skip("No fixture with default 'WORDCLOUD' layer yet — covered in Phase B.")


def test_scenario_2_custom_layer_name_replace_me(poster_frame_psd: Path) -> None:
    psd = PSDImage.open(poster_frame_psd)

    info = locate_smart_object(psd, layer_name="Replace me")

    assert isinstance(info, SmartObjectInfo)
    assert info.layer_name == "Replace me"
    assert info.transform_box == (
        532.0, 326.0, 1766.0, 326.0, 1766.0, 2050.0, 532.0, 2050.0,
    )
    assert info.bbox == (532, 326, 1766, 2050)
    assert info.layer_index >= 0


def test_scenario_3_missing_layer_raises_with_available_names(
    poster_frame_psd: Path,
) -> None:
    psd = PSDImage.open(poster_frame_psd)

    with pytest.raises(NoSmartObjectError) as exc:
        locate_smart_object(psd, layer_name="DOES_NOT_EXIST")

    assert "DOES_NOT_EXIST" in str(exc.value)
    assert exc.value.available_layers, "should list available layers"
    assert "Replace me" in exc.value.available_layers


def test_scenario_4_layer_exists_but_is_not_smart_object(
    poster_frame_psd: Path,
) -> None:
    """The fixture has top-level 'Shadow' which is a PixelLayer, not SO."""
    psd = PSDImage.open(poster_frame_psd)

    with pytest.raises(NoSmartObjectError) as exc:
        locate_smart_object(psd, layer_name="Place Bg image here")

    msg = str(exc.value).lower()
    assert "not a smart object" in msg

"""Sprint P26 — graceful-degradation tests (scenarios 8 + 9).

We never need a real PSD here: the engine's fallback logic is exercised by
monkeypatching the compositor module so the primary call raises and the
fallback returns a sentinel image. This keeps the test deterministic and
fast — no psd-tools, no Pillow re-warp.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from aerocloud_worker.mockup import compositor as compositor_module
from aerocloud_worker.mockup.engine import MockupEngine
from aerocloud_worker.mockup.exceptions import MockupRenderError


class _StubSmartLayer:
    name = "Replace me"


def _stub_psd():
    class _Psd:
        width = 100
        height = 100
        color_mode = type("M", (), {"name": "RGB"})()

    return _Psd()


@pytest.fixture
def patched_engine_internals(
    valid_design_path: Path,
    minimal_valid_psd_path: Path,
    tmp_path: Path,
):
    """Patch ALL of engine.py's heavy dependencies so we can drive the
    fallback path with simple stubs.
    """
    sentinel_overlay = Image.new("RGBA", (100, 100), (50, 50, 50, 255))
    sentinel_bg_only = Image.new("RGBA", (100, 100), (200, 200, 200, 255))

    # locate_smart_object returns an info object — we only need .layer_name.
    class _Info:
        layer_name = "Replace me"
        transform_box = None  # consumed only by warp_to_box (which we mock)

    with (
        patch("aerocloud_worker.mockup.engine.PSDImage") as mock_psd_cls,
        patch("aerocloud_worker.mockup.engine.locate_smart_object") as mock_locate,
        patch("aerocloud_worker.mockup.engine._iter_layers") as mock_iter,
        patch("aerocloud_worker.mockup.engine.warp_to_box") as mock_warp,
    ):
        mock_psd_cls.open.return_value = _stub_psd()
        mock_locate.return_value = _Info()

        layer = _StubSmartLayer()
        # SmartObjectLayer isinstance check — patch at the engine level so we
        # accept _StubSmartLayer.
        with patch(
            "aerocloud_worker.mockup.engine.SmartObjectLayer", _StubSmartLayer
        ):
            mock_iter.return_value = [layer]
            mock_warp.return_value = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
            yield sentinel_overlay, sentinel_bg_only


# ---------------------------------------------------------------------------
# Scenario 8 — overlay failure → background-only fallback
# ---------------------------------------------------------------------------


def test_scenario_8_overlay_failure_falls_back(
    patched_engine_internals,
    valid_design_path: Path,
    minimal_valid_psd_path: Path,
) -> None:
    sentinel_overlay, sentinel_bg_only = patched_engine_internals

    with (
        patch.object(
            compositor_module,
            "render_composite",
            side_effect=RuntimeError("frame layer corrupt"),
        ),
        patch.object(
            compositor_module,
            "render_background_only",
            return_value=sentinel_bg_only,
        ) as mock_bg,
    ):
        engine = MockupEngine(cache={}, fallback_on_overlay_failure=True)
        result = engine.render(minimal_valid_psd_path, valid_design_path)

    assert result is sentinel_bg_only
    mock_bg.assert_called_once()


def test_scenario_8_fallback_disabled_propagates(
    patched_engine_internals,
    valid_design_path: Path,
    minimal_valid_psd_path: Path,
) -> None:
    with patch.object(
        compositor_module,
        "render_composite",
        side_effect=RuntimeError("frame layer corrupt"),
    ):
        engine = MockupEngine(cache={}, fallback_on_overlay_failure=False)
        with pytest.raises(MockupRenderError):
            engine.render(minimal_valid_psd_path, valid_design_path)


def test_scenario_8_fallback_failure_raises_mockup_render_error(
    patched_engine_internals,
    valid_design_path: Path,
    minimal_valid_psd_path: Path,
) -> None:
    with (
        patch.object(
            compositor_module,
            "render_composite",
            side_effect=RuntimeError("primary fail"),
        ),
        patch.object(
            compositor_module,
            "render_background_only",
            side_effect=RuntimeError("fallback fail too"),
        ),
    ):
        engine = MockupEngine(cache={}, fallback_on_overlay_failure=True)
        with pytest.raises(MockupRenderError, match="fallback"):
            engine.render(minimal_valid_psd_path, valid_design_path)


# ---------------------------------------------------------------------------
# Scenario 9 — composite force fallback (already integrated in compositor.py
# via psd.composite(force=True); the engine guarantees that even if the
# primary path raises, render_background_only is attempted before failure).
# ---------------------------------------------------------------------------


def test_scenario_9_force_composite_is_used_inside_subset(
    patched_engine_internals,
    valid_design_path: Path,
    minimal_valid_psd_path: Path,
) -> None:
    """Read-the-source assertion: _composite_visible_subset uses force=True."""
    import inspect
    src = inspect.getsource(compositor_module._composite_visible_subset)
    assert "force=True" in src, (
        "_composite_visible_subset must call psd.composite(force=True) "
        "as the documented Phase A fallback"
    )

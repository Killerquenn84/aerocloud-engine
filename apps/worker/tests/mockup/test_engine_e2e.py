"""BDD scenarios 9-10: end-to-end MockupEngine + idempotency cache."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image
from psd_tools import PSDImage

from aerocloud_worker.mockup import MockupEngine


def test_scenario_9_full_replace_flow(
    poster_frame_psd: Path, design_png: Path, tmp_path: Path,
) -> None:
    engine = MockupEngine(cache={})

    result = engine.render(
        poster_frame_psd, design_png, layer_name="Replace me",
    )

    # Validate canvas dimensions match the source PSD.
    psd = PSDImage.open(poster_frame_psd)
    assert result.size == (psd.width, psd.height)
    assert result.mode == "RGBA"

    # Design must be visible at the transform-box position. The checkerboard
    # design has saturated red/blue cells, so the colour channel variance at
    # the centre of the smart-object area must be high (not a flat fill).
    arr = np.array(result)
    # smart-object bbox from spike output:
    x1, y1, x2, y2 = 532, 326, 1766, 2050
    centre_patch = arr[
        (y1 + y2) // 2 - 50 : (y1 + y2) // 2 + 50,
        (x1 + x2) // 2 - 50 : (x1 + x2) // 2 + 50,
        :3,
    ]
    # Either red or blue cells present → high std-dev across the patch.
    assert centre_patch.std() > 30, (
        f"checkerboard design should be visible in frame, std={centre_patch.std():.1f}"
    )

    # Save the output PNG to a tempfile so a human can inspect it on demand.
    out = tmp_path / "scenario9-output.png"
    result.save(out, format="PNG")
    assert out.stat().st_size > 0


def test_scenario_10_idempotency_cache_hit(
    poster_frame_psd: Path, design_png: Path,
) -> None:
    cache: dict = {}
    engine = MockupEngine(cache=cache)

    first = engine.render(poster_frame_psd, design_png, layer_name="Replace me")
    assert len(cache) == 1

    # Second call with identical inputs must NOT trigger render_composite again.
    import aerocloud_worker.mockup.engine as engine_mod

    with patch.object(
        engine_mod, "render_composite", side_effect=AssertionError("re-render!"),
    ):
        second = engine.render(
            poster_frame_psd, design_png, layer_name="Replace me",
        )

    assert second.size == first.size
    assert second.mode == first.mode
    # Cache still holds exactly one entry; same key was hit.
    assert len(cache) == 1

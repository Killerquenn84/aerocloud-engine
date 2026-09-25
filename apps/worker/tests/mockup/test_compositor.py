"""BDD scenarios 7-8: render_composite layer ordering."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from psd_tools import PSDImage
from psd_tools.api.layers import SmartObjectLayer

from aerocloud_worker.mockup import render_composite
from aerocloud_worker.mockup.smart_object import _iter_layers


def _find_smart(psd: PSDImage, name: str) -> SmartObjectLayer:
    for layer in _iter_layers(psd):
        if layer.name == name and isinstance(layer, SmartObjectLayer):
            return layer
    raise AssertionError(f"no SmartObject named {name!r} in PSD")


def test_scenario_7_background_warped_overlay_order(poster_frame_psd: Path) -> None:
    """The poster fixture has Background ('Place Bg image here'+'Shadow')
    BELOW the Smart Object container ('Artwork' group) and overlay groups
    ('Passe-partout', 'Frame', plus a duplicate 'Your design here' SO) ABOVE.
    Compositor must produce a canvas-sized RGBA with the warped design visible
    INSIDE the frame area and the frame overlay drawn ON TOP."""
    psd = PSDImage.open(poster_frame_psd)
    smart = _find_smart(psd, "Replace me")

    # Solid bright-green warped design exactly inside the Smart-Object bbox.
    canvas_size = (psd.width, psd.height)
    warped = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    x1, y1, x2, y2 = smart.bbox
    green = Image.new("RGBA", (x2 - x1, y2 - y1), (0, 255, 0, 255))
    warped.paste(green, (x1, y1))

    result = render_composite(psd, warped, smart)

    assert result.size == canvas_size
    assert result.mode == "RGBA"
    arr = np.array(result)

    # 1) Inside the Smart-Object area the bright green from the warped design
    #    must dominate (the Smart-Object group is dropped, green is painted,
    #    Passe-partout overlay is a translucent shape but its inner cut-out
    #    leaves the green visible at the centre).
    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2
    g = arr[cy, cx, 1]
    r = arr[cy, cx, 0]
    assert g > 150, f"centre should show warped green design, got RGB={arr[cy, cx, :3]}"
    assert g > r, "green channel must dominate red at the centre"

    # 2) Outside the Smart-Object bbox the background must be present
    #    (alpha=255 from the 'Place Bg image here' full-canvas pixel layer).
    assert arr[10, 10, 3] == 255, "background should fill the canvas edge"


def test_scenario_8_psd_without_overlays_only_background_plus_warped(
    poster_frame_psd: Path,
) -> None:
    """Simulate a no-overlay PSD by hiding every top-level layer above the
    Smart-Object container before compositing."""
    psd = PSDImage.open(poster_frame_psd)
    smart = _find_smart(psd, "Replace me")

    # Find which top-level layer holds the smart object.
    top = list(psd)
    container_idx = next(
        i for i, lay in enumerate(top)
        if any(child is smart for child in (lay, *_iter_layers(lay)))
    )

    # Hide everything above; restore after.
    saved = {id(lay): lay.visible for lay in top[container_idx + 1 :]}
    try:
        for lay in top[container_idx + 1 :]:
            lay.visible = False

        canvas_size = (psd.width, psd.height)
        warped = Image.new("RGBA", canvas_size, (0, 0, 255, 255))  # full blue plate

        result = render_composite(psd, warped, smart)
    finally:
        for lay in top[container_idx + 1 :]:
            lay.visible = saved[id(lay)]

    assert result.size == canvas_size
    arr = np.array(result)
    # Everywhere should be blue from the warped layer (overlays disabled).
    # Sample 4 corners far from any background-only zone.
    for x, y in [(100, 100), (canvas_size[0] - 100, 100),
                 (100, canvas_size[1] - 100),
                 (canvas_size[0] - 100, canvas_size[1] - 100)]:
        assert arr[y, x, 2] == 255, f"blue plate should win at ({x},{y})"
        assert arr[y, x, 0] == 0 and arr[y, x, 1] == 0

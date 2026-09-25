"""BDD scenarios 5-6: warp_to_box."""
from __future__ import annotations

import numpy as np
from PIL import Image

from aerocloud_worker.mockup import warp_to_box


def _make_design(w: int, h: int) -> Image.Image:
    """Solid red design with a 1-px transparent border so alpha exists."""
    img = Image.new("RGBA", (w, h), (255, 0, 0, 255))
    return img


def test_scenario_5_four_point_warp_places_corners_exactly() -> None:
    design = _make_design(600, 600)
    transform_box = (200.0, 100.0, 800.0, 150.0, 850.0, 700.0, 150.0, 650.0)
    canvas = (1000, 800)

    result = warp_to_box(design, transform_box, canvas)

    assert result.size == canvas
    assert result.mode == "RGBA"
    arr = np.array(result)

    # Each transform-box corner should land on an opaque pixel from the design.
    # Inset by 3 px to avoid sampling the anti-aliased perimeter.
    corners = [
        (int(transform_box[0]) + 3, int(transform_box[1]) + 3),
        (int(transform_box[2]) - 4, int(transform_box[3]) + 3),
        (int(transform_box[4]) - 4, int(transform_box[5]) - 4),
        (int(transform_box[6]) + 3, int(transform_box[7]) - 4),
    ]
    for x, y in corners:
        assert arr[y, x, 3] > 200, f"corner ({x},{y}) should be opaque (red design)"
        assert arr[y, x, 0] > 200 and arr[y, x, 1] < 60, "color is the red design"

    # A pixel far outside the quad must be fully transparent.
    assert arr[10, 10, 3] == 0
    assert arr[790, 990, 3] == 0


def test_scenario_6_aspect_mismatch_stretch_mode_fills_quad() -> None:
    """16:9 design stretched onto a square box — no cropping, full alpha fill."""
    design = _make_design(1600, 900)  # 16:9
    transform_box = (100.0, 100.0, 500.0, 100.0, 500.0, 500.0, 100.0, 500.0)
    canvas = (700, 700)

    result = warp_to_box(design, transform_box, canvas, fit_mode="stretch")
    arr = np.array(result)

    # Interior of the square quad should be opaque red.
    cx, cy = 300, 300
    assert arr[cy, cx, 3] == 255
    assert arr[cy, cx, 0] > 240 and arr[cy, cx, 1] < 30

    # All four interior box-corners are filled (no cropping artifacts).
    for x, y in [(110, 110), (490, 110), (490, 490), (110, 490)]:
        assert arr[y, x, 3] > 200

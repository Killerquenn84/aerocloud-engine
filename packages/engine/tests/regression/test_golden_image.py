"""Golden-image SSIM regression tests (PROD-21, D-27).

Compares fresh rendered output against committed PNG fixtures using SSIM.
SSIM threshold >= 0.95 per D-27.

Fixtures: circle, square, star, crescent (generated with seed=42).

Determinism guarantee: render_fixture(name, seed=42) must produce byte-for-byte
identical output on every call in the same environment. Tests skip gracefully
when golden images have not yet been generated.

Implementation note:
    PNG encoding is done inline (PIL.Image) rather than via
    ``aerocloud.export.export_png`` to avoid triggering
    ``aerocloud/export/__init__.py``, which transitively imports
    ``boolean_union`` (shapely) and ``bezier`` (cv2) — neither is required
    for golden-image testing. The encoding logic is identical to
    ``aerocloud.export.png_export.export_png`` (clamp → scale → PIL → PNG).

References:
    - PROD-21: Golden-image regression tests — Phase 12 exit gate
    - D-27: SSIM threshold locked at 0.95
    - packages/engine/scripts/generate_golden_images.py — one-shot generation
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image
from skimage.metrics import structural_similarity as ssim

from aerocloud.renderer._renderer import DifferentiableRenderer
from aerocloud.utils.determinism import set_seed

GOLDEN_DIR = Path(__file__).parent / "golden"
SSIM_THRESHOLD = 0.95  # D-27 locked floor
FIXTURES = ["circle", "square", "star", "crescent"]

# Canvas size used for generation AND testing — must be identical.
CANVAS_H = 128
CANVAS_W = 128

# Number of synthetic word sprites used in render_fixture.
# Each sprite is a small white rectangle on a black background.
N_WORDS = 8
SPRITE_H = 12
SPRITE_W = 32


def _make_synthetic_sprites(n: int, h: int = SPRITE_H, w: int = SPRITE_W) -> list[torch.Tensor]:
    """Create N synthetic word sprites (white rectangles, (1,1,h,w) float32)."""
    sprites = []
    for _ in range(n):
        s = torch.ones(1, 1, h, w, dtype=torch.float32)
        sprites.append(s)
    return sprites


def _fixture_params(fixture_name: str) -> torch.Tensor:
    """Return deterministic (N, 4) params [y, x, scale, rotation] for a fixture.

    Each fixture uses a different spatial layout so SSIM tests cover varied
    visual patterns. Params are designed to keep all words inside CANVAS_H x CANVAS_W.
    """
    layouts: dict[str, list[tuple[float, float, float, float]]] = {
        "circle": [
            (32.0, 64.0, 1.2, 0.0),
            (64.0, 32.0, 1.0, 0.1),
            (64.0, 96.0, 1.0, -0.1),
            (96.0, 64.0, 1.2, 0.0),
            (48.0, 48.0, 0.9, 0.2),
            (48.0, 80.0, 0.9, -0.2),
            (80.0, 48.0, 1.1, 0.15),
            (80.0, 80.0, 1.1, -0.15),
        ],
        "square": [
            (24.0, 24.0, 1.0, 0.0),
            (24.0, 64.0, 1.0, 0.0),
            (24.0, 104.0, 1.0, 0.0),
            (64.0, 24.0, 1.0, 0.0),
            (64.0, 64.0, 1.2, 0.0),
            (64.0, 104.0, 1.0, 0.0),
            (104.0, 24.0, 1.0, 0.0),
            (104.0, 64.0, 1.0, 0.0),
        ],
        "star": [
            (20.0, 64.0, 1.3, 0.0),
            (64.0, 20.0, 1.1, 0.3),
            (64.0, 108.0, 1.1, -0.3),
            (108.0, 64.0, 1.3, 0.0),
            (40.0, 40.0, 0.8, 0.785),
            (40.0, 88.0, 0.8, -0.785),
            (88.0, 40.0, 0.8, 0.785),
            (88.0, 88.0, 0.8, -0.785),
        ],
        "crescent": [
            (30.0, 80.0, 1.0, 0.3),
            (50.0, 90.0, 1.1, 0.1),
            (70.0, 85.0, 1.0, -0.1),
            (90.0, 75.0, 0.9, -0.3),
            (40.0, 70.0, 0.8, 0.4),
            (60.0, 95.0, 0.9, 0.0),
            (80.0, 90.0, 1.0, -0.2),
            (100.0, 70.0, 0.8, -0.4),
        ],
    }
    rows = layouts[fixture_name]
    return torch.tensor(rows, dtype=torch.float32)


def _tensor_to_grayscale_array(density_2d: torch.Tensor) -> np.ndarray:
    """Convert a (H, W) float32 tensor in [0,1] to uint8 numpy array.

    Mirrors the logic of aerocloud.export.png_export.export_png(mode='L')
    without importing the full export package (which pulls in shapely/cv2).
    """
    t = density_2d.clamp(0.0, 1.0)
    if t.ndim == 3 and t.shape[0] == 1:
        t = t.squeeze(0)
    arr: np.ndarray = (t.cpu().float().numpy() * 255.0).astype(np.uint8)
    return arr


def render_fixture(fixture_name: str, seed: int = 42) -> np.ndarray:
    """Render a named fixture to a grayscale uint8 numpy array.

    Uses a simplified pipeline (synthetic word sprites + DifferentiableRenderer)
    to validate visual output determinism without requiring the full NLP/SDF
    pipeline to be integrated end-to-end.

    The SAME code path runs in generation (generate_golden_images.py) and
    testing (test_golden_image.py), which is the essential guarantee.

    Args:
        fixture_name: One of "circle", "square", "star", "crescent".
        seed: Integer seed for reproducibility. Default 42.

    Returns:
        uint8 numpy array of shape (CANVAS_H, CANVAS_W) in range [0, 255].
    """
    set_seed(seed)
    device = torch.device("cpu")  # CI-safe: no CUDA required (CPU fallback per PROJECT.md)

    params = _fixture_params(fixture_name)
    sprites = _make_synthetic_sprites(N_WORDS)

    renderer = DifferentiableRenderer(params, sprites, device)

    with torch.no_grad():
        density = renderer.forward(CANVAS_H, CANVAS_W, mode="alpha_over")
        # density: (1, 1, H, W) in [0, 1]
        density_2d = density.squeeze()  # (H, W)

    return _tensor_to_grayscale_array(density_2d)


@pytest.mark.parametrize("fixture_name", FIXTURES)
def test_golden_image_ssim(fixture_name: str) -> None:
    """Assert SSIM >= 0.95 between fresh render and committed golden PNG (D-27).

    Skips gracefully if the golden image has not yet been generated.
    Run ``python packages/engine/scripts/generate_golden_images.py`` first.

    Args:
        fixture_name: Name of the fixture to test.
    """
    golden_path = GOLDEN_DIR / f"{fixture_name}.png"
    if not golden_path.exists():
        pytest.skip(
            f"Golden image not found: {golden_path}. "
            "Run generate_golden_images.py first."
        )

    golden = np.array(Image.open(golden_path).convert("L"))
    rendered = render_fixture(fixture_name, seed=42)

    assert golden.shape == rendered.shape, (
        f"{fixture_name}: shape mismatch — golden {golden.shape} vs rendered {rendered.shape}"
    )

    score = ssim(golden, rendered, data_range=255)
    assert score >= SSIM_THRESHOLD, (
        f"{fixture_name}: SSIM {score:.4f} < threshold {SSIM_THRESHOLD}. "
        f"Visual drift detected — re-run generate_golden_images.py if renderer changed intentionally."
    )

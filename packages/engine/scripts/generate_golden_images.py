"""One-shot golden image generation script for SSIM regression tests (PROD-21).

Generates PNG fixtures for the four test shapes (circle, square, star, crescent)
using seed=42 for deterministic output. Commit the generated PNGs; the regression
test in tests/regression/test_golden_image.py asserts SSIM >= 0.95 against them.

Usage:
    cd /var/www/wordcloud-app-v2/server/aerocloud-engine
    uv run python packages/engine/scripts/generate_golden_images.py

Regeneration policy:
    Re-run ONLY when the renderer's forward pass changes intentionally (e.g. new
    compositing mode, sprite pipeline change). After regenerating, verify that
    ``uv run pytest packages/engine/tests/regression/test_golden_image.py -v``
    passes with SSIM = 1.0 (byte-identical to the freshly committed goldens).

Design:
    Uses the same render_fixture() logic as test_golden_image.py — same params,
    same sprites, same seed. Importing from the test module is intentionally
    avoided to keep the script self-contained (no pytest dependency at runtime).
    Both files share the same algorithm so any drift is caught by the SSIM test.

References:
    - PROD-21: Golden-image regression tests
    - D-27: SSIM threshold 0.95
    - T-12-07-01: Golden PNGs committed to git; integrity via git hash
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image

# Adjust sys.path so this script can run from the repo root without install.
_ENGINE_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_ENGINE_SRC) not in sys.path:
    sys.path.insert(0, str(_ENGINE_SRC))

from aerocloud.renderer._renderer import DifferentiableRenderer  # noqa: E402
from aerocloud.utils.determinism import set_seed  # noqa: E402

# ---------------------------------------------------------------------------
# Constants — MUST stay in sync with test_golden_image.py
# ---------------------------------------------------------------------------
GOLDEN_DIR = Path(__file__).resolve().parents[1] / "tests" / "regression" / "golden"
FIXTURES = ["circle", "square", "star", "crescent"]
CANVAS_H = 128
CANVAS_W = 128
N_WORDS = 8
SPRITE_H = 12
SPRITE_W = 32
SEED = 42


# ---------------------------------------------------------------------------
# Helpers (duplicated from test_golden_image.py intentionally — keeps script
# runnable without pytest import and makes the generation script self-contained)
# ---------------------------------------------------------------------------

def _make_synthetic_sprites(n: int, h: int = SPRITE_H, w: int = SPRITE_W) -> list[torch.Tensor]:
    """Create N synthetic word sprites (white rectangles, (1,1,h,w) float32)."""
    return [torch.ones(1, 1, h, w, dtype=torch.float32) for _ in range(n)]


def _fixture_params(fixture_name: str) -> torch.Tensor:
    """Return deterministic (N, 4) params [y, x, scale, rotation] for a fixture."""
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
    return torch.tensor(layouts[fixture_name], dtype=torch.float32)


def _tensor_to_grayscale_array(density_2d: torch.Tensor) -> np.ndarray:
    """Convert a (H, W) float32 tensor in [0,1] to uint8 numpy array."""
    t = density_2d.clamp(0.0, 1.0)
    if t.ndim == 3 and t.shape[0] == 1:
        t = t.squeeze(0)
    arr: np.ndarray = (t.cpu().float().numpy() * 255.0).astype(np.uint8)
    return arr


def render_fixture(fixture_name: str, seed: int = SEED) -> np.ndarray:
    """Render a named fixture to a grayscale uint8 numpy array.

    Args:
        fixture_name: One of "circle", "square", "star", "crescent".
        seed: Integer seed. Default SEED (42).

    Returns:
        uint8 numpy array of shape (CANVAS_H, CANVAS_W).
    """
    set_seed(seed)
    device = torch.device("cpu")

    params = _fixture_params(fixture_name)
    sprites = _make_synthetic_sprites(N_WORDS)

    renderer = DifferentiableRenderer(params, sprites, device)

    with torch.no_grad():
        density = renderer.forward(CANVAS_H, CANVAS_W, mode="alpha_over")
        density_2d = density.squeeze()  # (H, W)

    return _tensor_to_grayscale_array(density_2d)


def generate(out_dir: Path = GOLDEN_DIR) -> None:
    """Generate all golden PNG fixtures and save to out_dir.

    Args:
        out_dir: Directory where PNGs are written. Created if absent.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    for fixture_name in FIXTURES:
        arr = render_fixture(fixture_name, seed=SEED)
        img = Image.fromarray(arr, mode="L")
        path = out_dir / f"{fixture_name}.png"
        img.save(path, format="PNG")
        print(f"wrote {path}  shape={arr.shape}  min={arr.min()}  max={arr.max()}")

    print(f"\nDone: {len(FIXTURES)} golden images written to {out_dir}")
    print("Commit these files and run the SSIM regression test to verify.")


if __name__ == "__main__":
    generate()

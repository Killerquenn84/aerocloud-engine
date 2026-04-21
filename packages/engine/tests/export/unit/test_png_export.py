"""Unit tests for PNG export module (PROD-05).

BDD Scenarios:
    Given a (C, H, W) float32 tensor in [0, 1],
    When export_png is called,
    Then valid PNG bytes are returned (PNG magic header).

    Given a tensor exported to PNG,
    When decoded back via PIL,
    Then pixel values match the original within 1/255 tolerance.
"""

import io

import numpy as np
import pytest
import torch
from PIL import Image

from aerocloud.export.png_export import export_png

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class TestExportPng:
    """Tests for export_png() — PROD-05."""

    def test_rgb_tensor_returns_png_bytes(self) -> None:
        """RGB (3, 64, 64) float32 tensor must produce valid PNG bytes."""
        tensor = torch.zeros(3, 64, 64, dtype=torch.float32)
        result = export_png(tensor, mode="RGB")
        assert isinstance(result, bytes)
        assert result[:8] == _PNG_MAGIC

    def test_grayscale_tensor_returns_png_bytes(self) -> None:
        """Grayscale (1, 64, 64) float32 tensor must produce valid PNG bytes."""
        tensor = torch.ones(1, 64, 64, dtype=torch.float32)
        result = export_png(tensor, mode="L")
        assert isinstance(result, bytes)
        assert result[:8] == _PNG_MAGIC

    def test_rgb_roundtrip_within_tolerance(self) -> None:
        """Roundtrip tensor -> PNG -> PIL -> numpy must match within 1/255."""
        rng = torch.Generator()
        rng.manual_seed(42)
        tensor = torch.rand(3, 32, 32, generator=rng, dtype=torch.float32)
        png_bytes = export_png(tensor, mode="RGB")

        img = Image.open(io.BytesIO(png_bytes))
        recovered = np.array(img).astype(np.float32) / 255.0  # (H, W, C)
        # Tensor is (C, H, W) — transpose to (H, W, C) for comparison
        original = tensor.permute(1, 2, 0).numpy()  # (H, W, C)
        np.testing.assert_allclose(recovered, original, atol=1.0 / 255.0)

    def test_grayscale_roundtrip_within_tolerance(self) -> None:
        """Grayscale roundtrip must also match within 1/255."""
        rng = torch.Generator()
        rng.manual_seed(7)
        tensor = torch.rand(1, 32, 32, generator=rng, dtype=torch.float32)
        png_bytes = export_png(tensor, mode="L")

        img = Image.open(io.BytesIO(png_bytes))
        recovered = np.array(img).astype(np.float32) / 255.0  # (H, W)
        original = tensor.squeeze(0).numpy()  # (H, W)
        np.testing.assert_allclose(recovered, original, atol=1.0 / 255.0)

    def test_clamping_above_one(self) -> None:
        """Values above 1.0 must be clamped to 1.0 (255) without error."""
        tensor = torch.full((3, 8, 8), fill_value=2.0, dtype=torch.float32)
        result = export_png(tensor, mode="RGB")
        img = Image.open(io.BytesIO(result))
        arr = np.array(img)
        assert np.all(arr == 255)

    def test_clamping_below_zero(self) -> None:
        """Values below 0.0 must be clamped to 0.0 (0) without error."""
        tensor = torch.full((3, 8, 8), fill_value=-1.0, dtype=torch.float32)
        result = export_png(tensor, mode="RGB")
        img = Image.open(io.BytesIO(result))
        arr = np.array(img)
        assert np.all(arr == 0)

    def test_default_mode_is_rgb(self) -> None:
        """Default mode is RGB — (3, H, W) tensor without explicit mode works."""
        tensor = torch.zeros(3, 16, 16, dtype=torch.float32)
        result = export_png(tensor)
        assert result[:8] == _PNG_MAGIC

    def test_invalid_mode_raises(self) -> None:
        """Unsupported mode must raise ValueError."""
        tensor = torch.zeros(3, 8, 8, dtype=torch.float32)
        with pytest.raises(ValueError, match="mode"):
            export_png(tensor, mode="CMYK")

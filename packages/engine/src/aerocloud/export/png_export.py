"""PNG export module for AeroCloud word cloud rendering (PROD-05).

Converts PyTorch float32 tensors to PNG-encoded bytes for downstream consumers
(SVG/PDF export, API responses, Celery result storage).

Supports:
    - RGB mode: (3, H, W) or (H, W, 3) float32 tensors in [0.0, 1.0]
    - Grayscale mode: (1, H, W) or (H, W) float32 tensors in [0.0, 1.0]

References:
    - PROD-05: PNG export pipeline — Blueprint Teil X
    - T-12-01-02: Tensors are internal pipeline output, not user-supplied (accept)

Design decisions:
    - Clamp input to [0, 1] before scaling — prevents overflow silently
    - Use PIL.Image.fromarray() for reliable byte encoding
    - Return bytes (not file path) — callers control persistence
"""

from __future__ import annotations

import io

import numpy as np
import torch
from PIL import Image

_SUPPORTED_MODES = frozenset({"RGB", "L"})


def export_png(tensor: torch.Tensor, mode: str = "RGB") -> bytes:
    """Export a float32 PyTorch tensor as PNG-encoded bytes.

    Args:
        tensor: Float32 tensor in [0.0, 1.0]. Accepted shapes:
            - RGB mode: (3, H, W) or (H, W, 3)
            - Grayscale mode: (1, H, W) or (H, W)
        mode: PIL image mode. Supported: "RGB" (default) or "L" (grayscale).

    Returns:
        PNG-encoded bytes. Starts with the 8-byte PNG magic header.

    Raises:
        ValueError: If mode is not "RGB" or "L".
    """
    if mode not in _SUPPORTED_MODES:
        raise ValueError(
            f"Unsupported mode {mode!r}. Supported modes: {sorted(_SUPPORTED_MODES)}"
        )

    # Clamp to [0, 1] silently (T-12-01-02: internal input, no validation needed)
    t = tensor.clamp(0.0, 1.0)

    if mode == "RGB":
        # Handle (3, H, W) → (H, W, 3)
        if t.ndim == 3 and t.shape[0] == 3:
            t = t.permute(1, 2, 0)
        # Now shape is (H, W, 3)
        arr: np.ndarray = (t.cpu().float().numpy() * 255.0).astype(np.uint8)
        img = Image.fromarray(arr, mode="RGB")
    else:
        # Grayscale: handle (1, H, W) → (H, W) or already (H, W)
        if t.ndim == 3 and t.shape[0] == 1:
            t = t.squeeze(0)
        arr = (t.cpu().float().numpy() * 255.0).astype(np.uint8)
        img = Image.fromarray(arr, mode="L")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

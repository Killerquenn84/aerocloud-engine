"""DifferentiableRenderer: 2D sprite compositing via grid_sample (Phase 5).

Pure PyTorch implementation per D-01. No nvdiffrast, no PyTorch3D.
Uses affine_grid + grid_sample with bilinear interpolation (D-02).
Alpha-over compositing: density = 1 - prod(1 - alpha_i) (D-04).
"""

from __future__ import annotations

import math

import torch
import torch.nn as nn
import torch.nn.functional as F


class DifferentiableRenderer(nn.Module):
    """Differentiable 2D sprite compositor (D-14).

    Composites N pre-rasterized glyph sprites onto a canvas with learnable
    position, scale, and rotation parameters. Output is a density tensor
    in [0, 1] that Phase 6 loss functions consume.

    Parameters are stored as a packed (N, 4) nn.Parameter with columns
    [y, x, scale, rotation] per D-05.

    Args:
        params_n4: (N, 4) float32 tensor with [y, x, scale, rotation] per word.
        sprites: List of N tensors, each (1, 1, H_i, W_i) float32 in [0, 1].
        device: Target torch device (cpu or cuda).
    """

    def __init__(
        self,
        params_n4: torch.Tensor,
        sprites: list[torch.Tensor],
        device: torch.device,
    ) -> None:
        super().__init__()
        if params_n4.ndim != 2 or params_n4.shape[1] != 4:
            raise ValueError(
                f"params_n4 must be (N, 4), got {params_n4.shape}"
            )
        if len(sprites) != params_n4.shape[0]:
            raise ValueError(
                f"Expected {params_n4.shape[0]} sprites, got {len(sprites)}"
            )
        self.params = nn.Parameter(params_n4.to(device, dtype=torch.float32))
        # Sprites are data, not learned -- store as plain tensors (D-10, D-11)
        self._sprites: list[torch.Tensor] = [
            s.to(device, dtype=torch.float32) for s in sprites
        ]
        self._device = device

    def forward(self, canvas_h: int, canvas_w: int) -> torch.Tensor:
        """Render all sprites onto a canvas.

        Returns (1, 1, canvas_h, canvas_w) density tensor in [0, 1] (D-15, D-17).
        """
        density = torch.zeros(
            1, 1, canvas_h, canvas_w,
            device=self._device, dtype=torch.float32,
        )
        for i, sprite in enumerate(self._sprites):
            y_i, x_i, s_i, theta_i = self.params[i]

            # Clamp rotation to [-pi, pi] (D-09)
            theta_i = torch.remainder(theta_i + math.pi, 2 * math.pi) - math.pi

            # Normalize pixel coords to NDC [-1, 1] for affine_grid (D-07)
            x_n = (x_i / (canvas_w / 2.0)) - 1.0
            y_n = (y_i / (canvas_h / 2.0)) - 1.0

            cos_t = torch.cos(theta_i)
            sin_t = torch.sin(theta_i)

            # 2x3 affine matrix: scale + rotate + translate (D-16)
            # Row 0 controls x-sampling, Row 1 controls y-sampling
            # in affine_grid's convention
            theta_mat = torch.stack([
                s_i * cos_t, -s_i * sin_t, x_n,
                s_i * sin_t,  s_i * cos_t, y_n,
            ]).reshape(1, 2, 3)

            # affine_grid + grid_sample (D-02)
            # align_corners=False for pixel-edge semantics (Pitfall 2)
            grid = F.affine_grid(
                theta_mat, [1, 1, canvas_h, canvas_w], align_corners=False,
            )
            warped = F.grid_sample(
                sprite, grid,
                mode="bilinear", padding_mode="zeros", align_corners=False,
            )

            # Alpha-over compositing (D-04):
            # density = 1 - prod(1 - alpha_i)
            density = 1.0 - (1.0 - density) * (1.0 - warped)

        return density

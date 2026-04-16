"""DifferentiableRenderer: 2D sprite compositing via grid_sample (Phase 5).

Pure PyTorch implementation per D-01. No nvdiffrast, no PyTorch3D.
Uses affine_grid + grid_sample with bilinear interpolation (D-02).
Alpha-over compositing: density = 1 - prod(1 - alpha_i) (D-04).

Phase 7 / D-20: forward() gains a ``mode`` parameter so both alpha-over
and additive density are produced in a **single** sprite loop (fixes F-3).
"""

from __future__ import annotations

import math

import torch
import torch.nn as nn  # noqa: PLR0402
import torch.nn.functional as F  # noqa: N812


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

    def forward(
        self,
        canvas_h: int,
        canvas_w: int,
        mode: str = "alpha_over",
    ) -> torch.Tensor | tuple[torch.Tensor, torch.Tensor]:
        """Render all sprites onto a canvas (D-15, D-17, D-20).

        Args:
            canvas_h: Canvas height in pixels.
            canvas_w: Canvas width in pixels.
            mode: Compositing mode.
                - ``'alpha_over'`` (default): returns a single
                  ``(1, 1, canvas_h, canvas_w)`` density tensor in [0, 1].
                  This is the backward-compatible mode used by all Phase 5
                  callers.
                - ``'both'``: returns ``(density, additive_density)`` tuple,
                  both shaped ``(1, 1, canvas_h, canvas_w)``.  Both outputs
                  are computed in a **single** sprite loop — no double forward
                  pass (D-20, fixes F-3).  ``additive_density`` is the SUM
                  compositing output which may exceed 1.0 at overlap pixels
                  (needed by L_overlap / D-03).

        Returns:
            Single tensor when mode='alpha_over'; 2-tuple when mode='both'.

        Raises:
            ValueError: If ``mode`` is not ``'alpha_over'`` or ``'both'``.
        """
        if mode not in ("alpha_over", "both"):
            raise ValueError(
                f"Unknown mode {mode!r}; expected 'alpha_over' or 'both'"
            )

        density = torch.zeros(
            1, 1, canvas_h, canvas_w,
            device=self._device, dtype=torch.float32,
        )
        # Only allocate additive tensor when requested (avoids memory overhead)
        additive: torch.Tensor | None = (
            torch.zeros_like(density) if mode == "both" else None
        )

        for i, sprite in enumerate(self._sprites):
            y_i, x_i, s_i, theta_i = self.params[i]

            # Clamp rotation to [-pi, pi] (D-09)
            theta_i = torch.remainder(theta_i + math.pi, 2 * math.pi) - math.pi

            # Soft-clamp scale: gradient-friendly floor via softplus (Codex post-fix review)
            # softplus(s_i - 0.01) + 0.01 ensures s_i >= 0.01 with non-zero gradient
            s_i = torch.nn.functional.softplus(s_i - 0.01) + 0.01

            # Normalize pixel coords to NDC [-1, 1] for affine_grid (D-07)
            # align_corners=False: pixel center p maps to ((2p+1)/size) - 1 (Codex Fix 2)
            x_n = ((2.0 * x_i + 1.0) / canvas_w) - 1.0
            y_n = ((2.0 * y_i + 1.0) / canvas_h) - 1.0

            cos_t = torch.cos(theta_i)
            sin_t = torch.sin(theta_i)

            # Inverse scale for target-to-source mapping (Gemini + Codex review)
            inv_s = 1.0 / s_i

            # 2x3 affine matrix: TARGET-TO-SOURCE (D-16)
            # affine_grid maps output pixels to input (sprite) coordinates.
            # A^{-1} = (1/s) * R(-theta), translation b = -A^{-1} * T
            # Row 0 controls x-sampling, Row 1 controls y-sampling
            a11 = inv_s * cos_t
            a12 = inv_s * sin_t
            a21 = -inv_s * sin_t
            a22 = inv_s * cos_t
            tx = -(a11 * x_n + a12 * y_n)
            ty = -(a21 * x_n + a22 * y_n)

            theta_mat = torch.stack([
                a11, a12, tx,
                a21, a22, ty,
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

            # Alpha-over compositing (D-04): density = 1 - prod(1 - alpha_i)
            density = 1.0 - (1.0 - density) * (1.0 - warped)

            # Additive compositing branch (D-20): only computed when mode='both'.
            # SUM allows values to exceed 1.0 at overlap pixels (needed by L_overlap).
            if additive is not None:
                additive = additive + warped

        if mode == "both":
            # additive is guaranteed non-None here (allocated above when mode='both')
            assert additive is not None  # for mypy
            return density, additive
        return density

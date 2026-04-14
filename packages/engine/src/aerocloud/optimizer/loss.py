"""Loss functions for the inner-loop optimizer (Phase 6).

Implements the 4-part composite loss per D-01..D-06 of the AeroCloud Blueprint:

    L_total = alpha * L_wmse + beta * L_overlap + gamma * L_fidelity + lambda_ * L_temporal

Also provides compute_additive_density, the SUM-based compositing helper
needed by L_overlap that allows per-pixel density to exceed 1.0.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import torch
import torch.nn.functional as F  # noqa: N812

if TYPE_CHECKING:
    from aerocloud.renderer._renderer import DifferentiableRenderer

from aerocloud.models.optimizer import LossWeights


def compute_l_wmse(
    density: torch.Tensor,
    sdf: torch.Tensor,
) -> torch.Tensor:
    """Weighted Mean Squared Error loss (D-01).

    Penalizes uncovered interior pixels weighted by their SDF depth.
    Exterior pixels (sdf < 0) contribute zero via the clamp.

    Formula::

        L_wmse = mean((clamp(sdf, min=0) * (1 - density))^2)

    Args:
        density: (1, 1, H, W) float32 renderer output in [0, 1].
        sdf: (1, 1, H, W) float32 signed distance field.
            Positive inside the shape, negative outside.

    Returns:
        Scalar tensor.
    """
    sdf_positive = sdf.clamp(min=0.0)
    return ((sdf_positive * (1.0 - density)) ** 2).mean()


def compute_l_overlap(
    additive_density: torch.Tensor,
) -> torch.Tensor:
    """Primitive Overlap loss (D-03).

    Penalizes pixels where sprites overlap (additive density > 1.0).
    Uses squared ReLU so the penalty is smooth and differentiable.

    Formula::

        L_overlap = mean(ReLU(density - 1.0)^2)

    Args:
        additive_density: (1, 1, H, W) float32 SUM-composited density
            (may exceed 1.0 where sprites overlap).

    Returns:
        Scalar tensor.
    """
    return (F.relu(additive_density - 1.0) ** 2).mean()


def compute_l_fidelity(
    s_ref: torch.Tensor,
    params: torch.Tensor,
) -> torch.Tensor:
    """Data Fidelity loss (D-04).

    Prevents artificial scale inflation by penalising deviation between
    the reference scale distribution and the current scale parameters.
    Uses cosine similarity so only the *shape* of the distribution matters,
    not the absolute magnitudes.

    Formula::

        L_fidelity = 1 - cosine_similarity(s_ref, params[:, 2])

    Args:
        s_ref: (N,) float32 reference scale vector (from TF-IDF weights).
        params: (N, 4) float32 parameter tensor [y, x, scale, rotation].

    Returns:
        Scalar tensor in approximately [0, 2].
    """
    s_current = params[:, 2]
    return 1.0 - F.cosine_similarity(
        s_ref.unsqueeze(0), s_current.unsqueeze(0)
    ).squeeze()


def compute_l_temporal(
    params_current: torch.Tensor,
    params_initial: torch.Tensor,
) -> torch.Tensor:
    """Temporal Coherence loss (D-05).

    Penalises position drift between the current and initial parameters.
    Only (y, x) columns contribute; scale and rotation changes are ignored.
    Default weight lambda_=0.0 effectively disables this term for static
    word clouds.

    Formula::

        L_temporal = mean((params_current[:, :2] - params_initial[:, :2])^2)

    Args:
        params_current: (N, 4) float32 current parameter tensor.
        params_initial: (N, 4) float32 initial (reference) parameter tensor.

    Returns:
        Scalar tensor.
    """
    return ((params_current[:, :2] - params_initial[:, :2]) ** 2).mean()


def compute_total_loss(
    weights: LossWeights,
    l_wmse: torch.Tensor,
    l_overlap: torch.Tensor,
    l_fidelity: torch.Tensor,
    l_temporal: torch.Tensor,
) -> torch.Tensor:
    """Composite loss combining all four terms (D-06).

    Formula::

        L_total = alpha * L_wmse + beta * L_overlap
                + gamma * L_fidelity + lambda_ * L_temporal

    Args:
        weights: LossWeights instance with the four weighting scalars.
        l_wmse: Boundary-fitness loss scalar.
        l_overlap: Primitive-overlap loss scalar.
        l_fidelity: Data-fidelity loss scalar.
        l_temporal: Temporal-coherence loss scalar.

    Returns:
        Scalar tensor.
    """
    return (
        weights.alpha * l_wmse
        + weights.beta * l_overlap
        + weights.gamma * l_fidelity
        + weights.lambda_ * l_temporal
    )


def compute_additive_density(
    renderer: DifferentiableRenderer,
    canvas_h: int,
    canvas_w: int,
) -> torch.Tensor:
    """SUM-based sprite compositing for overlap detection (D-03 helper).

    Replicates the renderer's per-sprite warp logic (affine_grid +
    grid_sample with the same rotation clamping and scale softplus) but
    **sums** warped sprite contributions instead of using alpha-over.
    This means the output can exceed 1.0 wherever sprites overlap,
    which is exactly what L_overlap needs to detect.

    Accesses renderer private state:
        - renderer._sprites  (list of (1, 1, H_i, W_i) tensors)
        - renderer.params    (nn.Parameter, shape (N, 4))
        - renderer._device   (torch.device)

    Args:
        renderer: A DifferentiableRenderer instance (must have at least
            one sprite).
        canvas_h: Target canvas height in pixels.
        canvas_w: Target canvas width in pixels.

    Returns:
        (1, 1, canvas_h, canvas_w) float32 tensor. Values may exceed 1.0
        at pixels covered by more than one sprite.
    """
    additive = torch.zeros(
        1, 1, canvas_h, canvas_w,
        device=renderer._device,
        dtype=torch.float32,
    )

    for i, sprite in enumerate(renderer._sprites):
        y_i, x_i, s_i, theta_i = renderer.params[i]

        # Same rotation clamping as DifferentiableRenderer.forward() (D-09)
        theta_i = torch.remainder(theta_i + math.pi, 2 * math.pi) - math.pi

        # Same scale soft-clamp: softplus(s - 0.01) + 0.01 (Codex post-fix)
        s_i = torch.nn.functional.softplus(s_i - 0.01) + 0.01

        # NDC normalisation (align_corners=False convention, Codex Fix 2)
        x_n = ((2.0 * x_i + 1.0) / canvas_w) - 1.0
        y_n = ((2.0 * y_i + 1.0) / canvas_h) - 1.0

        cos_t = torch.cos(theta_i)
        sin_t = torch.sin(theta_i)
        inv_s = 1.0 / s_i

        # Target-to-source affine matrix (same as renderer forward, D-16)
        a11 = inv_s * cos_t
        a12 = inv_s * sin_t
        a21 = -inv_s * sin_t
        a22 = inv_s * cos_t
        tx = -(a11 * x_n + a12 * y_n)
        ty = -(a21 * x_n + a22 * y_n)

        theta_mat = torch.stack([a11, a12, tx, a21, a22, ty]).reshape(1, 2, 3)

        grid = F.affine_grid(
            theta_mat, [1, 1, canvas_h, canvas_w], align_corners=False,
        )
        warped = F.grid_sample(
            sprite, grid,
            mode="bilinear", padding_mode="zeros", align_corners=False,
        )

        # SUM instead of alpha-over — allows values to exceed 1.0
        additive = additive + warped

    return additive

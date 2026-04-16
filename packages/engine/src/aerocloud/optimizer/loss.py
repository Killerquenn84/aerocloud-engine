"""Loss functions for the inner-loop optimizer (Phase 6).

Implements the 4-part composite loss per D-01..D-06 of the AeroCloud Blueprint:

    L_total = alpha * L_wmse + beta * L_overlap + gamma * L_fidelity + lambda_ * L_temporal

Phase 7 / D-21: ``compute_additive_density`` has been removed.  The renderer
now produces both alpha-over density and additive density in a single forward
pass via ``DifferentiableRenderer.forward(h, w, mode='both')`` (fixes F-3
and F-10).  InnerLoop.optimize() unpacks the tuple directly.
"""

from __future__ import annotations

import torch
import torch.nn.functional as F  # noqa: N812

from aerocloud.models.optimizer import LossWeights


def compute_l_wmse(
    density: torch.Tensor,
    sdf: torch.Tensor,
) -> torch.Tensor:
    """Weighted Mean Squared Error loss (D-01, extended with outside penalty).

    Two complementary terms:
    1. **Inside penalty**: uncovered interior pixels weighted by SDF depth.
       ``mean((clamp(sdf, min=0) * (1 - density))^2)``
    2. **Outside penalty**: density that leaks beyond the silhouette boundary.
       ``mean((clamp(-sdf, min=0) * density)^2)``

    Without the outside penalty, words can expand freely beyond the
    silhouette because only L_overlap constrains sprite-to-sprite overlap,
    not silhouette boundary adherence (F-1 finding, Gemini+Codex consensus).

    Args:
        density: (1, 1, H, W) float32 renderer output in [0, 1].
        sdf: (1, 1, H, W) float32 signed distance field.
            Positive inside the shape, negative outside.

    Returns:
        Scalar tensor.
    """
    sdf_positive = sdf.clamp(min=0.0)
    sdf_negative = (-sdf).clamp(min=0.0)
    inside_penalty = ((sdf_positive * (1.0 - density)) ** 2).mean()
    outside_penalty = ((sdf_negative * density) ** 2).mean()
    return inside_penalty + outside_penalty


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
    return 1.0 - F.cosine_similarity(s_ref.unsqueeze(0), s_current.unsqueeze(0)).squeeze()


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

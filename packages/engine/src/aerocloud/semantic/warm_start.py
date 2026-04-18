"""Semantic warm-start glue function for DifferentiableRenderer (Phase 8, SEM-08).

Chains BERT embeddings → cosine distance → UMAP/t-SNE projection →
Sinkhorn-Knopp transport → (N, 4) params tensor for the Inner Loop.

Purpose:
    Replaces random/spiral initialization in the Inner Loop with
    semantically-informed positions, where similar words are placed near
    each other. The function is the public API that Phase 9 (Outer Loop)
    and production callers will use.

Design decisions:
    D-11: External function — no InnerLoop API changes. semantic_warm_start
        accepts candidates, sdf, mat_result and returns (N, 4) tensor.
        Scale=1.0, theta=0.0 per spec.
    D-12: Sinkhorn → SDF coordinates: UMAP projected coords are rescaled
        to the SDF interior bounding box. MAT branch origins serve as
        primary anchor target positions; UMAP-scaled fill provides
        remaining positions when N > num_branches.
    T-08-07: Inside-pixel search is O(H*W) worst case; bounded by SDF size
        which is bounded by config (mitigation: only called per-position,
        not per-pixel).

References:
    - .planning/phases/08-semantic-vector-space/08-04-PLAN.md
    - .planning/phases/08-semantic-vector-space/08-RESEARCH.md §D-11, §D-12
    - AeroCloud Blueprint Teil II §2.2 (Sinkhorn warm-start)
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import structlog
import torch
from scipy.spatial.distance import cdist

from aerocloud.config import settings
from aerocloud.geometry.mat import MATResult
from aerocloud.models.tokens import WordCandidate
from aerocloud.semantic.cosine import cosine_similarity_matrix
from aerocloud.semantic.embeddings import encode_surfaces
from aerocloud.semantic.projection import project_to_2d
from aerocloud.semantic.transport import compute_transport

logger = structlog.get_logger(__name__)


def semantic_warm_start(
    candidates: list[WordCandidate],
    sdf: np.ndarray,
    mat_result: MATResult,
    config: dict[str, object] | None = None,
) -> torch.Tensor:
    """Compute semantically-informed initial positions for DifferentiableRenderer (D-11).

    Pipeline:
    1. Encode candidate surfaces → (N, 384) embeddings via BERT
    2. Cosine similarity matrix → distance cost matrix
    3. UMAP/t-SNE project embeddings → (N, 2) semantic positions
    4. Build target positions from MAT branch origins (+ UMAP-scaled fill)
    5. Sinkhorn transport: assign words to canvas positions
    6. Map assigned positions to SDF canvas coordinates (D-12)
    7. Return (N, 4) tensor [y, x, 1.0, 0.0]

    Args:
        candidates: List of N WordCandidates from NLP pipeline.
        sdf: (H, W) float32 SDF array (positive=inside, ADR-0004 convention).
        mat_result: MATResult with branch origins for target positions.
        config: Optional overrides — keys:
            "seed" (int): Random seed for UMAP/t-SNE (default: settings.seed).
            "projection_method" (str): "umap" or "tsne" (default: settings.projection_method).
            "eps_init" (float): Sinkhorn initial epsilon (default: settings.sinkhorn_eps_init).

    Returns:
        (N, 4) float32 tensor [y, x, scale, theta] with requires_grad=False.
        Column 2 (scale) is all 1.0. Column 3 (theta) is all 0.0 per D-11.
        All (y, x) positions are inside the SDF positive region per D-12.

    Example:
        >>> import numpy as np
        >>> from aerocloud.geometry.mat import extract_mat
        >>> H, W = 128, 128
        >>> sdf = np.zeros((H, W), dtype=np.float32)
        >>> sdf[32:96, 32:96] = 10.0  # square positive region
        >>> mat = extract_mat(sdf)
        >>> candidates = [WordCandidate(surface="cloud", stem="cloud", score=5.0, font_size=24.0)]
        >>> params = semantic_warm_start(candidates, sdf, mat, config={"seed": 42})
        >>> params.shape
        torch.Size([1, 4])
        >>> params[0, 2].item()
        1.0
    """
    N = len(candidates)
    _seed_val = config.get("seed", settings.seed) if config else settings.seed
    seed: int = int(_seed_val) if isinstance(_seed_val, (int, float, str)) else settings.seed
    _method_val = config.get("projection_method", settings.projection_method) if config else settings.projection_method
    _method_str = str(_method_val) if _method_val is not None else settings.projection_method
    method: Literal["umap", "tsne"] = "tsne" if _method_str == "tsne" else "umap"
    _eps_val = config.get("eps_init", settings.sinkhorn_eps_init) if config else settings.sinkhorn_eps_init
    eps_init: float = float(_eps_val) if isinstance(_eps_val, (int, float, str)) else settings.sinkhorn_eps_init

    surfaces = [c.surface for c in candidates]
    logger.info("semantic.warm_start.start", n=N, method=method, seed=seed)

    # Step 1: BERT encode → (N, 384) float32
    embeddings = encode_surfaces(surfaces)

    # Step 2: Cosine similarity → distance cost matrix (N, N)
    sim_matrix = cosine_similarity_matrix(embeddings)
    cost_matrix = (1.0 - sim_matrix).astype(np.float64)  # cosine distance

    # Step 3: UMAP/t-SNE project embeddings → (N, 2) semantic 2D positions
    coords_2d = project_to_2d(embeddings, method=method, seed=seed)  # (N, 2) float32

    # Step 4: Build N target positions on the SDF canvas (D-12)
    target_positions = _build_target_positions(coords_2d, sdf, mat_result, N)

    # Step 5: Sinkhorn transport
    # Cost: Euclidean distance between UMAP word positions and canvas target positions
    transport_cost = cdist(
        coords_2d.astype(np.float64),
        target_positions.astype(np.float64),
        metric="euclidean",
    )
    plan = compute_transport(transport_cost, eps_init=eps_init)

    # Step 6: Assign canvas positions via transport matrix argmax per word
    T = plan.transport_matrix  # (N, N) float64
    assignments = T.argmax(axis=1)  # each word → best target position index
    assigned_positions = target_positions[assignments]  # (N, 2) float32

    # Step 7: Build (N, 4) params tensor [y, x, scale=1.0, theta=0.0]
    params = np.zeros((N, 4), dtype=np.float32)
    params[:, 0] = assigned_positions[:, 0]  # y
    params[:, 1] = assigned_positions[:, 1]  # x
    params[:, 2] = 1.0  # scale — D-11
    params[:, 3] = 0.0  # theta — D-11

    result = torch.from_numpy(params)  # requires_grad=False by default
    logger.info(
        "semantic.warm_start.complete",
        n=N,
        eps=plan.eps_used,
        iterations=plan.iterations,
    )
    return result


def _build_target_positions(
    coords_2d: np.ndarray,
    sdf: np.ndarray,
    mat_result: MATResult,
    n_positions: int,
) -> np.ndarray:
    """Build N target positions on the SDF canvas from MAT branches + UMAP fill (D-12).

    Strategy:
    1. Start with MAT branch origin_yx points (deepest interior points per branch)
    2. If N > num_branches, fill remaining slots with UMAP-projected positions
       scaled to the SDF interior bounding box
    3. Truncate to exactly N positions if num_branches > N
    4. All positions clamped to valid SDF > 0 region (snap to nearest inside pixel)

    Args:
        coords_2d: (N, 2) float32 UMAP/t-SNE 2D coordinates.
        sdf: (H, W) float32 SDF array (positive = inside).
        mat_result: MATResult with MAT branches.
        n_positions: Number of target positions to produce.

    Returns:
        (N, 2) float32 array of (y, x) canvas positions, all inside SDF > 0.
    """
    H, W = sdf.shape

    # Collect MAT branch origins as primary anchor positions
    positions: list[np.ndarray] = []
    for branch in mat_result.branches:
        positions.append(np.array(branch.origin_yx, dtype=np.float32))

    # Find SDF interior region bounding box
    inside_yx = np.argwhere(sdf > 0)
    if len(inside_yx) == 0:
        # Pathological: no inside pixels — use canvas centre
        inside_min = np.array([H / 4.0, W / 4.0], dtype=np.float32)
        inside_max = np.array([3.0 * H / 4.0, 3.0 * W / 4.0], dtype=np.float32)
    else:
        inside_min = inside_yx.min(axis=0).astype(np.float32)
        inside_max = inside_yx.max(axis=0).astype(np.float32)

    # Scale UMAP 2D coordinates to the SDF interior bounding box
    umap_min = coords_2d.min(axis=0)
    umap_max = coords_2d.max(axis=0)
    umap_range = umap_max - umap_min
    # Avoid division by zero for degenerate 1-point or colinear embeddings
    umap_range = np.where(np.abs(umap_range) < 1e-8, 1.0, umap_range)

    scaled_unit = (coords_2d - umap_min) / umap_range  # → [0, 1] per dimension
    interior_range = inside_max - inside_min
    canvas_coords = (scaled_unit * interior_range + inside_min).astype(np.float32)  # (N, 2)

    # Fill remaining positions beyond the MAT branch count
    for i in range(len(positions), n_positions):
        idx = i % len(canvas_coords)
        positions.append(canvas_coords[idx])

    # Truncate if we have more MAT branches than words
    positions = positions[:n_positions]

    result = np.array(positions, dtype=np.float32)  # (N, 2)

    # Clamp to canvas bounds
    result[:, 0] = np.clip(result[:, 0], 0, H - 1)
    result[:, 1] = np.clip(result[:, 1], 0, W - 1)

    # Snap any position outside the SDF positive region to the nearest inside pixel
    if len(inside_yx) > 0:
        for i in range(n_positions):
            y_idx = int(round(float(result[i, 0])))
            x_idx = int(round(float(result[i, 1])))
            # Clamp indices to valid canvas range
            y_idx = max(0, min(y_idx, H - 1))
            x_idx = max(0, min(x_idx, W - 1))
            if float(sdf[y_idx, x_idx]) <= 0.0:
                # T-08-07: O(P) search over inside pixels — bounded by SDF canvas size
                dists = np.sqrt(
                    ((inside_yx[:, 0] - y_idx) ** 2 + (inside_yx[:, 1] - x_idx) ** 2).astype(
                        np.float64
                    )
                )
                nearest_idx = int(dists.argmin())
                result[i, 0] = float(inside_yx[nearest_idx, 0])
                result[i, 1] = float(inside_yx[nearest_idx, 1])

    return result

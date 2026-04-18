"""Behavioral descriptor computation for MAP-Elites (Outer Loop).

Computes the 4D behavioral descriptor vector from post-optimization layout data:
    [shape_fidelity, rotation_ratio, symmetry, semantic_clustering]

All values are clamped to [0.0, 1.0] before constructing BehaviorDescriptor.

References:
    - .planning/phases/09-outer-loop-v1/09-01-PLAN.md (Task 2)
    - .planning/phases/09-outer-loop-v1/09-RESEARCH.md (BD computation table)
    - D-17: behavioral descriptors computed from post-optimization layout data
    - Pitfall 5: clamp to [0,1] before archive.add
    - (y, x) coordinate convention throughout (CLAUDE.md constraint)
"""

from __future__ import annotations

import math

import numpy as np
import torch
from scipy.spatial.distance import cdist

from aerocloud.models.archive import BehaviorDescriptor


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp a float to [lo, hi]."""
    return max(lo, min(hi, value))


def compute_descriptors(
    params: torch.Tensor,
    lc_metric: float,
    embeddings: np.ndarray,
    positions_yx: np.ndarray,
    sdf_mask: np.ndarray,
    n_words: int,
) -> BehaviorDescriptor:
    """Compute the 4D behavioral descriptor from post-optimization layout data.

    Args:
        params:       (N, 4) or larger params tensor [y, x, scale, rotation].
                      Only the first ``n_words`` rows are used (Pitfall 3 —
                      solution may be padded to max_words).
        lc_metric:    Layout Coverage metric value, already in [0.0, 1.0].
                      Used directly as shape_fidelity (per RESEARCH BD table).
        embeddings:   (n_words, 384) float32 BERT embeddings for placed words.
        positions_yx: (n_words, 2) float32 word positions in (y, x) format
                      in pixel coordinates.
        sdf_mask:     (H, W) bool array — True inside silhouette.
        n_words:      Actual word count (params may be padded beyond this).

    Returns:
        BehaviorDescriptor with shape_fidelity, rotation_ratio, symmetry,
        and semantic_clustering all in [0.0, 1.0].
    """
    # Slice to actual word count (Pitfall 3)
    actual_params = params[:n_words]  # (n_words, 4)
    rotations = actual_params[:, 3].detach().cpu().numpy()  # (n_words,)

    # ------------------------------------------------------------------
    # 1. shape_fidelity = LC metric (RESEARCH: shape_fidelity = LC metric value)
    # ------------------------------------------------------------------
    shape_fidelity = _clamp(float(lc_metric))

    # ------------------------------------------------------------------
    # 2. rotation_ratio = fraction of words with |theta| > pi/4
    # ------------------------------------------------------------------
    rotation_ratio = float(np.mean(np.abs(rotations) > (math.pi / 4)))
    rotation_ratio = _clamp(rotation_ratio)

    # ------------------------------------------------------------------
    # 3. symmetry: horizontal reflection score
    #    Project word positions onto the horizontal axis.
    #    Compare left-half density to right-half density via:
    #    1 - |mean_x_left_mirrored - mean_x_right| / canvas_width
    #    Clamped to [0, 1].
    # ------------------------------------------------------------------
    symmetry = _compute_symmetry(positions_yx, sdf_mask)
    symmetry = _clamp(symmetry)

    # 4. semantic_clustering: 1 - normalized distortion ratio between
    # spatial proximity and embedding similarity.
    # Captures how well semantically similar words are spatially close.
    semantic_clustering = _compute_semantic_clustering(positions_yx, embeddings)
    semantic_clustering = _clamp(semantic_clustering)

    return BehaviorDescriptor(
        shape_fidelity=shape_fidelity,
        rotation_ratio=rotation_ratio,
        symmetry=symmetry,
        semantic_clustering=semantic_clustering,
    )


def _compute_symmetry(positions_yx: np.ndarray, sdf_mask: np.ndarray) -> float:
    """Compute horizontal symmetry score from word positions.

    Approach: Split word (x) positions into left and right halves around the
    canvas centre. Mirror left-half x-coordinates and compare to right-half
    using mean distance ratio.

    Args:
        positions_yx: (n_words, 2) array in (y, x) format.
        sdf_mask:     (H, W) bool mask — used to determine canvas width.

    Returns:
        Symmetry score in [0.0, 1.0] (clamped by caller).
    """
    if len(positions_yx) == 0:
        return 0.5  # neutral

    canvas_w = sdf_mask.shape[1] if sdf_mask.ndim == 2 else 1
    x_positions = positions_yx[:, 1].astype(float)  # (y, x) convention → index 1 is x
    cx = canvas_w / 2.0

    left_x = x_positions[x_positions < cx]
    right_x = x_positions[x_positions >= cx]

    if len(left_x) == 0 or len(right_x) == 0:
        # All words on one side — low symmetry
        return 0.0

    # Mirror left-side x-coordinates
    mirrored_left_x = 2.0 * cx - left_x
    mean_mirrored = float(np.mean(mirrored_left_x))
    mean_right = float(np.mean(right_x))

    if canvas_w <= 0:
        return 0.5

    # 1 - normalized |mirrored_mean - right_mean| / canvas_w
    return 1.0 - abs(mean_mirrored - mean_right) / float(canvas_w)


def _compute_semantic_clustering(positions_yx: np.ndarray, embeddings: np.ndarray) -> float:
    """Compute semantic clustering score: how well spatial proximity matches semantic similarity.

    Score = 1 - clamp(mean_spatial_dist_per_embedding_dist_unit)

    Uses scipy cdist for both spatial (Euclidean) and embedding (cosine) distances.

    Args:
        positions_yx: (n_words, 2) word positions in (y, x) format.
        embeddings:   (n_words, D) word embeddings.

    Returns:
        Semantic clustering score in [0.0, 1.0] (clamped by caller).
    """
    n = len(positions_yx)
    if n <= 1:
        return 0.5  # neutral — cannot compute pairwise distances

    # Spatial distances (Euclidean, (n, n))
    spatial_dists = cdist(positions_yx, positions_yx, metric="euclidean")

    # Embedding distances (cosine, (n, n))
    # Normalize embeddings to unit sphere first for numerical stability
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms > 0, norms, 1.0)
    normed_embs = embeddings / norms
    embedding_dists = cdist(normed_embs, normed_embs, metric="cosine")

    # Extract upper-triangle pairs (exclude diagonal)
    triu_idx = np.triu_indices(n, k=1)
    s_pairs = spatial_dists[triu_idx]  # (n_pairs,)
    e_pairs = embedding_dists[triu_idx]  # (n_pairs,)

    if len(s_pairs) == 0:
        return 0.5

    # Mean spatial distance, mean embedding distance
    mean_s = float(np.mean(s_pairs))
    mean_e = float(np.mean(e_pairs))

    if mean_e <= 0:
        # All embeddings identical — clustering undefined, return neutral
        return 0.5

    # Distortion ratio: spatial spread per unit embedding distance
    # High ratio → semantically similar words are far apart (low clustering)
    # Normalize by max possible spatial distance (canvas diagonal estimate)
    max_spatial = float(np.max(s_pairs)) if float(np.max(s_pairs)) > 0 else 1.0
    distortion = (mean_s / max_spatial) * (1.0 - mean_e)

    # Invert: high distortion → low clustering
    return 1.0 - _clamp(distortion)

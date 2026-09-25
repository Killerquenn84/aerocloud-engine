"""Seam carving export module for AeroCloud word cloud layout (PROD-01, PROD-02).

Implements energy-based seam carving to adaptively resize the word cloud canvas
while preserving word positions. The energy map encodes word importance via
Gaussian weighting, and Dynamic Programming finds the optimal low-energy seam.

References:
    - PROD-01: Energy function E(x,y) = sum(w_i * Gauss(distance)) — Blueprint Teil VI
    - PROD-02: DP seam finder O(w*h) — Blueprint Teil VI
    - T-12-01-01: DoS mitigation — canvas dimensions capped at 4096

Design decisions:
    - Pure numpy: no torch dependency in export modules
    - Vectorized DP inner loop: uses np.minimum on shifted arrays (no Python loop over columns)
    - (y, x) coordinate convention matches the rest of the engine (D-14)
"""

from __future__ import annotations

import numpy as np

_MAX_CANVAS_DIM = 4096  # T-12-01-01: DoS mitigation — reject oversized inputs


def build_energy_map(
    canvas_h: int,
    canvas_w: int,
    word_positions: list[tuple[int, int]],
    word_weights: list[float],
    sigma: float = 15.0,
) -> np.ndarray:
    """Build a Gaussian-weighted energy map from word positions and weights.

    Each word contributes a Gaussian "bump" centered at its position, scaled by
    its weight. The total energy at each pixel is the sum of all word contributions:
        E(y, x) = sum_i(w_i * exp(-dist(y,x, y_i,x_i)^2 / (2*sigma^2)))

    Args:
        canvas_h: Canvas height in pixels. Must be <= 4096 (T-12-01-01).
        canvas_w: Canvas width in pixels. Must be <= 4096 (T-12-01-01).
        word_positions: List of (y, x) word center positions in pixel coordinates.
        word_weights: List of weights per word (same length as word_positions).
        sigma: Gaussian spread in pixels. Larger sigma = wider energy influence.

    Returns:
        Float64 ndarray of shape (canvas_h, canvas_w) with non-negative energy values.
        Returns all-zeros if word_positions is empty.

    Raises:
        ValueError: If canvas_h or canvas_w exceeds 4096 (T-12-01-01 DoS guard).
    """
    # T-12-01-01: Reject oversized canvas to prevent memory explosion
    if canvas_h > _MAX_CANVAS_DIM or canvas_w > _MAX_CANVAS_DIM:
        raise ValueError(
            f"canvas dimensions ({canvas_h}, {canvas_w}) exceed maximum "
            f"{_MAX_CANVAS_DIM}. Reduce canvas size. (T-12-01-01)"
        )

    energy = np.zeros((canvas_h, canvas_w), dtype=np.float64)

    if not word_positions:
        return energy

    # Vectorized: build (H, W) coordinate grids once
    # ys shape: (H, 1), xs shape: (1, W) — broadcast to (H, W) for each word
    ys, xs = np.mgrid[0:canvas_h, 0:canvas_w]  # both shape (H, W)
    ys = ys.astype(np.float64)
    xs = xs.astype(np.float64)

    two_sigma_sq = 2.0 * sigma * sigma

    for (wy, wx), w in zip(word_positions, word_weights, strict=True):
        dist_sq = (ys - wy) ** 2 + (xs - wx) ** 2
        energy += w * np.exp(-dist_sq / two_sigma_sq)

    return energy


def find_vertical_seam(energy: np.ndarray) -> np.ndarray:
    """Find the minimum-cost vertical seam through an energy map via Dynamic Programming.

    A vertical seam is a path from the top row to the bottom row where each step
    moves to an adjacent column (at most ±1). The seam minimises total energy.

    DP recurrence:
        dp[r, c] = energy[r, c] + min(dp[r-1, c-1], dp[r-1, c], dp[r-1, c+1])

    The inner loop is vectorized: for each row, we compute the minimum of three
    shifted copies of the previous dp row (no Python for-loop over columns).

    Args:
        energy: 2D float64 array of shape (H, W) representing pixel energy values.

    Returns:
        Int32 array of length H containing column indices of the optimal seam.
        Adjacent entries differ by at most 1. Values are in [0, W-1].

    References:
        PROD-02: DP seam finder O(w*h) — Blueprint Teil VI
    """
    h, w = energy.shape
    dp = energy.copy()

    # Forward pass: fill DP table row-by-row (vectorized per row)
    for r in range(1, h):
        prev = dp[r - 1]  # shape (W,)
        # Three neighbours: left-shifted, centre, right-shifted
        left = np.empty(w, dtype=np.float64)
        right = np.empty(w, dtype=np.float64)
        left[0] = np.inf
        left[1:] = prev[:-1]
        right[w - 1] = np.inf
        right[:-1] = prev[1:]
        # Vectorized min across three options
        dp[r] += np.minimum(prev, np.minimum(left, right))

    # Backtrack from minimum in last row
    seam = np.empty(h, dtype=np.int32)
    seam[h - 1] = int(np.argmin(dp[h - 1]))

    for r in range(h - 2, -1, -1):
        c = seam[r + 1]
        # Look at at most 3 neighbours in the row above
        lo = max(0, c - 1)
        hi = min(w - 1, c + 1)
        # argmin within [lo, hi] slice; offset back to full-width index
        seam[r] = lo + int(np.argmin(dp[r, lo : hi + 1]))

    return seam


def remove_vertical_seam(image: np.ndarray, seam: np.ndarray) -> np.ndarray:
    """Remove a vertical seam from an image, reducing its width by 1.

    For each row r, the pixel at column seam[r] is removed. The operation
    works on both 2D (H, W) and 3D (H, W, C) arrays.

    Args:
        image: Input image as numpy array of shape (H, W) or (H, W, C).
        seam: Int32 array of length H with column indices to remove per row.

    Returns:
        New array with one fewer column (H, W-1) or (H, W-1, C).

    References:
        PROD-02: seam removal after DP seam finding — Blueprint Teil VI
    """
    h, w = image.shape[:2]
    is_3d = image.ndim == 3
    channels = image.shape[2] if is_3d else 1

    if is_3d:
        output = np.empty((h, w - 1, channels), dtype=image.dtype)
    else:
        output = np.empty((h, w - 1), dtype=image.dtype)

    for r in range(h):
        c = seam[r]
        if is_3d:
            output[r, :c, :] = image[r, :c, :]
            output[r, c:, :] = image[r, c + 1 :, :]
        else:
            output[r, :c] = image[r, :c]
            output[r, c:] = image[r, c + 1 :]

    return output

"""Convergence detection for the inner-loop optimizer (Phase 6).

Implements rolling-window plateau detection per D-14/D-15 of the
AeroCloud Blueprint.
"""

from __future__ import annotations


def check_convergence(
    loss_history: list[float],
    window: int = 10,
    epsilon: float = 0.001,
) -> bool:
    """Detect a loss plateau using a rolling window.

    Returns True if the relative range of the last ``window`` loss values
    is below ``epsilon``, indicating the optimizer has converged.

    The relative range is computed as::

        (max(window) - min(window)) / max(abs(max(window)), 1e-8)

    Args:
        loss_history: Recorded loss values, oldest first.
        window: Number of recent epochs to inspect.  Must be >= 2.
        epsilon: Convergence threshold for the relative range.

    Returns:
        True if converged, False if not enough data or range is too large.
    """
    if len(loss_history) < window:
        return False

    window_vals = loss_history[-window:]
    max_val = max(window_vals)
    min_val = min(window_vals)
    range_val = max_val - min_val
    scale = max(abs(max_val), abs(min_val), 1e-8)
    return (range_val / scale) < epsilon

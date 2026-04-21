"""AdversarialReviewer: rule-based heuristic to detect reward hacking (Plan 10-02, Task 2).

Implements 4 rejection rules in priority order:
    Rule 3 (degenerate_layout): layout_coverage < 0.1 — layout is essentially empty.
    Rule 2 (ood_parameters):    any |z_score| > 3.0 — solution out of archive distribution.
    Rule 4 (gaming_aspect_ratio): AR weighted contribution > 50% of combined fitness.
    Rule 1 (reward_hacking):    combined fitness up but >= 2 individual metrics decrease.

Priority rationale:
    - Degenerate layout is the cheapest O(1) check and the most common failure mode.
    - OOD detection is cheap (vectorized z-score) and catches implausible solutions.
    - Metric gaming is a structural property (no baseline needed).
    - Reward hacking requires baseline comparison (most expensive, checked last).

Design decisions:
    D-10: Rule-based heuristics only; no ML model; deterministic and interpretable.
    D-11: Returns (accepted: bool, reason: str) — empty string on acceptance.
    D-12: >5% rejection rate is a success criterion tested at integration level (Plan 04).

Security:
    T-10-05: Solutions are read-only; no mutation happens in reviewer.
    T-10-06: Archive stats (mean/std) computed once at __init__; O(1) per review call.
"""

from __future__ import annotations

import numpy as np

from aerocloud.outer_loop.models import QualityMetrics, QualityWeights

# All 7 metric field names in QualityMetrics (used for Rule 1 individual-metric comparison)
_METRIC_FIELDS: list[str] = [
    "layout_coverage",
    "layout_uniformity",
    "space_saving",
    "compactness",
    "aspect_ratio",
    "realized_adjacencies",
    "distortion_score",
]

_DEGENERATE_LC_THRESHOLD: float = 0.1    # Rule 3: strict < 0.1
_OOD_ZSCORE_THRESHOLD: float = 3.0       # Rule 2: |z| > 3.0
_GAMING_SHARE_THRESHOLD: float = 0.5     # Rule 4: > 50% of combined fitness
_REWARD_HACK_MIN_DECREASES: int = 2      # Rule 1: >= 2 metrics must decrease


class AdversarialReviewer:
    """Rule-based heuristic reviewer that detects reward-hacking in Self-Play candidates.

    Uses archive statistics computed at construction time to identify solutions
    that are degenerate, out-of-distribution, or gaming a single metric.

    Args:
        archive_solutions: ndarray of shape (n_elites, solution_dim) — all current
                           elite solutions in the archive.
        weights:           QualityWeights used for combined_fitness calculations.
    """

    def __init__(
        self,
        archive_solutions: np.ndarray,
        weights: QualityWeights,
    ) -> None:
        self._weights = weights

        # Compute archive statistics for Rule 2 (OOD z-score detection)
        # Use ddof=0 (population std) for large archives; add epsilon for zero-div safety
        self._archive_mean: np.ndarray = np.mean(archive_solutions, axis=0)
        self._archive_std: np.ndarray = np.std(archive_solutions, axis=0) + 1e-8

    def review(
        self,
        solution: np.ndarray,
        metrics_new: QualityMetrics,
        metrics_baseline: QualityMetrics | None,
    ) -> tuple[bool, str]:
        """Evaluate a candidate solution against all 4 adversarial rules.

        Rules are evaluated in priority order (cheapest/most-critical first):
            1. Rule 3: degenerate layout
            2. Rule 2: OOD parameters
            3. Rule 4: single-metric gaming
            4. Rule 1: reward hacking (only if baseline provided)

        Args:
            solution:         Flat ndarray (solution_dim,) — the candidate params.
            metrics_new:      QualityMetrics for the candidate solution.
            metrics_baseline: QualityMetrics for the parent/baseline, or None to
                              skip Rule 1.

        Returns:
            (True, "") if all rules pass.
            (False, reason_string) on first rule violation.
        """
        # Rule 3 — Degenerate layout (cheapest, checked first)
        if metrics_new.layout_coverage < _DEGENERATE_LC_THRESHOLD:
            return (
                False,
                f"degenerate_layout: layout_coverage < {_DEGENERATE_LC_THRESHOLD}",
            )

        # Rule 2 — OOD parameters
        z_scores = np.abs((solution - self._archive_mean) / self._archive_std)
        if float(np.max(z_scores)) > _OOD_ZSCORE_THRESHOLD:
            return (False, "ood_parameters: z_score > 3.0")

        # Rule 4 — Single-metric gaming (aspect_ratio)
        combined = metrics_new.combined_fitness(self._weights)
        if combined > 0.0:
            ar_contribution = self._weights.w_ar * metrics_new.aspect_ratio
            ar_share = ar_contribution / combined
            if ar_share > _GAMING_SHARE_THRESHOLD:
                return (
                    False,
                    "gaming_aspect_ratio: single metric > 50% of total fitness",
                )

        # Rule 1 — Reward hacking (requires baseline)
        if metrics_baseline is not None:
            result = self._check_reward_hacking(metrics_new, metrics_baseline)
            if result is not None:
                return result

        return (True, "")

    def _check_reward_hacking(
        self,
        metrics_new: QualityMetrics,
        metrics_baseline: QualityMetrics,
    ) -> tuple[bool, str] | None:
        """Rule 1: reject if combined fitness increases but >= 2 individual metrics decrease.

        Args:
            metrics_new:      Candidate quality metrics.
            metrics_baseline: Baseline (parent) quality metrics.

        Returns:
            (False, reason) if reward hacking detected, else None (rule passes).
        """
        combined_new = metrics_new.combined_fitness(self._weights)
        combined_baseline = metrics_baseline.combined_fitness(self._weights)

        # Only check if combined fitness actually increased
        if combined_new <= combined_baseline:
            return None

        # Count how many individual metrics decreased
        n_decreased = 0
        for field in _METRIC_FIELDS:
            val_new: float = float(getattr(metrics_new, field))
            val_old: float = float(getattr(metrics_baseline, field))
            if val_new < val_old:
                n_decreased += 1

        if n_decreased >= _REWARD_HACK_MIN_DECREASES:
            return (
                False,
                f"reward_hacking: {n_decreased} metrics decreased while combined increased",
            )

        return None

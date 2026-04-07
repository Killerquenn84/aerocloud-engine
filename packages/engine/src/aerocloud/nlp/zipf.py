"""Zipf log-normalization — maps scores to font sizes.

Font sizes in a word cloud must follow a power-law distribution to match
natural-language frequency statistics (Blueprint Teil 1.2: Zipf).

The formula is ``font_size(r) = min_size + scale * log(score_max / score(r))``
where r is the rank (0 for the top word). The log ensures the top word
is largest and the tail is compressed — matching perceptual size-ranking
in Zipf-distributed text.
"""

from __future__ import annotations

import math


def zipf_font_sizes(
    scores: dict[str, float],
    min_size: float = 10.0,
    max_size: float = 96.0,
) -> dict[str, float]:
    """Return ``stem -> font_size`` via log-normalization.

    Args:
        scores: ``stem -> raw TF-IDF-AP score``. Non-positive scores are
            filtered out.
        min_size: Smallest font size in pixels (must be > 0).
        max_size: Largest font size in pixels (must be > ``min_size``).

    Returns:
        ``stem -> font_size`` dict. Empty if the input has no positive scores.
    """
    if min_size <= 0:
        raise ValueError(f"min_size must be > 0, got {min_size}")
    if max_size <= min_size:
        raise ValueError(f"max_size must be > min_size, got {max_size} <= {min_size}")

    positive = {k: v for k, v in scores.items() if v > 0}
    if not positive:
        return {}

    # Sort by descending score; rank 0 = largest
    ranked = sorted(positive.items(), key=lambda kv: kv[1], reverse=True)
    top_score = ranked[0][1]

    # If all scores are equal, every word gets max_size
    if all(score == top_score for _, score in ranked):
        return {stem: max_size for stem, _ in ranked}

    # Log-scale: top stem gets log(1) = 0 -> max_size
    # Tail stems get log(top/score) > 0 -> smaller sizes
    log_ratios = [math.log(top_score / score) for _, score in ranked]
    max_log = max(log_ratios)  # guaranteed > 0 by the equality check above

    size_range = max_size - min_size
    sizes: dict[str, float] = {}
    for (stem, _), log_ratio in zip(ranked, log_ratios, strict=True):
        fraction = log_ratio / max_log  # in [0, 1]
        sizes[stem] = max_size - fraction * size_range

    return sizes

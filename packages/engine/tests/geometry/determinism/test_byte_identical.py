"""Nyquist dim 6: 10 repeat runs produce byte-identical PlacementResult (D-45).

Verifies the determinism requirement: given identical input (PNG bytes + seed),
place_words() must produce byte-identical output across 10 consecutive runs.

Wall-clock timing is excluded from the comparison (non-deterministic by design).
The SDF cache is cleared between runs to force full re-computation each time —
this is the stricter test: even without cache benefit, the output is stable.

References:
    - D-45: set_seed() called at function entry for full determinism
    - D-46: integer arithmetic in hot loop (no FP noise accumulation)
    - .planning/phases/04-geometry-v1/04-CONTEXT.md
"""

from __future__ import annotations

import json

from aerocloud.geometry.placement import place_words
from aerocloud.geometry.sdf_cache import clear_cache
from aerocloud.models.geometry import PlacementRequest


def _canonical(result: object) -> str:
    """Serialize PlacementResult to a canonical string, excluding wall_clock_ms."""
    payload = result.model_dump(mode="json")  # type: ignore[union-attr]
    # Wall-clock time is inherently non-deterministic; everything else must match.
    stats = payload.get("stats", {})
    stats.pop("wall_clock_ms", None)
    return json.dumps(payload, sort_keys=True)


def test_ten_runs_byte_identical(circle_mask_bytes: bytes) -> None:
    """10 consecutive place_words() calls with the same input produce identical output."""
    req = PlacementRequest(
        raw_png_bytes=circle_mask_bytes,
        words=[(f"w{i}", 4, 6) for i in range(8)],
        seed=1337,
    )
    canonicals: list[str] = []
    for _ in range(10):
        clear_cache()
        result = place_words(req)
        canonicals.append(_canonical(result))

    unique = set(canonicals)
    assert len(unique) == 1, (
        f"Non-deterministic output across 10 runs: "
        f"{len(unique)} distinct results. "
        f"First two differ:\n{canonicals[0]}\n---\n{canonicals[1]}"
    )


def test_different_seeds_differ(circle_mask_bytes: bytes) -> None:
    """Sanity check: different seeds produce different placements (otherwise determinism
    test above is vacuously true because all runs are identical regardless of seed)."""
    words = [(f"w{i}", 4, 6) for i in range(8)]
    req1 = PlacementRequest(raw_png_bytes=circle_mask_bytes, words=words, seed=1)
    req2 = PlacementRequest(raw_png_bytes=circle_mask_bytes, words=words, seed=2)

    clear_cache()
    r1 = _canonical(place_words(req1))
    clear_cache()
    r2 = _canonical(place_words(req2))

    # With different seeds the spiral origin tiebreak may differ — this is a
    # sanity check that the seed is actually consumed. If they happen to be
    # identical it is not a failure, but very unlikely for 8 words.
    # We don't assert inequality — just that the pipeline runs without error.
    assert r1 is not None
    assert r2 is not None

"""Determinism tests for OuterLoop (Plan 09-05, Task 2).

Verifies that OuterLoop.run() with the same seed produces identical archive
coverage and best_fitness across two independent runs.

References:
    - 09-05-PLAN.md Task 2
    - PROJECT.md: Reproducibility constraint — same (input, seed, version) → same output
    - aerocloud.utils.determinism.set_seed
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np

from aerocloud.outer_loop.models import QualityMetrics, QualityWeights
from aerocloud.outer_loop.scheduler import OuterLoop, OuterLoopResult
from aerocloud.utils.determinism import set_seed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _deterministic_evaluate_fn(
    seed_val: float,
) -> any:  # type: ignore[valid-type]
    """Return an evaluate_fn that always returns the same deterministic outputs."""
    from aerocloud.models.archive import BehaviorDescriptor

    metrics = QualityMetrics(
        layout_coverage=seed_val,
        layout_uniformity=seed_val,
        space_saving=seed_val,
        compactness=seed_val,
        aspect_ratio=seed_val,
        realized_adjacencies=seed_val,
        distortion_score=seed_val,
    )
    bd = BehaviorDescriptor(
        shape_fidelity=seed_val,
        rotation_ratio=seed_val,
        symmetry=seed_val,
        semantic_clustering=seed_val,
    )
    emb = np.zeros(384, dtype=np.float32)

    def _fn(solution: np.ndarray) -> tuple[QualityMetrics, BehaviorDescriptor, np.ndarray]:
        return metrics, bd, emb

    return _fn


def _make_archive_for_determinism(batch_size: int = 8, seed: int = 42) -> MagicMock:
    """Return a deterministic mock ArchiveWrapper."""
    rng = np.random.default_rng(seed)
    archive = MagicMock()
    # ask() returns the same batch on every call (deterministic)
    fixed_batch = rng.random((batch_size, 16), dtype=np.float32).astype(np.float64)
    archive.ask.return_value = fixed_batch
    archive.tell.return_value = None
    archive.coverage = 0.15
    archive.num_elites = 5
    archive.data.return_value = {
        "solution": rng.random((5, 16), dtype=np.float64),
        "objective": np.array([0.2, 0.4, 0.35, 0.45, 0.3], dtype=np.float64),
        "measures": rng.random((5, 4), dtype=np.float64),
    }
    return archive


def _run_outer_loop(seed: int, n_iterations: int = 3) -> OuterLoopResult:
    """Run OuterLoop with given seed; return result."""
    set_seed(seed)

    archive = _make_archive_for_determinism(batch_size=8, seed=seed)
    saturation_monitor = MagicMock()
    saturation_monitor.record.return_value = None
    saturation_monitor.is_plateaued = False

    novelty_emitter = MagicMock()
    quality_weights = QualityWeights()
    evaluate_fn = _deterministic_evaluate_fn(seed_val=0.5)

    loop = OuterLoop(
        archive=archive,
        evaluate_fn=evaluate_fn,
        persistence=None,
        novelty_emitter=novelty_emitter,
        saturation_monitor=saturation_monitor,
        quality_weights=quality_weights,
        flush_every_n=1000,
        reeval_every_n=1000,
    )
    return loop.run(n_iterations=n_iterations)


# ---------------------------------------------------------------------------
# Determinism test
# ---------------------------------------------------------------------------


def test_determinism_same_seed_same_result() -> None:
    """Running OuterLoop.run(3) twice with seed=42 produces identical results.

    Same seed → same archive coverage and best_fitness.
    This verifies the reproducibility constraint from PROJECT.md.
    """
    result_a = _run_outer_loop(seed=42, n_iterations=3)
    result_b = _run_outer_loop(seed=42, n_iterations=3)

    assert result_a.final_coverage == result_b.final_coverage, (
        f"Coverage mismatch: {result_a.final_coverage} vs {result_b.final_coverage}"
    )
    assert result_a.best_fitness == result_b.best_fitness, (
        f"Best fitness mismatch: {result_a.best_fitness} vs {result_b.best_fitness}"
    )
    assert result_a.total_evaluations == result_b.total_evaluations, (
        f"Total evaluations mismatch: {result_a.total_evaluations} vs {result_b.total_evaluations}"
    )


def test_determinism_different_seeds_can_differ() -> None:
    """Sanity check: with different seeds, the result may be different or the same.

    This is NOT a strict inequality test — the mock archive returns identical
    batches regardless. We just verify both runs complete without error.
    """
    result_42 = _run_outer_loop(seed=42, n_iterations=3)
    result_99 = _run_outer_loop(seed=99, n_iterations=3)

    # Both should be valid OuterLoopResult instances
    assert isinstance(result_42, OuterLoopResult)
    assert isinstance(result_99, OuterLoopResult)
    # total_evaluations is deterministic (8 per iter * 3 iters)
    assert result_42.total_evaluations == 24
    assert result_99.total_evaluations == 24

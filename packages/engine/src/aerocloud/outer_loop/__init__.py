"""Outer Loop package — MAP-Elites Quality-Diversity archive (Phase 9 + Phase 11).

Provides the GridArchive wrapper (ArchiveWrapper), behavioral descriptor
computation, Pydantic models, and error hierarchy for the outer optimization
loop of AeroCloud Engine.

Phase 9 exports:
    ArchiveWrapper, ArchiveConfig, QualityMetrics, QualityWeights,
    NoveltyGaussianEmitter, SaturationMonitor, OuterLoop, OuterLoopResult

Phase 11 exports:
    CappedBOPEmitter,
    CQDResult, compute_cqd, compute_cqd_from_archive,
    ParetoFront, extract_pareto_front, extract_pareto_front_from_archive,
    compute_cqd_hv, compute_cqd_hv_from_archive, pareto_slider
"""

import numpy as np

# Phase 9: Archive + Emitter + Scheduler
from aerocloud.outer_loop.archive import ArchiveWrapper
from aerocloud.outer_loop.bop_emitter import CappedBOPEmitter

# Phase 11: CQD metric
from aerocloud.outer_loop.cqd import CQDResult, compute_cqd, compute_cqd_from_archive
from aerocloud.outer_loop.emitter import NoveltyGaussianEmitter, SaturationMonitor
from aerocloud.outer_loop.models import ArchiveConfig, QualityMetrics, QualityWeights

# Phase 11: Pareto-Front + CQD_HV + Pareto-Slider
from aerocloud.outer_loop.pareto import (
    ParetoFront,
    compute_cqd_hv,
    extract_pareto_front,
    extract_pareto_front_from_archive,
    pareto_slider,
)
from aerocloud.outer_loop.scheduler import OuterLoop, OuterLoopResult

# ---------------------------------------------------------------------------
# Phase 11: compute_cqd_hv_from_archive thin wrapper
# ---------------------------------------------------------------------------


def compute_cqd_hv_from_archive(
    archive: ArchiveWrapper,
    bins_per_dim: int | None = None,
) -> float:
    """Compute CQD_HV from an ArchiveWrapper instance.

    Thin wrapper that extracts data from archive.data() and delegates to
    compute_cqd_hv(). The bins_per_dim defaults to the archive's config value
    if not provided.

    Args:
        archive:      ArchiveWrapper instance with .data() and ._config.
        bins_per_dim: Number of bins per behavioral descriptor dimension.
                      If None, reads from archive._config.bins_per_dim.

    Returns:
        CQD_HV hypervolume sum (float >= 0.0).
    """
    data = archive.data()
    objectives = np.asarray(data["objective"], dtype=np.float64)
    measures = np.asarray(data["measures"], dtype=np.float64)
    layout_coverage = np.asarray(data["layout_coverage"], dtype=np.float64)
    space_saving = np.asarray(data["space_saving"], dtype=np.float64)

    _bins = bins_per_dim if bins_per_dim is not None else archive._config.bins_per_dim

    return compute_cqd_hv(objectives, measures, layout_coverage, space_saving, _bins)


__all__ = [
    "ArchiveConfig",
    "ArchiveWrapper",
    "CQDResult",
    "CappedBOPEmitter",
    "NoveltyGaussianEmitter",
    "OuterLoop",
    "OuterLoopResult",
    "ParetoFront",
    "QualityMetrics",
    "QualityWeights",
    "SaturationMonitor",
    "compute_cqd",
    "compute_cqd_from_archive",
    "compute_cqd_hv",
    "compute_cqd_hv_from_archive",
    "extract_pareto_front",
    "extract_pareto_front_from_archive",
    "pareto_slider",
]

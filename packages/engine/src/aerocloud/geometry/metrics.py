"""Phase 4 observability wiring (D-48, D-49).

structlog bound logger + OpenTelemetry counters/histograms. Module-level
metric instruments are created once; the OTel NoOp implementation used in
Phase 1 means all records are no-ops until Phase 12 wires a real exporter.

References:
    - D-48: structlog bound context for geometry.phase / geometry.word
    - D-49: OTel counters aerocloud_geometry_sdf_cache_{hits,misses}_total,
      aerocloud_geometry_dropped_words_total{reason=...},
      histograms aerocloud_geometry_sdf_build_seconds,
      aerocloud_geometry_placement_seconds
    - .planning/phases/04-geometry-v1/04-CONTEXT.md
"""

from __future__ import annotations

from typing import Final

import structlog
from opentelemetry import metrics

logger: Final = structlog.get_logger("aerocloud.geometry")

_meter: Final = metrics.get_meter("aerocloud.geometry")

SDF_CACHE_HITS: Final = _meter.create_counter(
    "aerocloud_geometry_sdf_cache_hits_total",
    description="SDF cache hits (content-hash key matched, compute_sdf skipped)",
)
SDF_CACHE_MISSES: Final = _meter.create_counter(
    "aerocloud_geometry_sdf_cache_misses_total",
    description="SDF cache misses (compute_sdf invoked)",
)
DROPPED_WORDS: Final = _meter.create_counter(
    "aerocloud_geometry_dropped_words_total",
    description="Words dropped during placement, labelled by DropReason",
)
SDF_BUILD_SECONDS: Final = _meter.create_histogram(
    "aerocloud_geometry_sdf_build_seconds",
    description="Wall-clock seconds spent in compute_sdf",
    unit="s",
)
PLACEMENT_SECONDS: Final = _meter.create_histogram(
    "aerocloud_geometry_placement_seconds",
    description="Wall-clock seconds spent in place_words end-to-end",
    unit="s",
)

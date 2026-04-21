"""Pareto-Front extraction, CQD_HV aggregate, and Pareto-Slider function.

Purpose:
    Compute the 2D Pareto front from the 4D behavioral descriptor space
    (design fidelity vs packing density), provide the CQD_HV hypervolume
    aggregate metric (D-10), and expose a pareto_slider() function that
    returns the elite closest to any interpolated position on the Pareto front.

Mathematical definitions (Blueprint Teil IX, D-10, D-11):
    obj1 (design_fidelity)  = measures[:, 0] + measures[:, 2]
                            = shape_fidelity + symmetry
    obj2 (packing_density)  = layout_coverage + space_saving

    CQD_HV = sum_G HV(S_HV(G))   — per-cell hypervolume sum (D-10)

    Pareto-Slider:
        position=0.0 → elite with max design_fidelity
        position=1.0 → elite with max packing_density
        Intermediate → nearest Pareto point by Euclidean distance in 2D
        objective space (SC4, D-14)

Threat mitigations:
    T-11-06 (DoS): grid cell iteration is O(n_elites); pymoo HV is O(n log n)
                   per cell — negligible for typical archive sizes.
    T-11-07 (Tampering): position clipped to [0.0, 1.0] in pareto_slider();
                          empty and 1-point degenerate fronts handled.
    Pitfall 5: position out-of-range clipping in pareto_slider().
    Pitfall 6: pymoo HV uses minimization framing — negate objectives before
               calling HV(); ref_point=[0.0, 0.0] (since -F in [-∞, 0]).

References:
    - .planning/phases/11-outer-loop-v2/11-03-PLAN.md
    - D-10: CQD_HV definition
    - D-11: objective construction from measures + extra_fields
    - D-14: Pareto-Slider interface
    - SC3: strict domination in Pareto front
    - SC4: 5-position slider contract
    - SC5: HV monotonically non-decreasing
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from pydantic import ConfigDict
from pymoo.indicators.hv import HV
from pymoo.util.nds.non_dominated_sorting import NonDominatedSorting

from aerocloud.models.base import AeroCloudBase

if TYPE_CHECKING:
    from aerocloud.outer_loop.archive import ArchiveWrapper


# ---------------------------------------------------------------------------
# ParetoFront Pydantic model
# ---------------------------------------------------------------------------


class ParetoFront(AeroCloudBase):
    """Non-dominated set extracted from the archive's 2D objective space.

    Attributes:
        indices:          Integer indices into the archive data arrays
                          identifying each non-dominated (Pareto-optimal) elite.
        design_fidelity:  obj1 value per Pareto point
                          (measures[:, 0] + measures[:, 2] = shape_fidelity + symmetry).
        packing_density:  obj2 value per Pareto point
                          (layout_coverage + space_saving).
    """

    # Override AeroCloudBase.model_config to allow arbitrary types (numpy arrays
    # may appear in subclasses; plain lists are fine here).
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=False,  # allow int/float coercion in lists
        arbitrary_types_allowed=True,
    )

    indices: list[int]
    design_fidelity: list[float]
    packing_density: list[float]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_objectives(
    measures: np.ndarray,
    layout_coverage: np.ndarray,
    space_saving: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute 2D objectives from 4D measures and extra fields (D-11).

    Args:
        measures:         2D array (n, 4): [shape_fidelity, rotation_ratio, symmetry, semantic].
        layout_coverage:  1D array (n,).
        space_saving:     1D array (n,).

    Returns:
        (obj1, obj2) where:
            obj1 = measures[:, 0] + measures[:, 2]  (design_fidelity)
            obj2 = layout_coverage + space_saving     (packing_density)
    """
    obj1: np.ndarray = measures[:, 0] + measures[:, 2]
    obj2: np.ndarray = layout_coverage + space_saving
    return obj1, obj2


def _cell_id(measure_row: np.ndarray, bins_per_dim: int) -> tuple[int, ...]:
    """Map a 4D measure vector to a discrete grid cell identifier.

    Uses floor(measure * bins_per_dim) clipped to [0, bins_per_dim - 1].

    Args:
        measure_row: 1D array of shape (4,) with values in [0, 1].
        bins_per_dim: Number of bins per behavioral descriptor dimension.

    Returns:
        Tuple of 4 ints identifying the grid cell.
    """
    bins = np.minimum(
        np.floor(measure_row * bins_per_dim).astype(int),
        bins_per_dim - 1,
    )
    return tuple(int(b) for b in bins)


def _hv_single_cell(f_cell: np.ndarray) -> float:
    """Compute hypervolume for a single grid cell (Pitfall 6 compliant).

    Args:
        f_cell: 2D array (n, 2) of [design_fidelity, packing_density] values.
                Values may exceed [0, 1] because design_fidelity = m0 + m2 ∈ [0, 2].

    Returns:
        Hypervolume (float). 0.0 if the cell has no elites.
    """
    if len(f_cell) == 0:
        return 0.0
    # Pitfall 6: pymoo HV is a minimizer; negate objectives so that higher is
    # better maps to the standard minimization problem.
    # ref_point=[0, 0] because -F ∈ (-∞, 0] after negation, so [0, 0] is
    # dominated by all negated points (as required by pymoo).
    ref_point = np.array([0.0, 0.0])
    return float(HV(ref_point=ref_point).do(-f_cell))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_pareto_front(
    objectives: np.ndarray,
    measures: np.ndarray,
    layout_coverage: np.ndarray,
    space_saving: np.ndarray,
) -> ParetoFront:
    """Extract the non-dominated Pareto front from archive elites.

    Operates on the 2D objective space (design_fidelity, packing_density)
    derived from the 4D behavioral descriptor measures and extra_fields.

    Algorithm:
        1. Compute obj1 = measures[:, 0] + measures[:, 2] (design_fidelity)
        2. Compute obj2 = layout_coverage + space_saving   (packing_density)
        3. Stack into F = (n, 2); negate for pymoo minimization (F_neg = -F)
        4. Apply NonDominatedSorting; take front[0] (non-dominated set)

    Args:
        objectives:       1D array (n,) of archive fitness values (not used for
                          Pareto computation, but kept for API consistency).
        measures:         2D array (n, 4) of behavioral descriptor values.
        layout_coverage:  1D array (n,) of layout coverage extra_field values.
        space_saving:     1D array (n,) of space saving extra_field values.

    Returns:
        ParetoFront with indices, design_fidelity, and packing_density for
        the non-dominated set.
    """
    n = len(objectives)

    if n == 0:
        return ParetoFront(indices=[], design_fidelity=[], packing_density=[])

    obj1, obj2 = _compute_objectives(measures, layout_coverage, space_saving)

    # Stack into (n, 2) objective matrix
    f_mat = np.column_stack([obj1, obj2])  # shape (n, 2)

    # Negate for pymoo minimization framing (Pitfall 6)
    f_neg = -f_mat

    # Non-dominated sorting — fronts[0] is the Pareto-optimal front
    fronts = NonDominatedSorting().do(f_neg)
    pareto_indices: np.ndarray = fronts[0]

    return ParetoFront(
        indices=pareto_indices.tolist(),
        design_fidelity=obj1[pareto_indices].tolist(),
        packing_density=obj2[pareto_indices].tolist(),
    )


def compute_cqd_hv(
    objectives: np.ndarray,
    measures: np.ndarray,
    layout_coverage: np.ndarray,
    space_saving: np.ndarray,
    bins_per_dim: int,
) -> float:
    """Compute CQD_HV — sum of per-cell hypervolumes (Blueprint Teil IX, D-10).

    For each occupied grid cell G:
        1. Collect all elites in G
        2. Compute their 2D objectives (design_fidelity, packing_density)
        3. Compute HV with ref_point=[0, 0] (negated for pymoo minimization)
        4. Accumulate

    T-11-06 (DoS): cell iteration is O(n_elites) — bounded by archive capacity.

    Args:
        objectives:       1D array (n,) of archive fitness values (not used directly).
        measures:         2D array (n, 4) of behavioral descriptor values.
        layout_coverage:  1D array (n,) of layout coverage extra_field values.
        space_saving:     1D array (n,) of space saving extra_field values.
        bins_per_dim:     Number of bins per behavioral descriptor dimension.
                          Must match the GridArchive configuration.

    Returns:
        Sum of per-cell hypervolumes. 0.0 if the archive is empty.
    """
    n = len(objectives)
    if n == 0:
        return 0.0

    obj1, obj2 = _compute_objectives(measures, layout_coverage, space_saving)

    # Group elite indices by cell ID
    cell_map: dict[tuple[int, ...], list[int]] = {}
    for i in range(n):
        cid = _cell_id(measures[i], bins_per_dim)
        if cid not in cell_map:
            cell_map[cid] = []
        cell_map[cid].append(i)

    total_hv: float = 0.0
    for cell_indices in cell_map.values():
        idx = np.array(cell_indices)
        f_cell = np.column_stack([obj1[idx], obj2[idx]])
        total_hv += _hv_single_cell(f_cell)

    return total_hv


def pareto_slider(
    pareto_front: ParetoFront,
    position: float,
    archive_data: dict[str, Any],
) -> dict[str, Any]:
    """Return the archive elite closest to a position on the Pareto front.

    The slider interpolates from the elite with the highest design_fidelity
    (position=0.0) to the elite with the highest packing_density (position=1.0).

    Algorithm:
        1. Clip position to [0.0, 1.0] (T-11-07, Pitfall 5)
        2. If len(pareto_front.indices) == 0: raise ValueError
        3. If len(pareto_front.indices) == 1: return that elite directly
        4. Sort Pareto front by design_fidelity descending
        5. Interpolate target objectives between extremes
        6. Find nearest Pareto point by Euclidean distance in 2D objective space
        7. Return archive entry at the found index

    Args:
        pareto_front:   ParetoFront from extract_pareto_front().
        position:       Float in [0.0, 1.0]. Values outside are clipped.
                        0.0 = max design_fidelity, 1.0 = max packing_density.
        archive_data:   Dict from ArchiveWrapper.data() containing array fields
                        keyed by 'solution', 'objective', 'measures', etc.
                        Each value at index i corresponds to the i-th elite.

    Returns:
        Dict slice of archive_data at the nearest Pareto point index.
        Keys match ArchiveWrapper.data() output.

    Raises:
        ValueError: If pareto_front.indices is empty.
    """
    # T-11-07: clip position to [0.0, 1.0]
    clipped_pos: float = float(np.clip(position, 0.0, 1.0))

    indices = pareto_front.indices
    design_fidelity = pareto_front.design_fidelity
    packing_density = pareto_front.packing_density

    if len(indices) == 0:
        raise ValueError("pareto_slider: empty pareto_front — cannot select elite")

    if len(indices) == 1:
        idx = indices[0]
        return {k: v[idx] for k, v in archive_data.items()}

    # Sort Pareto front by design_fidelity descending
    df_arr = np.array(design_fidelity)
    pd_arr = np.array(packing_density)
    sort_order = np.argsort(-df_arr)  # descending
    df_sorted = df_arr[sort_order]
    pd_sorted = pd_arr[sort_order]
    indices_sorted = [indices[i] for i in sort_order]

    # Interpolate target point between extremes
    max_df = float(df_sorted[0])
    min_df = float(df_sorted[-1])
    min_pd = float(pd_sorted[0])  # pd at max df position (min pd)
    max_pd = float(pd_sorted[-1])  # pd at min df position (max pd)

    target_df = max_df * (1.0 - clipped_pos) + min_df * clipped_pos
    target_pd = min_pd * (1.0 - clipped_pos) + max_pd * clipped_pos
    target = np.array([target_df, target_pd])

    # Find nearest Pareto point by Euclidean distance in 2D objective space
    pareto_points = np.column_stack([df_sorted, pd_sorted])
    dists = np.linalg.norm(pareto_points - target, axis=1)
    nearest = int(np.argmin(dists))
    best_archive_idx = indices_sorted[nearest]

    return {k: v[best_archive_idx] for k, v in archive_data.items()}


# ---------------------------------------------------------------------------
# Thin wrapper for ArchiveWrapper
# ---------------------------------------------------------------------------


def extract_pareto_front_from_archive(archive: ArchiveWrapper) -> ParetoFront:
    """Extract Pareto front from an ArchiveWrapper instance.

    Thin wrapper that calls archive.data() and delegates to the pure
    extract_pareto_front() function.

    Args:
        archive: ArchiveWrapper instance with .data() method returning
                 a dict with 'objective', 'measures', 'layout_coverage',
                 'space_saving' arrays.

    Returns:
        ParetoFront from extract_pareto_front().
    """
    data = archive.data()
    objectives = np.asarray(data["objective"], dtype=np.float64)
    measures = np.asarray(data["measures"], dtype=np.float64)
    layout_coverage = np.asarray(data["layout_coverage"], dtype=np.float64)
    space_saving = np.asarray(data["space_saving"], dtype=np.float64)

    return extract_pareto_front(objectives, measures, layout_coverage, space_saving)

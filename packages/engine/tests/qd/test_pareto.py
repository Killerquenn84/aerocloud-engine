"""Tests for pareto.py — Pareto-Front extraction, CQD_HV, and Pareto-Slider.

BDD scenarios (D-14, SC3, SC4, SC5):

Given a MAP-Elites archive with 4 objectives and 2D behavioral space
When extract_pareto_front() is called
Then it returns the correct non-dominated set

Given a multi-cell archive
When compute_cqd_hv() is called
Then it returns the sum of per-cell hypervolumes (D-10)

Given a Pareto front
When pareto_slider() is called at positions [0.0, 0.25, 0.5, 0.75, 1.0]
Then it returns the nearest elite on the front (SC4, D-14)

References:
    - .planning/phases/11-outer-loop-v2/11-03-PLAN.md
    - D-10: CQD_HV = sum_G HV(S_HV(G))
    - D-11: obj1 = shape_fidelity + symmetry; obj2 = layout_coverage + space_saving
    - D-14: Pareto-Slider: position 0.0 = max design_fidelity, 1.0 = max packing_density
    - SC3: Pareto front has no dominance ties (strict domination)
    - SC4: pareto_slider returns valid elites at 5 positions
    - SC5: HV monotonically non-decreasing as elites are added
    - T-11-06: Cap grid cell iteration (DoS)
    - T-11-07: Clip position to [0.0, 1.0] (Tampering)
    - Pitfall 5: position out-of-range clipping
    - Pitfall 6: pymoo HV ref_point for maximization — negate objectives
"""

from __future__ import annotations

import pytest
import numpy as np


# ---------------------------------------------------------------------------
# Helpers — build test data
# ---------------------------------------------------------------------------


def _make_4elite_data() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """4-elite archive with known 2-point Pareto front.

    Objectives (design_fidelity = m0+m2, packing_density = lc+ss):
        elite 0: df=0.8, pd=0.3  → Pareto point
        elite 1: df=0.4, pd=0.9  → Pareto point
        elite 2: df=0.3, pd=0.3  → dominated by elite 1 (0.4>0.3, 0.9>0.3)
        elite 3: df=0.5, pd=0.2  → dominated by elite 0 (0.8>0.5, 0.3>0.2)

    Returns (objectives, measures, layout_coverage, space_saving).
    """
    objectives = np.array([0.5, 0.9, 0.3, 0.2])  # archive fitness (not used by pareto)
    measures = np.array([
        [0.5, 0.0, 0.3, 0.0],  # elite 0: shape_fidelity=0.5, symmetry=0.3 -> df=0.8
        [0.2, 0.0, 0.2, 0.0],  # elite 1: shape_fidelity=0.2, symmetry=0.2 -> df=0.4
        [0.1, 0.0, 0.2, 0.0],  # elite 2: shape_fidelity=0.1, symmetry=0.2 -> df=0.3
        [0.2, 0.0, 0.3, 0.0],  # elite 3: shape_fidelity=0.2, symmetry=0.3 -> df=0.5
    ])
    layout_coverage = np.array([0.3, 0.9, 0.3, 0.2])
    space_saving = np.zeros(4)
    return objectives, measures, layout_coverage, space_saving


def _make_single_dominated_data() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """All elites dominated by one.

    elite 0: df=0.9, pd=0.9  → Pareto point (dominates all others)
    elite 1: df=0.5, pd=0.5  → dominated
    elite 2: df=0.3, pd=0.7  → dominated
    """
    objectives = np.array([0.9, 0.5, 0.3])
    measures = np.array([
        [0.5, 0.0, 0.4, 0.0],  # df=0.9
        [0.2, 0.0, 0.3, 0.0],  # df=0.5
        [0.1, 0.0, 0.2, 0.0],  # df=0.3
    ])
    layout_coverage = np.array([0.9, 0.5, 0.7])
    space_saving = np.zeros(3)
    return objectives, measures, layout_coverage, space_saving


def _make_3cell_data() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """3-cell archive with 2 elites each, for hand-calculated CQD_HV.

    Cell assignment: bins_per_dim=2, bin = floor(measure * 2) clipped to [0, 1].
    Cells:
        A (0,0,0,0): elites 0,1 — measures all < 0.5
        B (1,1,1,1): elites 2,3 — measures all >= 0.5
        C (0,1,0,1): elites 4,5 — measures [<0.5, >=0.5, <0.5, >=0.5]

    Objectives (D-11):
        Elite 0: df = m0+m2 = 0.1+0.1 = 0.2,  pd = lc+ss = 0.3+0 = 0.3
        Elite 1: df = 0.2+0.2 = 0.4,          pd = 0.2+0 = 0.2
        Elite 2: df = 0.9+0.9 = 1.8,          pd = 0.9+0 = 0.9
        Elite 3: df = 0.8+0.8 = 1.6,          pd = 0.7+0 = 0.7
        Elite 4: df = 0.1+0.1 = 0.2,          pd = 0.5+0 = 0.5
        Elite 5: df = 0.2+0.2 = 0.4,          pd = 0.4+0 = 0.4

    Hand-calculated HV per cell (ref_point=[0,0], negated F for pymoo):
        HV(Cell A) = 0.10  (computed via pymoo)
        HV(Cell B) = 1.62  (computed via pymoo)
        HV(Cell C) = 0.18  (computed via pymoo)
        Total = 1.90
    """
    objectives = np.zeros(6)
    measures = np.array([
        [0.1, 0.1, 0.1, 0.1],  # elite 0 — Cell A
        [0.2, 0.2, 0.2, 0.2],  # elite 1 — Cell A
        [0.9, 0.9, 0.9, 0.9],  # elite 2 — Cell B
        [0.8, 0.8, 0.8, 0.8],  # elite 3 — Cell B
        [0.1, 0.9, 0.1, 0.9],  # elite 4 — Cell C
        [0.2, 0.8, 0.2, 0.8],  # elite 5 — Cell C
    ])
    layout_coverage = np.array([0.3, 0.2, 0.9, 0.7, 0.5, 0.4])
    space_saving = np.zeros(6)
    return objectives, measures, layout_coverage, space_saving


# ---------------------------------------------------------------------------
# extract_pareto_front() tests
# ---------------------------------------------------------------------------


class TestExtractParetoFront:
    """Test 1–4: extract_pareto_front() behavior."""

    def test_four_elites_two_point_pareto_front(self) -> None:
        """Test 1: 4 elites with known objectives -> correct 2-point Pareto front."""
        from aerocloud.outer_loop.pareto import extract_pareto_front

        objectives, measures, layout_coverage, space_saving = _make_4elite_data()
        pf = extract_pareto_front(objectives, measures, layout_coverage, space_saving)

        assert len(pf.indices) == 2, f"Expected 2 Pareto points, got {len(pf.indices)}"
        assert set(pf.indices) == {0, 1}, f"Expected indices {{0,1}}, got {set(pf.indices)}"

    def test_four_elites_pareto_front_objectives(self) -> None:
        """Test 1b: Pareto front objectives match expected values."""
        from aerocloud.outer_loop.pareto import extract_pareto_front

        objectives, measures, layout_coverage, space_saving = _make_4elite_data()
        pf = extract_pareto_front(objectives, measures, layout_coverage, space_saving)

        # Sort by index for deterministic comparison
        paired = sorted(zip(pf.indices, pf.design_fidelity, pf.packing_density))
        idx0, df0, pd0 = paired[0]
        idx1, df1, pd1 = paired[1]

        assert idx0 == 0
        assert abs(df0 - 0.8) < 1e-9, f"Expected df=0.8, got {df0}"
        assert abs(pd0 - 0.3) < 1e-9, f"Expected pd=0.3, got {pd0}"

        assert idx1 == 1
        assert abs(df1 - 0.4) < 1e-9, f"Expected df=0.4, got {df1}"
        assert abs(pd1 - 0.9) < 1e-9, f"Expected pd=0.9, got {pd1}"

    def test_single_dominant_elite_gives_one_point_pareto_front(self) -> None:
        """Test 2: All elites dominated by one -> single-point Pareto front."""
        from aerocloud.outer_loop.pareto import extract_pareto_front

        objectives, measures, layout_coverage, space_saving = _make_single_dominated_data()
        pf = extract_pareto_front(objectives, measures, layout_coverage, space_saving)

        assert len(pf.indices) == 1, f"Expected 1 Pareto point, got {len(pf.indices)}"
        assert pf.indices[0] == 0, f"Expected index 0 (dominant), got {pf.indices[0]}"

    def test_empty_archive_gives_empty_pareto_front(self) -> None:
        """Test 3: Empty archive -> ParetoFront with empty indices."""
        from aerocloud.outer_loop.pareto import extract_pareto_front

        objectives = np.empty(0)
        measures = np.empty((0, 4))
        layout_coverage = np.empty(0)
        space_saving = np.empty(0)

        pf = extract_pareto_front(objectives, measures, layout_coverage, space_saving)

        assert pf.indices == [], f"Expected empty indices, got {pf.indices}"
        assert pf.design_fidelity == [], f"Expected empty design_fidelity"
        assert pf.packing_density == [], f"Expected empty packing_density"

    def test_pareto_front_no_dominated_points(self) -> None:
        """Test 4: SC3 — Pareto front has no dominated points.

        For every pair (i, j) in the front: neither i dominates j nor j dominates i.
        """
        from aerocloud.outer_loop.pareto import extract_pareto_front

        # 6 elites — only 2 should be Pareto-optimal
        objectives = np.zeros(6)
        measures = np.array([
            [0.5, 0.0, 0.3, 0.0],  # df=0.8
            [0.2, 0.0, 0.2, 0.0],  # df=0.4
            [0.1, 0.0, 0.2, 0.0],  # df=0.3
            [0.2, 0.0, 0.3, 0.0],  # df=0.5
            [0.0, 0.0, 0.1, 0.0],  # df=0.1
            [0.1, 0.0, 0.1, 0.0],  # df=0.2
        ])
        layout_coverage = np.array([0.3, 0.9, 0.3, 0.2, 0.1, 0.1])
        space_saving = np.zeros(6)

        pf = extract_pareto_front(objectives, measures, layout_coverage, space_saving)

        # Build 2D objective arrays for Pareto-front members
        obj1 = measures[:, 0] + measures[:, 2]
        obj2 = layout_coverage + space_saving
        pareto_df = np.array([obj1[i] for i in pf.indices])
        pareto_pd = np.array([obj2[i] for i in pf.indices])

        # Check no pair has one dominating the other
        n = len(pf.indices)
        for a in range(n):
            for b in range(n):
                if a == b:
                    continue
                # a dominates b if a.df >= b.df AND a.pd >= b.pd (and at least one strict)
                a_dom_b = (
                    pareto_df[a] >= pareto_pd[b]
                    and pareto_pd[a] >= pareto_pd[b]
                    and (pareto_df[a] > pareto_df[b] or pareto_pd[a] > pareto_pd[b])
                )
                assert not a_dom_b, (
                    f"Pareto point {pf.indices[a]} dominates {pf.indices[b]} — "
                    "front not clean"
                )


# ---------------------------------------------------------------------------
# compute_cqd_hv() tests
# ---------------------------------------------------------------------------


class TestComputeCqdHv:
    """Test 5–7: compute_cqd_hv() behavior."""

    def test_three_cell_archive_hand_calculated_hv(self) -> None:
        """Test 5: Known 3-cell archive with 2 elites each -> hand-calculated HV sum.

        Hand-calculated expected values (D-10, pymoo HV with ref_point=[0,0]):
            HV(Cell A) = 0.10
            HV(Cell B) = 1.62
            HV(Cell C) = 0.18
            Total = 1.90
        """
        from aerocloud.outer_loop.pareto import compute_cqd_hv

        objectives, measures, layout_coverage, space_saving = _make_3cell_data()
        result = compute_cqd_hv(objectives, measures, layout_coverage, space_saving, bins_per_dim=2)

        assert abs(result - 1.90) < 1e-6, f"Expected ~1.90, got {result}"

    def test_empty_archive_gives_zero_cqd_hv(self) -> None:
        """Test 6: Empty archive -> CQD_HV = 0.0."""
        from aerocloud.outer_loop.pareto import compute_cqd_hv

        objectives = np.empty(0)
        measures = np.empty((0, 4))
        layout_coverage = np.empty(0)
        space_saving = np.empty(0)

        result = compute_cqd_hv(objectives, measures, layout_coverage, space_saving, bins_per_dim=4)

        assert result == 0.0, f"Expected 0.0 for empty archive, got {result}"

    def test_hv_monotonically_non_decreasing_when_adding_non_dominated_elite(self) -> None:
        """Test 7: SC5 — HV non-decreasing as non-dominated elites are added.

        Start with 1 elite (HV = area of bounding box from ref_point).
        Add a non-dominated elite → HV must be >= HV of single elite.
        """
        from aerocloud.outer_loop.pareto import compute_cqd_hv

        # Single elite in one cell
        measures_1 = np.array([[0.5, 0.0, 0.3, 0.0]])
        lc_1 = np.array([0.3])
        ss_1 = np.zeros(1)
        objs_1 = np.zeros(1)
        hv1 = compute_cqd_hv(objs_1, measures_1, lc_1, ss_1, bins_per_dim=2)

        # Add a non-dominated elite in the same cell
        measures_2 = np.array([
            [0.5, 0.0, 0.3, 0.0],  # df=0.8, pd=0.3
            [0.2, 0.0, 0.2, 0.0],  # df=0.4, pd=0.9 — non-dominated
        ])
        lc_2 = np.array([0.3, 0.9])
        ss_2 = np.zeros(2)
        objs_2 = np.zeros(2)
        hv2 = compute_cqd_hv(objs_2, measures_2, lc_2, ss_2, bins_per_dim=2)

        assert hv2 >= hv1, f"HV should be >= after adding non-dominated elite: hv1={hv1}, hv2={hv2}"


# ---------------------------------------------------------------------------
# pareto_slider() tests
# ---------------------------------------------------------------------------


def _make_two_point_pareto_front() -> object:
    """Make a 2-point ParetoFront for slider tests.

    Pareto points:
        index=0: df=0.8, pd=0.3  (max design fidelity)
        index=1: df=0.4, pd=0.9  (max packing density)
    """
    from aerocloud.outer_loop.pareto import ParetoFront
    return ParetoFront(
        indices=[0, 1],
        design_fidelity=[0.8, 0.4],
        packing_density=[0.3, 0.9],
    )


def _make_archive_data() -> dict:  # type: ignore[type-arg]
    """Mock archive data dict matching ArchiveWrapper.data() output."""
    return {
        "solution": np.zeros((2, 8)),
        "objective": np.array([0.5, 0.9]),
        "measures": np.array([
            [0.5, 0.0, 0.3, 0.0],
            [0.2, 0.0, 0.2, 0.0],
        ]),
        "layout_coverage": np.array([0.3, 0.9]),
        "space_saving": np.zeros(2),
    }


class TestParetoSlider:
    """Test 8–12: pareto_slider() behavior."""

    def test_position_zero_returns_max_design_fidelity_elite(self) -> None:
        """Test 8: position=0.0 returns elite with max design_fidelity."""
        from aerocloud.outer_loop.pareto import pareto_slider

        pf = _make_two_point_pareto_front()
        archive_data = _make_archive_data()
        result = pareto_slider(pf, 0.0, archive_data)  # type: ignore[arg-type]

        # Max design_fidelity is index 0 (df=0.8)
        assert result["objective"] == pytest.approx(0.5), (
            f"Expected elite 0 (fitness=0.5), got objective={result['objective']}"
        )

    def test_position_one_returns_max_packing_density_elite(self) -> None:
        """Test 9: position=1.0 returns elite with max packing_density."""
        from aerocloud.outer_loop.pareto import pareto_slider

        pf = _make_two_point_pareto_front()
        archive_data = _make_archive_data()
        result = pareto_slider(pf, 1.0, archive_data)  # type: ignore[arg-type]

        # Max packing_density is index 1 (pd=0.9)
        assert result["objective"] == pytest.approx(0.9), (
            f"Expected elite 1 (fitness=0.9), got objective={result['objective']}"
        )

    def test_five_positions_all_return_valid_elites(self) -> None:
        """Test 10: SC4 — positions 0.0, 0.25, 0.5, 0.75, 1.0 all return valid elites."""
        from aerocloud.outer_loop.pareto import pareto_slider

        pf = _make_two_point_pareto_front()
        archive_data = _make_archive_data()

        for position in [0.0, 0.25, 0.5, 0.75, 1.0]:
            result = pareto_slider(pf, position, archive_data)  # type: ignore[arg-type]
            assert isinstance(result, dict), f"Expected dict at position {position}"
            assert "objective" in result, f"Dict missing 'objective' key at position {position}"
            assert "measures" in result, f"Dict missing 'measures' key at position {position}"

    def test_single_point_front_all_positions_return_same_elite(self) -> None:
        """Test 11: 1-point Pareto front -> all positions return the same elite."""
        from aerocloud.outer_loop.pareto import ParetoFront, pareto_slider

        pf = ParetoFront(
            indices=[0],
            design_fidelity=[0.8],
            packing_density=[0.3],
        )
        archive_data = {
            "solution": np.zeros((3, 8)),
            "objective": np.array([0.5, 0.9, 0.3]),
            "measures": np.array([
                [0.5, 0.0, 0.3, 0.0],
                [0.2, 0.0, 0.2, 0.0],
                [0.1, 0.0, 0.1, 0.0],
            ]),
            "layout_coverage": np.array([0.3, 0.9, 0.1]),
            "space_saving": np.zeros(3),
        }

        results = [
            pareto_slider(pf, pos, archive_data)  # type: ignore[arg-type]
            for pos in [0.0, 0.25, 0.5, 0.75, 1.0]
        ]

        # All should return the same single elite (index 0)
        for i, result in enumerate(results):
            assert result["objective"] == pytest.approx(0.5), (
                f"Position {i}: expected elite 0, got objective={result['objective']}"
            )

    def test_position_outside_range_is_clipped(self) -> None:
        """Test 12: Pitfall 5 / T-11-07 — position outside [0,1] is clipped.

        Positions -0.5 and 1.5 should behave identically to 0.0 and 1.0.
        """
        from aerocloud.outer_loop.pareto import pareto_slider

        pf = _make_two_point_pareto_front()
        archive_data = _make_archive_data()

        # -0.5 should be clipped to 0.0 -> max design_fidelity (elite 0)
        result_neg = pareto_slider(pf, -0.5, archive_data)  # type: ignore[arg-type]
        result_zero = pareto_slider(pf, 0.0, archive_data)  # type: ignore[arg-type]
        assert result_neg["objective"] == result_zero["objective"], (
            f"position=-0.5 should behave like 0.0"
        )

        # 1.5 should be clipped to 1.0 -> max packing_density (elite 1)
        result_over = pareto_slider(pf, 1.5, archive_data)  # type: ignore[arg-type]
        result_one = pareto_slider(pf, 1.0, archive_data)  # type: ignore[arg-type]
        assert result_over["objective"] == result_one["objective"], (
            f"position=1.5 should behave like 1.0"
        )

    def test_empty_pareto_front_raises_value_error(self) -> None:
        """Test 12b: Empty Pareto front raises ValueError."""
        from aerocloud.outer_loop.pareto import ParetoFront, pareto_slider

        pf = ParetoFront(indices=[], design_fidelity=[], packing_density=[])
        archive_data = _make_archive_data()

        with pytest.raises(ValueError, match="empty"):
            pareto_slider(pf, 0.5, archive_data)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# extract_pareto_front_from_archive() wrapper test
# ---------------------------------------------------------------------------


class TestExtractParetoFrontFromArchive:
    """Thin-wrapper integration test."""

    def test_extract_from_archive_wrapper_matches_raw(self) -> None:
        """extract_pareto_front_from_archive() results match extract_pareto_front()."""
        from unittest.mock import MagicMock
        from aerocloud.outer_loop.pareto import (
            extract_pareto_front,
            extract_pareto_front_from_archive,
        )

        objectives, measures, layout_coverage, space_saving = _make_4elite_data()

        # Mock ArchiveWrapper.data()
        mock_archive = MagicMock()
        mock_archive.data.return_value = {
            "solution": np.zeros((4, 8)),
            "objective": objectives,
            "measures": measures,
            "layout_coverage": layout_coverage,
            "space_saving": space_saving,
        }

        pf_raw = extract_pareto_front(objectives, measures, layout_coverage, space_saving)
        pf_wrapped = extract_pareto_front_from_archive(mock_archive)

        assert set(pf_raw.indices) == set(pf_wrapped.indices), (
            f"Raw vs wrapper mismatch: {pf_raw.indices} vs {pf_wrapped.indices}"
        )

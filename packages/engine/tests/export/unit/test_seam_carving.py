"""Unit tests for seam carving export module (PROD-01, PROD-02).

BDD Scenarios:
    Given a canvas with word positions and weights,
    When build_energy_map is called,
    Then the energy map has Gaussian peaks at word positions.

    Given an energy map,
    When find_vertical_seam is called,
    Then the seam is a valid column-index array respecting adjacency constraints.

    Given an image and a seam,
    When remove_vertical_seam is called,
    Then the image width shrinks by exactly 1 column.
"""

import numpy as np
import pytest

from aerocloud.export.seam_carving import (
    build_energy_map,
    find_vertical_seam,
    remove_vertical_seam,
)


class TestBuildEnergyMap:
    """Tests for build_energy_map() — PROD-01."""

    def test_output_shape(self) -> None:
        """Energy map must have exactly (canvas_h, canvas_w) shape."""
        energy = build_energy_map(100, 100, [(50, 50)], [1.0])
        assert energy.shape == (100, 100)

    def test_output_dtype(self) -> None:
        """Energy map must be float64."""
        energy = build_energy_map(100, 100, [(50, 50)], [1.0])
        assert energy.dtype == np.float64

    def test_peak_near_word_position(self) -> None:
        """Peak of energy map must be near the word position (50, 50)."""
        energy = build_energy_map(100, 100, [(50, 50)], [1.0], sigma=15.0)
        peak_idx = np.unravel_index(np.argmax(energy), energy.shape)
        # Peak row and column should be within 5 pixels of word position
        assert abs(peak_idx[0] - 50) <= 5
        assert abs(peak_idx[1] - 50) <= 5

    def test_energy_strictly_positive_where_words_exist(self) -> None:
        """Energy values must be strictly positive throughout (Gaussian is never zero)."""
        energy = build_energy_map(100, 100, [(50, 50)], [1.0], sigma=15.0)
        assert np.all(energy > 0)

    def test_multiple_word_positions(self) -> None:
        """With two words, there should be two peaks in the energy map."""
        energy = build_energy_map(100, 200, [(10, 10), (80, 180)], [1.0, 1.0], sigma=5.0)
        assert energy.shape == (100, 200)
        # Both regions should have significant energy
        assert energy[10, 10] > energy[50, 100]  # peak near word 1
        assert energy[80, 180] > energy[50, 100]  # peak near word 2

    def test_weight_scales_energy(self) -> None:
        """Higher word weight produces proportionally higher energy at word position."""
        energy_low = build_energy_map(50, 50, [(25, 25)], [1.0], sigma=5.0)
        energy_high = build_energy_map(50, 50, [(25, 25)], [2.0], sigma=5.0)
        assert energy_high[25, 25] > energy_low[25, 25]

    def test_canvas_size_rejection_oversized(self) -> None:
        """Canvas dimensions exceeding 4096 must be rejected (T-12-01-01 DoS mitigation)."""
        with pytest.raises(ValueError, match="canvas"):
            build_energy_map(4097, 100, [(50, 50)], [1.0])
        with pytest.raises(ValueError, match="canvas"):
            build_energy_map(100, 4097, [(50, 50)], [1.0])

    def test_empty_word_list(self) -> None:
        """Empty word list produces a zero energy map (no words, no energy)."""
        energy = build_energy_map(50, 50, [], [], sigma=5.0)
        assert energy.shape == (50, 50)
        assert np.all(energy == 0.0)


class TestFindVerticalSeam:
    """Tests for find_vertical_seam() — PROD-02."""

    def test_seam_length_equals_canvas_height(self) -> None:
        """Seam array length must equal canvas height."""
        energy = np.ones((50, 60), dtype=np.float64)
        seam = find_vertical_seam(energy)
        assert len(seam) == 50

    def test_seam_dtype_is_int32(self) -> None:
        """Seam must be int32 array."""
        energy = np.ones((30, 40), dtype=np.float64)
        seam = find_vertical_seam(energy)
        assert seam.dtype == np.int32

    def test_seam_values_within_bounds(self) -> None:
        """All seam column indices must be in [0, width-1]."""
        energy = np.random.default_rng(42).random((40, 50))
        seam = find_vertical_seam(energy)
        assert np.all(seam >= 0)
        assert np.all(seam <= 49)

    def test_adjacent_rows_differ_by_at_most_one(self) -> None:
        """Consecutive seam entries must differ by at most 1 (adjacency constraint)."""
        rng = np.random.default_rng(42)
        energy = rng.random((60, 80))
        seam = find_vertical_seam(energy)
        diffs = np.abs(np.diff(seam.astype(np.int64)))
        assert np.all(diffs <= 1)

    def test_uniform_energy_returns_valid_seam(self) -> None:
        """On uniform energy, any valid seam is acceptable — just check constraints."""
        energy = np.ones((20, 30), dtype=np.float64)
        seam = find_vertical_seam(energy)
        assert len(seam) == 20
        assert np.all(seam >= 0)
        assert np.all(seam <= 29)
        diffs = np.abs(np.diff(seam.astype(np.int64)))
        assert np.all(diffs <= 1)

    def test_low_cost_column_seam(self) -> None:
        """Seam should concentrate in the low-cost column."""
        energy = np.ones((20, 10), dtype=np.float64) * 10.0
        # Column 5 has near-zero cost — seam must pass through it
        energy[:, 5] = 0.001
        seam = find_vertical_seam(energy)
        # Most seam entries should be in column 5 (allowing ±1 for adjacency)
        near_five = np.sum((seam >= 4) & (seam <= 6))
        assert near_five >= 15  # at least 75% of rows


class TestRemoveVerticalSeam:
    """Tests for remove_vertical_seam() — PROD-02."""

    def test_2d_image_shrinks_width_by_one(self) -> None:
        """Removing seam from (10, 10) 2D image returns (10, 9) image."""
        image = np.arange(100, dtype=np.float64).reshape(10, 10)
        seam = np.zeros(10, dtype=np.int32)  # remove column 0
        result = remove_vertical_seam(image, seam)
        assert result.shape == (10, 9)

    def test_3d_image_shrinks_width_by_one(self) -> None:
        """Removing seam from (10, 10, 3) 3D image returns (10, 9, 3) image."""
        image = np.ones((10, 10, 3), dtype=np.uint8)
        seam = np.zeros(10, dtype=np.int32)
        result = remove_vertical_seam(image, seam)
        assert result.shape == (10, 9, 3)

    def test_correct_column_removed(self) -> None:
        """Pixel identity check: the seam column is removed, others kept."""
        # Create image where each pixel = its column index
        image = np.tile(np.arange(10, dtype=np.float64), (5, 1))  # shape (5, 10)
        seam = np.full(5, fill_value=3, dtype=np.int32)  # remove column 3
        result = remove_vertical_seam(image, seam)
        # After removing column 3, remaining columns: 0,1,2,4,5,6,7,8,9
        expected_row = [0.0, 1.0, 2.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
        for row_idx in range(5):
            np.testing.assert_array_equal(result[row_idx], expected_row)

    def test_varying_seam_removal(self) -> None:
        """Test removal with a seam that varies across rows."""
        # 3 rows, 5 columns. Remove col 0 from row 0, col 2 from row 1, col 4 from row 2.
        image = np.tile(np.arange(5, dtype=np.float64), (3, 1))
        seam = np.array([0, 2, 4], dtype=np.int32)
        result = remove_vertical_seam(image, seam)
        assert result.shape == (3, 4)
        np.testing.assert_array_equal(result[0], [1.0, 2.0, 3.0, 4.0])
        np.testing.assert_array_equal(result[1], [0.0, 1.0, 3.0, 4.0])
        np.testing.assert_array_equal(result[2], [0.0, 1.0, 2.0, 3.0])

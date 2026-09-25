"""Tests for outer_loop.descriptors — compute_descriptors() function.

TDD RED phase.

Behavioral:
    - Test 7: compute_descriptors returns BehaviorDescriptor with all fields in [0.0, 1.0]
    - Test 8: shape_fidelity = lc_metric value (per RESEARCH BD computation table)
    - Test 9: rotation_ratio = fraction of words with |theta| > pi/4
    - Test 10: descriptors are clamped to [0.0, 1.0] (Pitfall 5)
"""

from __future__ import annotations

import math

import numpy as np
import pytest
import torch

from aerocloud.models.archive import BehaviorDescriptor
from aerocloud.outer_loop.descriptors import compute_descriptors


def _make_params(n_words: int, rotation_values: list[float] | None = None) -> torch.Tensor:
    """Create a params tensor of shape (n_words, 4): [y, x, scale, rotation]."""
    params = torch.zeros(n_words, 4)
    params[:, 0] = torch.linspace(0.1, 0.9, n_words)  # y positions
    params[:, 1] = torch.linspace(0.1, 0.9, n_words)  # x positions
    params[:, 2] = 0.5  # scale
    if rotation_values is not None:
        for i, r in enumerate(rotation_values[:n_words]):
            params[i, 3] = r
    return params


def _make_embeddings(n_words: int) -> np.ndarray:
    """Create random (n_words, 384) float32 embeddings."""
    rng = np.random.default_rng(42)
    embs = rng.standard_normal((n_words, 384)).astype(np.float32)
    # Normalize rows
    norms = np.linalg.norm(embs, axis=1, keepdims=True)
    return embs / norms


def _make_positions(n_words: int, canvas_h: int = 256, canvas_w: int = 256) -> np.ndarray:
    """Create (n_words, 2) [y, x] positions within the canvas."""
    rng = np.random.default_rng(7)
    positions = rng.uniform(0, 1, size=(n_words, 2))
    positions[:, 0] *= canvas_h
    positions[:, 1] *= canvas_w
    return positions.astype(np.float32)


def _make_sdf_mask(canvas_h: int = 256, canvas_w: int = 256) -> np.ndarray:
    """Create a circular binary SDF mask (True inside, False outside)."""
    cy, cx = canvas_h // 2, canvas_w // 2
    ys, xs = np.ogrid[:canvas_h, :canvas_w]
    radius = min(canvas_h, canvas_w) // 3
    return ((ys - cy) ** 2 + (xs - cx) ** 2) <= radius ** 2


class TestComputeDescriptors:
    def test_returns_behavior_descriptor(self) -> None:
        """Test 7: compute_descriptors returns a BehaviorDescriptor instance."""
        n_words = 10
        params = _make_params(n_words)
        embs = _make_embeddings(n_words)
        positions = _make_positions(n_words)
        mask = _make_sdf_mask()
        result = compute_descriptors(
            params=params,
            lc_metric=0.72,
            embeddings=embs,
            positions_yx=positions,
            sdf_mask=mask,
            n_words=n_words,
        )
        assert isinstance(result, BehaviorDescriptor)

    def test_all_fields_in_unit_interval(self) -> None:
        """Test 7: All 4 descriptor fields are in [0.0, 1.0]."""
        n_words = 15
        params = _make_params(n_words)
        embs = _make_embeddings(n_words)
        positions = _make_positions(n_words)
        mask = _make_sdf_mask()
        bd = compute_descriptors(
            params=params,
            lc_metric=0.65,
            embeddings=embs,
            positions_yx=positions,
            sdf_mask=mask,
            n_words=n_words,
        )
        assert 0.0 <= bd.shape_fidelity <= 1.0
        assert 0.0 <= bd.rotation_ratio <= 1.0
        assert 0.0 <= bd.symmetry <= 1.0
        assert 0.0 <= bd.semantic_clustering <= 1.0

    def test_shape_fidelity_equals_lc_metric(self) -> None:
        """Test 8: shape_fidelity is exactly the lc_metric value."""
        n_words = 8
        params = _make_params(n_words)
        embs = _make_embeddings(n_words)
        positions = _make_positions(n_words)
        mask = _make_sdf_mask()
        lc = 0.83
        bd = compute_descriptors(
            params=params,
            lc_metric=lc,
            embeddings=embs,
            positions_yx=positions,
            sdf_mask=mask,
            n_words=n_words,
        )
        assert bd.shape_fidelity == pytest.approx(lc)

    def test_rotation_ratio_all_zero_angles(self) -> None:
        """Test 9: rotation_ratio = 0 when all rotations are 0 (none exceed pi/4)."""
        n_words = 10
        params = _make_params(n_words, rotation_values=[0.0] * n_words)
        embs = _make_embeddings(n_words)
        positions = _make_positions(n_words)
        mask = _make_sdf_mask()
        bd = compute_descriptors(
            params=params,
            lc_metric=0.5,
            embeddings=embs,
            positions_yx=positions,
            sdf_mask=mask,
            n_words=n_words,
        )
        assert bd.rotation_ratio == pytest.approx(0.0)

    def test_rotation_ratio_all_large_angles(self) -> None:
        """Test 9: rotation_ratio = 1.0 when all rotations exceed pi/4."""
        n_words = 10
        large_angle = math.pi / 2  # 90 degrees — clearly > pi/4
        params = _make_params(n_words, rotation_values=[large_angle] * n_words)
        embs = _make_embeddings(n_words)
        positions = _make_positions(n_words)
        mask = _make_sdf_mask()
        bd = compute_descriptors(
            params=params,
            lc_metric=0.5,
            embeddings=embs,
            positions_yx=positions,
            sdf_mask=mask,
            n_words=n_words,
        )
        assert bd.rotation_ratio == pytest.approx(1.0)

    def test_rotation_ratio_half_large_angles(self) -> None:
        """Test 9: rotation_ratio = 0.5 when exactly half the rotations exceed pi/4."""
        n_words = 10
        large_angle = math.pi / 2
        rotations = [large_angle] * 5 + [0.0] * 5
        params = _make_params(n_words, rotation_values=rotations)
        embs = _make_embeddings(n_words)
        positions = _make_positions(n_words)
        mask = _make_sdf_mask()
        bd = compute_descriptors(
            params=params,
            lc_metric=0.5,
            embeddings=embs,
            positions_yx=positions,
            sdf_mask=mask,
            n_words=n_words,
        )
        assert bd.rotation_ratio == pytest.approx(0.5)

    def test_descriptors_clamped_at_boundaries(self) -> None:
        """Test 10: lc_metric at boundary values (0.0, 1.0) produces valid BehaviorDescriptor."""
        n_words = 5
        params = _make_params(n_words)
        embs = _make_embeddings(n_words)
        positions = _make_positions(n_words)
        mask = _make_sdf_mask()

        # lc = 0.0 boundary
        bd_low = compute_descriptors(
            params=params,
            lc_metric=0.0,
            embeddings=embs,
            positions_yx=positions,
            sdf_mask=mask,
            n_words=n_words,
        )
        assert 0.0 <= bd_low.shape_fidelity <= 1.0

        # lc = 1.0 boundary
        bd_high = compute_descriptors(
            params=params,
            lc_metric=1.0,
            embeddings=embs,
            positions_yx=positions,
            sdf_mask=mask,
            n_words=n_words,
        )
        assert 0.0 <= bd_high.shape_fidelity <= 1.0

    def test_n_words_smaller_than_params_rows(self) -> None:
        """Pitfall 3: n_words < params.shape[0] — only first n_words rows used."""
        # params is padded to 20, but only 10 actual words
        params = _make_params(20, rotation_values=[math.pi / 2] * 10 + [0.0] * 10)
        embs = _make_embeddings(10)  # only 10 embeddings
        positions = _make_positions(10)
        mask = _make_sdf_mask()
        # First 10 rows all have large rotation — expect rotation_ratio = 1.0
        bd = compute_descriptors(
            params=params,
            lc_metric=0.5,
            embeddings=embs,
            positions_yx=positions,
            sdf_mask=mask,
            n_words=10,  # actual word count
        )
        assert bd.rotation_ratio == pytest.approx(1.0)

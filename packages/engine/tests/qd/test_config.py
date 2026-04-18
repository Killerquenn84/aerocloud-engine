"""Tests for Settings archive-related fields (Phase 9 additions).

TDD RED phase.
"""

from __future__ import annotations

import pytest

from aerocloud.config import Settings


class TestSettingsArchiveFields:
    def test_archive_bins_per_dim_default(self) -> None:
        """archive_bins_per_dim defaults to 10."""
        s = Settings()
        assert s.archive_bins_per_dim == 10

    def test_archive_sigma_default(self) -> None:
        """archive_sigma defaults to 0.1."""
        s = Settings()
        assert s.archive_sigma == pytest.approx(0.1)

    def test_archive_batch_size_default(self) -> None:
        """archive_batch_size defaults to 16."""
        s = Settings()
        assert s.archive_batch_size == 16

    def test_archive_max_words_default(self) -> None:
        """archive_max_words defaults to 200."""
        s = Settings()
        assert s.archive_max_words == 200

    def test_novelty_k_default(self) -> None:
        """novelty_k defaults to 15."""
        s = Settings()
        assert s.novelty_k == 15

    def test_flush_every_n_default(self) -> None:
        """flush_every_n defaults to 100."""
        s = Settings()
        assert s.flush_every_n == 100

    def test_reeval_every_n_default(self) -> None:
        """reeval_every_n defaults to 200."""
        s = Settings()
        assert s.reeval_every_n == 200

    def test_archive_bins_per_dim_bounds(self) -> None:
        """archive_bins_per_dim must be in [2, 50]."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Settings(archive_bins_per_dim=1)  # below minimum

        with pytest.raises(ValidationError):
            Settings(archive_bins_per_dim=51)  # above maximum

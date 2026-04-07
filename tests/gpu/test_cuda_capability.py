"""GPU smoke tests — skipped on CPU-only hosts."""
from __future__ import annotations

import pytest
import torch

pytestmark = pytest.mark.gpu


def _has_cuda() -> bool:
    return torch.cuda.is_available()


@pytest.mark.skipif(not _has_cuda(), reason="no CUDA device available")
def test_compute_capability_at_least_6_0() -> None:
    assert torch.cuda.device_count() >= 1
    major, minor = torch.cuda.get_device_capability(0)
    assert major >= 6, f"Compute capability {major}.{minor} is below 6.0"


@pytest.mark.skipif(not _has_cuda(), reason="no CUDA device available")
def test_tensor_alloc_smoke() -> None:
    x = torch.zeros(1024, device="cuda:0")
    assert x.device.type == "cuda"
    assert x.numel() == 1024

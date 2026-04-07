"""Global determinism controls — call :func:`set_seed` at the start of every process.

Covers Python random, numpy, torch (CPU + CUDA), cuDNN, cuBLAS.

Must be called once at process startup (API lifespan hook, Celery worker init,
pytest fixture). Subsequent calls are idempotent.

References:
    - https://pytorch.org/docs/stable/notes/randomness.html
    - .planning/research/PITFALLS.md pitfall #11 (determinism loss)
    - .planning/phases/01-foundation/01-CONTEXT.md D-16/D-17/D-18
"""
from __future__ import annotations

import os
import random

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


def set_seed(seed: int = 42) -> None:
    """Set global seeds for reproducibility across all libraries.

    Args:
        seed: Integer seed value. Default 42 for test convenience.

    Notes:
        - ``CUBLAS_WORKSPACE_CONFIG=:4096:8`` is required for deterministic
          cuBLAS GEMM operations on CUDA 10.2+. This must be set BEFORE
          torch is first imported — we set it here with ``os.environ.setdefault``
          so it does not override a pre-existing Dockerfile/pytest env.
        - ``torch.use_deterministic_algorithms(True, warn_only=True)`` warns
          instead of raising when CUDA operations lack deterministic kernels.
          This is a deliberate trade-off for nvdiffrast compatibility in Phase 5.
    """
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    np.random.seed(seed)

    # Lazy torch import — keeps module import cheap for CPU-only environments
    import torch  # noqa: PLC0415

    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.use_deterministic_algorithms(True, warn_only=True)

    logger.info("determinism.set_seed", seed=seed)

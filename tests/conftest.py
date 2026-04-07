"""Shared pytest configuration.

- Sets CUBLAS_WORKSPACE_CONFIG BEFORE any torch import (required for
  deterministic cuBLAS GEMM on CUDA 10.2+).
- Provides session-scoped fixtures used across unit/integration/gpu tests.
"""
from __future__ import annotations

import os

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

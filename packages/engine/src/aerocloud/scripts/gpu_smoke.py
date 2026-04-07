"""GPU smoke test — reports CUDA availability and capability.

Exit codes:
    0 — CPU-only host (graceful skip) OR GPU with compute capability >= 6.0
    1 — CUDA available but all devices below compute capability 6.0

Usage:
    aerocloud-gpu-smoke                    # installed CLI
    uv run python scripts/gpu-smoke-test.py   # repo root wrapper
    uv run python -m aerocloud.scripts.gpu_smoke
"""
from __future__ import annotations

import sys

import torch

_MINIMUM_CAPABILITY = (6, 0)


def _format_capability(major: int, minor: int) -> str:
    return f"{major}.{minor}"


def main() -> int:
    print(f"torch: {torch.__version__}")
    print(f"torch.version.cuda: {torch.version.cuda}")
    print(f"torch.cuda.is_available: {torch.cuda.is_available()}")

    if not torch.cuda.is_available():
        print("[skip] no CUDA device — CPU-only host")
        return 0

    count = torch.cuda.device_count()
    print(f"torch.cuda.device_count: {count}")

    any_device_ok = False
    for idx in range(count):
        name = torch.cuda.get_device_name(idx)
        major, minor = torch.cuda.get_device_capability(idx)
        capability_str = _format_capability(major, minor)
        ok_marker = "OK" if (major, minor) >= _MINIMUM_CAPABILITY else "LOW"
        print(f"  device[{idx}]: {name} (compute {capability_str}) [{ok_marker}]")

        if (major, minor) >= _MINIMUM_CAPABILITY:
            any_device_ok = True

    # Tensor alloc smoke test
    try:
        x = torch.zeros(1024, device="cuda:0")
        print(f"tensor alloc: {x.device} numel={x.numel()} [OK]")
    except (RuntimeError, Exception) as exc:  # noqa: BLE001
        print(f"tensor alloc failed: {exc}")
        return 1

    # Optional nvdiffrast probe
    try:
        import nvdiffrast  # noqa: F401, PLC0415

        print("nvdiffrast: importable [OK]")
    except ImportError:
        print("nvdiffrast: not installed (expected in Phase 1 — arrives in Phase 5)")

    if not any_device_ok:
        print(
            f"[fail] all {count} devices below compute capability "
            f"{_format_capability(*_MINIMUM_CAPABILITY)}"
        )
        return 1

    print(f"[ok] at least one device meets compute capability {_format_capability(*_MINIMUM_CAPABILITY)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

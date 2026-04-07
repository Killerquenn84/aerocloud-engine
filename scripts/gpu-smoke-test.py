#!/usr/bin/env python3
"""Thin wrapper for the GPU smoke test — delegates to aerocloud.scripts.gpu_smoke.

Keeps the historical root-level scripts/ directory functional. The actual
logic lives in the installed Python package so it can be invoked via the
``aerocloud-gpu-smoke`` entry point.
"""

from __future__ import annotations

import sys

from aerocloud.scripts.gpu_smoke import main

if __name__ == "__main__":
    sys.exit(main())

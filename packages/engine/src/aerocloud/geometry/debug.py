"""AEROCLOUD_DEBUG_GEO=1 geometry debug dump (D-47).

Gated entirely on the env var — disabled by default, zero cost in production.
When enabled, writes a debug bundle to ``./debug/geometry/<ts>-<tag>/``:

    mask.png           — decoded boolean mask as L-mode PNG
    sdf_heatmap.png    — SDF rendered as a RdBu_r colormap (matplotlib lazy)
    spiral_trace.png   — spiral candidate positions overlaid on SDF (if provided)
    placement.json     — full PlacementResult dict (or whatever dict caller passes)
    env.json           — runtime environment snapshot

**R-7 compliance:** matplotlib is imported LAZILY inside the dump function, NOT
at module import time. matplotlib adds ~80 MB to the Docker image layers when
imported at module level. This module passes the grep-guard:
    ! grep -qE "^import matplotlib|^from matplotlib" debug.py

References:
    - D-47: debug dump specification
    - .planning/phases/04-geometry-v1/04-RESEARCH.md §12 R-7 (lazy matplotlib)
    - .planning/phases/04-geometry-v1/04-CONTEXT.md
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

_DEBUG_ENV: str = "AEROCLOUD_DEBUG_GEO"
_DEBUG_ALWAYS_ENV: str = "AEROCLOUD_DEBUG_GEO_ALWAYS"


def debug_enabled() -> bool:
    """Return True if the debug dump is active for this process.

    Active when ``AEROCLOUD_DEBUG_GEO`` is set to a truthy value (1, true, True).
    ``AEROCLOUD_DEBUG_GEO_ALWAYS`` is an alias that also enables this path.
    """
    for var in (_DEBUG_ENV, _DEBUG_ALWAYS_ENV):
        val = os.environ.get(var, "0")
        if val not in ("0", "", "false", "False"):
            return True
    return False


def dump_geometry_debug(
    *,
    mask: np.ndarray,
    sdf: np.ndarray,
    placement_json: dict[str, Any],
    spiral_trace: list[tuple[int, int]] | None = None,
    tag: str = "run",
) -> Path | None:
    """Write debug bundle to ``./debug/geometry/<ts>-<tag>/``.

    No-op and returns ``None`` when ``AEROCLOUD_DEBUG_GEO`` is not set.

    Args:
        mask:           Boolean (H, W) mask array. True = inside silhouette.
        sdf:            Float32 (H, W) signed distance field.
        placement_json: Dict representation of the placement result (e.g.,
                        ``PlacementResult.model_dump(mode='json')``).
        spiral_trace:   Optional list of ``(y, x)`` pixel positions visited by
                        the last failed word's spiral search.
        tag:            Short label appended to the output directory name.
                        Sanitized to alphanumerics and hyphens/underscores.

    Returns:
        ``Path`` to the created output directory, or ``None`` if disabled.
    """
    if not debug_enabled():
        return None

    # Sanitize tag to filesystem-safe characters
    safe_tag = "".join(c if c.isalnum() or c in "-_" else "_" for c in tag)
    ts = time.strftime("%Y%m%dT%H%M%S")
    out = Path("./debug/geometry") / f"{ts}-{safe_tag}"
    out.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # mask.png — plain L-mode greyscale (True → 255, False → 0)
    # -----------------------------------------------------------------------
    Image.fromarray((mask.astype(np.uint8) * 255), mode="L").save(out / "mask.png")

    # -----------------------------------------------------------------------
    # sdf_heatmap.png — lazy matplotlib import (R-7)
    # -----------------------------------------------------------------------
    try:
        import matplotlib  # noqa: PLC0415  (deliberate lazy import — R-7)

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # noqa: PLC0415

        fig, ax = plt.subplots(figsize=(6, 6))
        im = ax.imshow(sdf, cmap="RdBu_r", origin="upper")
        fig.colorbar(im, ax=ax)
        ax.set_title("SDF (positive=inside, ADR-0004)")
        fig.savefig(out / "sdf_heatmap.png", dpi=72, bbox_inches="tight")
        plt.close(fig)
    except ImportError:
        (out / "sdf_heatmap.MISSING").write_text("matplotlib not installed; SDF heatmap omitted")

    # -----------------------------------------------------------------------
    # spiral_trace.png — overlay of spiral positions on SDF (lazy matplotlib)
    # -----------------------------------------------------------------------
    if spiral_trace:
        try:
            import matplotlib  # noqa: PLC0415

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt  # noqa: PLC0415

            fig, ax = plt.subplots(figsize=(6, 6))
            ax.imshow(sdf, cmap="gray", origin="upper")
            ys, xs = zip(*spiral_trace, strict=True)
            ax.plot(xs, ys, "r.-", markersize=1, linewidth=0.5)
            ax.set_title(f"Spiral trace ({len(spiral_trace)} pts)")
            fig.savefig(out / "spiral_trace.png", dpi=72, bbox_inches="tight")
            plt.close(fig)
        except ImportError:
            (out / "spiral_trace.MISSING").write_text(
                "matplotlib not installed; spiral trace omitted"
            )

    # -----------------------------------------------------------------------
    # placement.json — full placement result
    # -----------------------------------------------------------------------
    (out / "placement.json").write_text(json.dumps(placement_json, indent=2, default=str))

    # -----------------------------------------------------------------------
    # env.json — runtime snapshot
    # -----------------------------------------------------------------------
    try:
        import PIL  # noqa: PLC0415

        pillow_version: str = getattr(PIL, "__version__", "unknown")
    except ImportError:
        pillow_version = "unknown"

    try:
        import scipy  # noqa: PLC0415

        scipy_version: str = getattr(scipy, "__version__", "unknown")
    except ImportError:
        scipy_version = "unknown"

    from PIL import features as _pil_features  # noqa: PLC0415

    env: dict[str, str] = {
        "python": sys.version,
        "platform": platform.platform(),
        "hostname": platform.node(),
        "numpy": np.__version__,
        "pillow": pillow_version,
        "freetype": str(_pil_features.version("freetype2")),
        "scipy": scipy_version,
    }
    (out / "env.json").write_text(json.dumps(env, indent=2))

    return out

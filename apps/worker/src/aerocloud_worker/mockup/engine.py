"""MockupEngine — canonical render entry point.

Sprint history:
    * P23 phase A: initial render + cache
    * P24: auto-detect of smart-object layer
    * P26: robustness-hardening — input validation, timeouts, graceful
      degradation, structured logging. The engine now NEVER crashes on
      malformed inputs — every failure mode raises a typed exception.
"""
from __future__ import annotations

import gc
import hashlib
import logging
import time
from pathlib import Path

from PIL import Image
from psd_tools import PSDImage
from psd_tools.api.layers import SmartObjectLayer

from . import compositor as _compositor
from .compositor import render_background_only, render_composite  # re-exported for tests
from .exceptions import (
    MockupRenderError,
    MockupRenderTimeoutError,
    UnsupportedColorModeError,
)
from .perspective import warp_to_box
from .smart_object import _iter_layers, locate_smart_object  # noqa: PLC2701
from .timeouts import with_timeout
from .validation import (
    validate_design,
    validate_psd_header,
    validate_psd_size,
)

log = logging.getLogger(__name__)

# Phase A: simple in-memory cache. Phase B swaps in Redis with the same API.
_RENDER_CACHE: dict[str, Image.Image] = {}

_SUPPORTED_COLOR_MODES = {"RGB", "RGBA"}


def _cache_key(psd_path: Path, design_path: Path, layer_name: str | None) -> str:
    h = hashlib.sha256()
    h.update((layer_name or "").encode("utf-8"))
    h.update(b"\x00")
    h.update(psd_path.read_bytes())
    h.update(b"\x00")
    h.update(design_path.read_bytes())
    return h.hexdigest()


def _psd_color_mode_name(psd: PSDImage) -> str:
    """Best-effort color-mode label for the unsupported-mode error."""
    mode = getattr(psd, "color_mode", None)
    if mode is None:
        return "?"
    return getattr(mode, "name", str(mode))


class MockupEngine:
    """Renders a Wordcloud design into a PSD mockup template.

    Stateless apart from the in-process idempotency cache. Safe to instantiate
    per request; Phase B will move state into Redis.
    """

    def __init__(
        self,
        *,
        cache: dict[str, Image.Image] | None = None,
        fallback_on_overlay_failure: bool = True,
        parse_timeout_s: float = 30.0,
        composite_timeout_s: float = 60.0,
    ) -> None:
        self._cache = _RENDER_CACHE if cache is None else cache
        self.fallback_on_overlay_failure = fallback_on_overlay_failure
        self.parse_timeout_s = parse_timeout_s
        self.composite_timeout_s = composite_timeout_s

    @staticmethod
    def clear_cache() -> None:
        _RENDER_CACHE.clear()

    def render(
        self,
        psd_path: str | Path,
        design_path: str | Path,
        layer_name: str | None = None,
        *,
        task_id: str | None = None,
    ) -> Image.Image:
        """Render ``design_path`` into the smart-object of ``psd_path``."""
        psd_path = Path(psd_path)
        design_path = Path(design_path)
        t_start = time.monotonic()

        log.info(
            "mockup.render.start",
            extra={
                "event": "mockup.render.start",
                "task_id": task_id,
                "psd_path": str(psd_path),
                "design_path": str(design_path),
                "layer_name": layer_name,
            },
        )

        # --- 1. Input validation ------------------------------------------------
        log.info("mockup.validate.start", extra={
            "event": "mockup.validate.start", "task_id": task_id})
        try:
            validate_psd_header(psd_path)
            validate_psd_size(psd_path)
            validate_design(design_path)
        except MockupRenderError as exc:
            log.warning(
                "mockup.validate.fail",
                extra={
                    "event": "mockup.validate.fail",
                    "task_id": task_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
            raise

        # --- 2. Cache lookup ----------------------------------------------------
        key = _cache_key(psd_path, design_path, layer_name)
        cached = self._cache.get(key)
        if cached is not None:
            log.info(
                "mockup.render.complete",
                extra={
                    "event": "mockup.render.complete",
                    "task_id": task_id,
                    "cached": True,
                    "duration_ms": int((time.monotonic() - t_start) * 1000),
                },
            )
            return cached.copy()

        # --- 3. Parse with timeout ---------------------------------------------
        psd: PSDImage | None = None
        try:
            try:
                psd = with_timeout(
                    PSDImage.open, psd_path, timeout_s=self.parse_timeout_s
                )
            except MockupRenderTimeoutError:
                log.error(
                    "mockup.render.error",
                    extra={
                        "event": "mockup.render.error",
                        "task_id": task_id,
                        "step": "parse",
                        "error_type": "MockupRenderTimeoutError",
                    },
                )
                raise

            mode_name = _psd_color_mode_name(psd)
            if mode_name not in _SUPPORTED_COLOR_MODES:
                exc = UnsupportedColorModeError(mode_name)
                log.warning(
                    "mockup.validate.fail",
                    extra={
                        "event": "mockup.validate.fail",
                        "task_id": task_id,
                        "error_type": "UnsupportedColorModeError",
                        "color_mode": mode_name,
                    },
                )
                raise exc

            # --- 4. Locate smart object ----------------------------------------
            info = locate_smart_object(psd, layer_name=layer_name)
            smart_layer: SmartObjectLayer | None = None
            for layer in _iter_layers(psd):
                if layer.name == info.layer_name and isinstance(
                    layer, SmartObjectLayer
                ):
                    smart_layer = layer
                    break
            if smart_layer is None:  # pragma: no cover — locate_smart_object guards
                raise MockupRenderError(
                    "smart layer disappeared between locate and composite"
                )

            # --- 5. Warp design -------------------------------------------------
            with Image.open(design_path) as raw_design:
                design = raw_design.convert("RGBA")
            warped = warp_to_box(design, info.transform_box, (psd.width, psd.height))

            # --- 6. Composite with overlay-fallback -----------------------------
            result = self._composite_with_fallback(
                psd=psd,
                warped=warped,
                smart_layer=smart_layer,
                task_id=task_id,
            )

            self._cache[key] = result.copy()

            log.info(
                "mockup.render.complete",
                extra={
                    "event": "mockup.render.complete",
                    "task_id": task_id,
                    "cached": False,
                    "duration_ms": int((time.monotonic() - t_start) * 1000),
                    "color_mode": mode_name,
                },
            )
            return result

        except MockupRenderError:
            raise
        except Exception as exc:
            log.error(
                "mockup.render.error",
                extra={
                    "event": "mockup.render.error",
                    "task_id": task_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                exc_info=True,
            )
            raise MockupRenderError(f"Unexpected render failure: {exc}") from exc
        finally:
            # Bounded-memory: drop PSD + run gc so the next render starts clean.
            if psd is not None:
                del psd
            gc.collect()

    # ----------------------------------------------------------------------
    # Internals
    # ----------------------------------------------------------------------

    def _composite_with_fallback(
        self,
        *,
        psd: PSDImage,
        warped: Image.Image,
        smart_layer: SmartObjectLayer,
        task_id: str | None,
    ) -> Image.Image:
        try:
            return with_timeout(
                _compositor.render_composite,
                psd,
                warped,
                smart_layer,
                timeout_s=self.composite_timeout_s,
            )
        except MockupRenderTimeoutError:
            raise
        except Exception as overlay_err:
            if not self.fallback_on_overlay_failure:
                raise
            log.warning(
                "mockup.render.fallback",
                extra={
                    "event": "mockup.render.fallback",
                    "task_id": task_id,
                    "error_type": type(overlay_err).__name__,
                    "error": str(overlay_err),
                    "reason": "overlay_failure",
                },
            )
            try:
                return _compositor.render_background_only(psd, warped, smart_layer)
            except Exception as fallback_err:
                log.error(
                    "mockup.render.error",
                    extra={
                        "event": "mockup.render.error",
                        "task_id": task_id,
                        "step": "fallback_background_only",
                        "error_type": type(fallback_err).__name__,
                    },
                    exc_info=True,
                )
                raise MockupRenderError(
                    f"Background-only fallback also failed: {fallback_err}"
                ) from fallback_err

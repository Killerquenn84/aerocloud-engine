"""Open-Source Mockup-Engine (Sprints P23 + P24 + P26).

Public surface:
    - MockupEngine        — canonical render() entry-point
    - SmartObjectInfo     — value object describing a located Smart Object
    - locate_smart_object — low-level finder used by tests/Phase B API
    - warp_to_box         — 4-point perspective warp
    - render_composite    — final compositor
    - render_background_only — graceful-degradation fallback (P26)
    - validation guards   — validate_psd_header / validate_psd_size / validate_design
    - with_timeout        — thread-based timeout wrapper for sync calls
    - retry               — exponential-backoff decorator
    - Exception hierarchy — see ``exceptions`` module
"""
from __future__ import annotations

from .compositor import render_background_only, render_composite
from .engine import MockupEngine
from .exceptions import (
    AmbiguousLayerError,
    InvalidDesignError,
    InvalidPSDError,
    MockupRenderError,
    MockupRenderTimeoutError,
    NoSmartObjectError,
    PSDTooLargeError,
    RateLimitError,
    S3DownloadError,
    UnsupportedColorModeError,
)
from .perspective import warp_to_box
from .retries import retry
from .smart_object import (
    DEFAULT_LAYER_PRIORITY,
    SmartObjectInfo,
    TransformBox,
    locate_smart_object,
)
from .timeouts import with_timeout
from .validation import validate_design, validate_psd_header, validate_psd_size

__all__ = [
    "DEFAULT_LAYER_PRIORITY",
    "AmbiguousLayerError",
    "InvalidDesignError",
    "InvalidPSDError",
    "MockupEngine",
    "MockupRenderError",
    "MockupRenderTimeoutError",
    "NoSmartObjectError",
    "PSDTooLargeError",
    "RateLimitError",
    "S3DownloadError",
    "SmartObjectInfo",
    "TransformBox",
    "UnsupportedColorModeError",
    "locate_smart_object",
    "render_background_only",
    "render_composite",
    "retry",
    "validate_design",
    "validate_psd_header",
    "validate_psd_size",
    "warp_to_box",
    "with_timeout",
]

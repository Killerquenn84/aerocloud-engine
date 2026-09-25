"""Custom exceptions for the Mockup-Engine (Sprint P23, P24, P26)."""
from __future__ import annotations


class MockupRenderError(Exception):
    """Base error for all mockup rendering failures."""


class NoSmartObjectError(MockupRenderError):
    """Raised when the requested smart-object layer cannot be located.

    Two cases:
      - Layer name not present at all (`available_layers` lists what was found)
      - Layer name present but the layer is not a Smart Object
    """

    def __init__(
        self,
        message: str,
        *,
        available_layers: list[str] | None = None,
    ) -> None:
        self.available_layers = available_layers or []
        if available_layers:
            message = f"{message} | available_layers={available_layers}"
        super().__init__(message)


class AmbiguousLayerError(MockupRenderError):
    """Raised when auto-detect finds multiple smart objects and none matches a convention.

    Sprint P24 Scenario 7. The caller must specify ``layer_name`` explicitly.
    """

    def __init__(self, candidates: list[str]):
        self.candidates = list(candidates)
        super().__init__(
            f"Multiple smart objects found, none matches convention. "
            f"Specify layer_name explicitly. Candidates: {self.candidates}"
        )


# ---------------------------------------------------------------------------
# Sprint P26 — robustness-hardening exceptions
# ---------------------------------------------------------------------------


class InvalidPSDError(MockupRenderError):
    """Raised when the PSD header sniff fails (bad magic bytes or truncated)."""


class PSDTooLargeError(MockupRenderError):
    """Raised when the PSD file exceeds MAX_PSD_BYTES before any parse attempt."""

    def __init__(self, size: int, limit: int) -> None:
        self.size = size
        self.limit = limit
        super().__init__(
            f"PSD size {size} bytes exceeds limit {limit} bytes"
        )


class InvalidDesignError(MockupRenderError):
    """Raised when the design file is not a usable single-frame raster image."""


class UnsupportedColorModeError(MockupRenderError):
    """Raised when the PSD is in an unsupported color mode (e.g. CMYK, Lab)."""

    def __init__(self, mode: str) -> None:
        self.mode = mode
        super().__init__(
            f"Unsupported PSD color mode '{mode}'. Convert to RGB before upload."
        )


class S3DownloadError(MockupRenderError):
    """Raised when an S3 download permanently fails after all retries."""


class MockupRenderTimeoutError(MockupRenderError):
    """Raised when a render-step exceeds its configured timeout."""


class RateLimitError(Exception):
    """Signals an upstream rate-limit response (HTTP 429).

    Carries ``retry_after_s`` so the retry decorator can honour the
    ``Retry-After`` header instead of using its own backoff schedule.
    Intentionally NOT a MockupRenderError — it is transient.
    """

    def __init__(self, retry_after_s: int, message: str = "Rate limited") -> None:
        self.retry_after_s = int(retry_after_s)
        super().__init__(f"{message} (retry_after_s={self.retry_after_s})")

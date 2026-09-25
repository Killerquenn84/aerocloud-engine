"""Input validation for the Mockup-Engine (Sprint P26 scenarios 1-4).

Three guards, each callable in isolation:

* :func:`validate_psd_header` — sniffs the 8-byte PSD signature.
* :func:`validate_psd_size`   — bounds the on-disk file size.
* :func:`validate_design`     — checks the PNG/JPG design for usability.

Each guard raises a typed exception from :mod:`.exceptions` and never returns
a value — the caller chains them defensively. Limits read from environment
variables on every call (no module-level capture) so tests can monkeypatch
``os.environ`` without re-importing.
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from .exceptions import (
    InvalidDesignError,
    InvalidPSDError,
    PSDTooLargeError,
)

_PSD_MAGIC = b"8BPS"

# Defaults — overridden by ENV at call-time.
_DEFAULT_MAX_PSD_BYTES = 500_000_000
_DEFAULT_MAX_DESIGN_BYTES = 100_000_000
_DEFAULT_MIN_DESIGN_DIM = 100
_DEFAULT_MAX_DESIGN_DIM = 10_000


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def validate_psd_header(path: str | Path) -> None:
    """Read the first 4 bytes and require the PSD ``8BPS`` magic.

    Raises :class:`InvalidPSDError` if the file is too short, unreadable, or
    has a non-PSD signature. Does NOT open the PSD through ``psd-tools``.
    """
    p = Path(path)
    try:
        with p.open("rb") as fh:
            head = fh.read(4)
    except OSError as exc:  # missing, permission denied, etc.
        raise InvalidPSDError(f"Cannot read PSD header: {exc}") from exc
    if len(head) < 4:
        raise InvalidPSDError(
            f"PSD too short: got {len(head)} header bytes, expected >=4"
        )
    if head != _PSD_MAGIC:
        raise InvalidPSDError(
            f"Invalid PSD magic bytes: expected {_PSD_MAGIC!r}, got {head!r}"
        )


def validate_psd_size(
    path: str | Path,
    max_bytes: int | None = None,
) -> None:
    """Refuse files above ``MAX_PSD_BYTES`` (env-tunable) before any parse."""
    if max_bytes is None:
        max_bytes = _env_int("MAX_PSD_BYTES", _DEFAULT_MAX_PSD_BYTES)
    p = Path(path)
    try:
        size = p.stat().st_size
    except OSError as exc:
        raise InvalidPSDError(f"Cannot stat PSD: {exc}") from exc
    if size > max_bytes:
        raise PSDTooLargeError(size, max_bytes)


def validate_design(path: str | Path) -> None:
    """Validate a design image: real raster, single frame, sane dimensions.

    Raises :class:`InvalidDesignError` on:
      * file missing / unreadable
      * size above ``MAX_DESIGN_BYTES``
      * Pillow cannot identify the image
      * multi-frame (animated GIF/APNG/TIFF)
      * dimensions outside [MIN_DESIGN_DIM, MAX_DESIGN_DIM]
    """
    max_bytes = _env_int("MAX_DESIGN_BYTES", _DEFAULT_MAX_DESIGN_BYTES)
    min_dim = _env_int("MIN_DESIGN_DIM", _DEFAULT_MIN_DESIGN_DIM)
    max_dim = _env_int("MAX_DESIGN_DIM", _DEFAULT_MAX_DESIGN_DIM)

    p = Path(path)
    try:
        size = p.stat().st_size
    except OSError as exc:
        raise InvalidDesignError(f"Cannot stat design: {exc}") from exc
    if size == 0:
        raise InvalidDesignError("Design file is empty (0 bytes)")
    if size > max_bytes:
        raise InvalidDesignError(
            f"Design size {size} bytes exceeds limit {max_bytes} bytes"
        )

    try:
        with Image.open(p) as img:
            # is_animated triggers a lazy header parse but reads no pixel data.
            is_animated = bool(getattr(img, "is_animated", False))
            n_frames = int(getattr(img, "n_frames", 1))
            width, height = img.size
            fmt = img.format or "?"
    except UnidentifiedImageError as exc:
        raise InvalidDesignError(
            f"Pillow cannot identify the design file as an image"
        ) from exc
    except OSError as exc:
        raise InvalidDesignError(f"Cannot read design image: {exc}") from exc

    if is_animated or n_frames > 1:
        raise InvalidDesignError(
            f"Animated images not supported (format={fmt}, frames={n_frames})"
        )

    if width < min_dim or height < min_dim:
        raise InvalidDesignError(
            f"Design too small: {width}x{height}, min {min_dim}x{min_dim}"
        )
    if width > max_dim or height > max_dim:
        raise InvalidDesignError(
            f"Design too large: {width}x{height}, max {max_dim}x{max_dim}"
        )

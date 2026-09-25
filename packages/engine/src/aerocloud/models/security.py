"""Security validators for AeroCloud Engine (PROD-13, PROD-14, PROD-15).

Provides pure-function validators for:
- Color allow-list: HEX_COLOR_RE regex per D-15 (XSS prevention in SVG fill=)
- Font allow-list: loaded from assets/fonts/ directory per D-16
- Path traversal prevention: rejects ../, .., null bytes per D-17

All validators are:
- Pure functions (no I/O side effects at call time)
- Testable in isolation
- Usable as Pydantic field_validator callbacks
- Usable by export modules for pre-flight checks

Trust boundary: API → export pipeline. User-supplied strings must be
validated before they cross into SVG attributes, PDF operators, or file paths.
"""

from __future__ import annotations

import re
from importlib import resources
from pathlib import Path

# ---------------------------------------------------------------------------
# Color validator (PROD-15, D-15)
# ---------------------------------------------------------------------------

#: Hex color allow-list regex — exactly matches D-15 specification.
#: Accepts 3, 4, 6, 7, or 8 hex characters with leading #.
#: Rejects named colors, rgb() functions, XSS payloads, empty strings.
HEX_COLOR_RE: re.Pattern[str] = re.compile(r"^#[0-9a-fA-F]{3,8}$")


def validate_hex_color(color: str) -> str:
    """Validate a CSS hex color string against the allow-list regex.

    Only accepts strings matching ^#[0-9a-fA-F]{3,8}$ (D-15).
    Rejects named colors, rgb() functions, empty strings, XSS payloads.

    Args:
        color: CSS color string to validate.

    Returns:
        The original color string if valid.

    Raises:
        ValueError: If the string does not match the hex color regex.
    """
    if not HEX_COLOR_RE.fullmatch(color):
        raise ValueError(
            f"Invalid hex color: {color!r}. "
            "Expected format: #RGB, #RRGGBB, or #RRGGBBAA (hex digits only)."
        )
    return color


# ---------------------------------------------------------------------------
# Font validator (PROD-14, D-16)
# ---------------------------------------------------------------------------


def _load_allowed_fonts() -> frozenset[str]:
    """Scan assets/fonts/ directory and return font family names as a frozenset.

    Font family names are the top-level directory names under assets/fonts/.
    For example, assets/fonts/Inter/ → "Inter".

    Uses importlib.resources for package-relative path resolution, with
    fallback to __file__-relative path for editable installs.

    Returns:
        Frozenset of allowed font family names.
    """
    try:
        # Preferred: importlib.resources (works in both editable + wheel)
        fonts_pkg = resources.files("aerocloud.assets.fonts")
        font_names: set[str] = set()
        for item in fonts_pkg.iterdir():
            # Each subdirectory is a font family
            if item.is_dir():
                font_names.add(item.name)
        return frozenset(font_names)
    except (TypeError, AttributeError, FileNotFoundError):
        # Fallback: path relative to this file
        fonts_dir = Path(__file__).parent.parent / "assets" / "fonts"
        if not fonts_dir.is_dir():
            return frozenset()
        return frozenset(d.name for d in fonts_dir.iterdir() if d.is_dir())


#: Module-level cache of allowed font names, loaded once at import time.
_ALLOWED_FONTS: frozenset[str] = _load_allowed_fonts()


def get_allowed_fonts() -> frozenset[str]:
    """Return the cached frozenset of allowed font family names.

    Font names are derived from directory names under assets/fonts/.
    The result is cached at module import time — no file I/O on subsequent calls.

    Returns:
        Frozenset of allowed font family names (e.g. {"Inter", "IBM-Plex-Serif"}).
    """
    return _ALLOWED_FONTS


def validate_font_name(
    name: str,
    allowed: frozenset[str] | None = None,
) -> str:
    """Validate a font family name against the allow-list.

    By default uses the module-level frozenset loaded from assets/fonts/.
    A custom allowed set can be provided for testing or dynamic configuration.

    Args:
        name: Font family name to validate.
        allowed: Optional frozenset of allowed names. Defaults to get_allowed_fonts().

    Returns:
        The original name string if valid.

    Raises:
        ValueError: If name is empty or not in the allowed set.
    """
    if not name:
        raise ValueError("Font name must not be empty.")

    effective_allowed = allowed if allowed is not None else _ALLOWED_FONTS

    if name not in effective_allowed:
        raise ValueError(
            f"Font {name!r} is not in the allowed font list. Allowed: {sorted(effective_allowed)}"
        )
    return name


# ---------------------------------------------------------------------------
# Path traversal validator (PROD-13, D-17)
# ---------------------------------------------------------------------------

#: Patterns that indicate path traversal attempts.
_TRAVERSAL_PATTERNS: tuple[str, ...] = ("../", "..\x5c", "\x00")


def validate_no_path_traversal(value: str) -> str:
    """Reject strings containing path traversal patterns or null bytes.

    Guards against:
    - Unix traversal: '../'
    - Windows traversal: '..\\'
    - Null byte injection: '\\x00'

    Applies to any user-supplied string field that could be used in file
    path operations (e.g. shape_b64 base64 strings, file references).

    Args:
        value: String to validate.

    Returns:
        The original value if no traversal patterns found.

    Raises:
        ValueError: If any traversal pattern or null byte is detected.
    """
    for pattern in _TRAVERSAL_PATTERNS:
        if pattern in value:
            raise ValueError(
                f"Path traversal pattern detected in input: {pattern!r}. "
                "Input rejected for security."
            )
    return value

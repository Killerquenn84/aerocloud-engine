"""Font registration — idempotent, module-level cache.

Phase 1 provides the registration machinery. Bundled font files (Inter +
IBM Plex Serif) are added in Wave 6. Calling :func:`register_fonts` before
the files exist will log a warning and return an empty set.

References:
    - .planning/research/PITFALLS.md pitfall #2 (canvas memory leak from
      per-request font registration)
    - .planning/phases/01-foundation/01-CONTEXT.md D-32..D-34
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

_REGISTERED: set[str] = set()


def _discover_font_files() -> list[Path]:
    """Find all ``.ttf`` files bundled under ``aerocloud/assets/fonts``.

    Uses :mod:`importlib.resources` so this works both when installed as a
    wheel and when running from a src layout.
    """
    try:
        root = resources.files("aerocloud") / "assets" / "fonts"
    except (ModuleNotFoundError, FileNotFoundError):
        return []

    if not root.is_dir():
        return []

    # Convert Traversable to a filesystem Path (works for editable installs
    # and unpacked wheels; Traversable doesn't expose rglob directly).
    root_path = Path(str(root))
    if not root_path.is_dir():
        return []
    return sorted(p for p in root_path.rglob("*.ttf") if p.is_file())


def register_fonts() -> set[str]:
    """Register all bundled fonts exactly once per process.

    Returns the set of font family names that have been registered. Safe to
    call many times — only the first call actually touches the filesystem
    (prevents the per-request canvas leak documented in the pitfalls research).
    """
    if _REGISTERED:
        return set(_REGISTERED)

    files = _discover_font_files()
    if not files:
        logger.warning("fonts.no_files_found", hint="Wave 6 will add them")
        return set()

    for font_file in files:
        _REGISTERED.add(font_file.stem)
        logger.info("fonts.registered", path=str(font_file))

    return set(_REGISTERED)


def registered_font_count() -> int:
    """Return the number of currently registered fonts (test helper)."""
    return len(_REGISTERED)


def _reset_for_tests() -> None:
    """Internal: clear the registry (only used by test fixtures)."""
    _REGISTERED.clear()

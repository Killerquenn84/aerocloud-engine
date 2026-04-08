"""Language detection backed by `lingua-language-detector`.

Design decisions (see wiki/discussions/2026-04-08-phase-03-wave-2-design.md):
- Wave 2 scope is restricted to English + German; lingua is limited to those
  two languages so short ambiguous fragments are classified against the
  smallest reasonable hypothesis space.
- The detector is built lazily behind a lock because `LanguageDetectorBuilder`
  loads language models into memory eagerly and we pay for it only if the
  pipeline actually calls us (e.g. when the caller passes `lang='auto'`).
- Low-confidence detections return `'und'` (ISO 639-3 "undetermined") instead
  of guessing. Mixed DE/EN texts are a known limitation documented here and
  in the Wave 2 design doc.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any, Final

_UNDETERMINED: Final[str] = "und"
_DEFAULT_CONFIDENCE_THRESHOLD: Final[float] = 0.5
_LANG_CODE_BY_LINGUA: Final[dict[str, str]] = {
    "ENGLISH": "en",
    "GERMAN": "de",
}

_detector_lock = threading.RLock()
_detector: Any | None = None

if TYPE_CHECKING:  # pragma: no cover
    pass


def _get_detector() -> Any:
    """Lazy-build the lingua detector, restricted to {English, German}.

    Concurrent callers (Celery workers in later phases) race through the
    double-checked lock; only one build ever runs.
    """
    global _detector  # noqa: PLW0603 - lazy singleton, thread-safe via _detector_lock
    if _detector is not None:
        return _detector
    with _detector_lock:
        if _detector is not None:
            return _detector
        from lingua import Language, LanguageDetectorBuilder  # noqa: PLC0415

        _detector = (
            LanguageDetectorBuilder.from_languages(Language.ENGLISH, Language.GERMAN)
            .with_preloaded_language_models()
            .build()
        )
        return _detector


def reset_detector() -> None:
    """Drop the cached detector. Test-only helper."""
    global _detector  # noqa: PLW0603 - test-only reset of the lazy singleton
    with _detector_lock:
        _detector = None


def detect_language(
    text: str,
    confidence_threshold: float = _DEFAULT_CONFIDENCE_THRESHOLD,
) -> str:
    """Detect the language of `text`.

    Returns an ISO 639-1 code (`'en'` or `'de'`) when the top candidate clears
    `confidence_threshold`, otherwise `'und'`. Empty / whitespace-only input
    short-circuits to `'und'` without touching lingua.
    """
    if not text.strip():
        return _UNDETERMINED

    detector = _get_detector()
    confidences = detector.compute_language_confidence_values(text)
    if not confidences:
        return _UNDETERMINED

    top = confidences[0]
    if top.value < confidence_threshold:
        return _UNDETERMINED
    return _LANG_CODE_BY_LINGUA.get(top.language.name, _UNDETERMINED)

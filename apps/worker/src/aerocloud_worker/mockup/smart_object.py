"""Locate Smart-Object layers in a PSD and expose their transform_box.

Sprint P23 (Phase A) — BDD scenarios 1-4: exact-name lookup.
Sprint P24 — auto-detect when ``layer_name`` is omitted (None).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from psd_tools import PSDImage
from psd_tools.api.layers import Layer, SmartObjectLayer

from .exceptions import AmbiguousLayerError, NoSmartObjectError

# 4 corners (x1,y1, x2,y2, x3,y3, x4,y4) — top-left, top-right, bottom-right, bottom-left.
TransformBox = tuple[float, float, float, float, float, float, float, float]


#: Priority list for auto-detect. Exact-name matches win in this order before
#: pattern fallbacks (``*Design``) and the single-smart-object fallback kick in.
DEFAULT_LAYER_PRIORITY: list[str] = [
    "WORDCLOUD",
    "Replace me",
    "Your artwork here",
]


@dataclass(frozen=True)
class SmartObjectInfo:
    """Value object describing a located Smart-Object layer."""

    layer_name: str
    transform_box: TransformBox
    bbox: tuple[int, int, int, int]
    layer_index: int  # depth-first traversal index (Background=0 first leaf)


def _iter_layers(node: PSDImage | Layer) -> Iterable[Layer]:
    """Depth-first traversal yielding every leaf layer (groups expanded)."""
    if hasattr(node, "__iter__"):
        for child in node:
            yield child
            if hasattr(child, "__iter__"):
                yield from _iter_layers(child)


def _all_layer_names(psd: PSDImage) -> list[str]:
    return [layer.name for layer in _iter_layers(psd)]


def _build_info(layer: SmartObjectLayer, index: int) -> SmartObjectInfo:
    """Build a SmartObjectInfo from an already-validated SmartObjectLayer."""
    transform_box = tuple(float(v) for v in layer.smart_object.transform_box)
    if len(transform_box) != 8:
        raise NoSmartObjectError(
            f"Smart-Object {layer.name!r} has malformed transform_box "
            f"(expected 8 floats, got {len(transform_box)})"
        )
    bbox = tuple(int(v) for v in layer.bbox)
    return SmartObjectInfo(
        layer_name=layer.name,
        transform_box=transform_box,  # type: ignore[arg-type]
        bbox=bbox,  # type: ignore[arg-type]
        layer_index=index,
    )


def _collect_all_smart_objects(psd: PSDImage) -> list[SmartObjectInfo]:
    """Walk the PSD tree and collect every valid Smart-Object layer.

    Returns the layers in depth-first traversal order. Layers whose
    ``smart_object`` is ``None`` or whose ``transform_box`` is malformed are
    silently skipped — they cannot be edited anyway.
    """
    out: list[SmartObjectInfo] = []
    for idx, layer in enumerate(_iter_layers(psd)):
        if not isinstance(layer, SmartObjectLayer):
            continue
        if layer.smart_object is None:
            continue
        try:
            out.append(_build_info(layer, idx))
        except NoSmartObjectError:
            # Malformed transform_box — skip rather than crash auto-detect.
            continue
    return out


def _locate_by_exact_name(psd: PSDImage, layer_name: str) -> SmartObjectInfo:
    """Original Phase-A path: exact case-sensitive name lookup."""
    found: Layer | None = None
    index = -1
    for idx, layer in enumerate(_iter_layers(psd)):
        if layer.name == layer_name:
            found = layer
            index = idx
            break

    if found is None:
        raise NoSmartObjectError(
            f"Smart-Object layer {layer_name!r} not found in PSD",
            available_layers=_all_layer_names(psd),
        )

    if not isinstance(found, SmartObjectLayer) or found.smart_object is None:
        raise NoSmartObjectError(
            f"Layer {layer_name!r} exists but is not a Smart Object "
            f"(kind={type(found).__name__})"
        )

    return _build_info(found, index)


def _auto_detect(psd: PSDImage) -> SmartObjectInfo:
    """Auto-detect the target Smart-Object using P24 priority rules."""
    candidates = _collect_all_smart_objects(psd)
    if not candidates:
        raise NoSmartObjectError(
            "No Smart-Object layers found in PSD",
            available_layers=_all_layer_names(psd),
        )

    by_name = {c.layer_name: c for c in candidates}

    # 1. Exact match against DEFAULT_LAYER_PRIORITY (in order).
    for preferred in DEFAULT_LAYER_PRIORITY:
        if preferred in by_name:
            return by_name[preferred]

    # 2. Pattern: layers whose name contains "Design".
    #    Prefer exact "*Design" suffix matches; fall back to "Design" anywhere.
    suffix_design = [c for c in candidates if c.layer_name.endswith("Design")]
    if len(suffix_design) == 1:
        return suffix_design[0]

    contains_design = [c for c in candidates if "Design" in c.layer_name]
    if len(contains_design) == 1:
        return contains_design[0]

    # 3. Last resort: exactly one Smart Object → take it.
    if len(candidates) == 1:
        return candidates[0]

    # 4. Ambiguous — caller must disambiguate via layer_name.
    raise AmbiguousLayerError(candidates=[c.layer_name for c in candidates])


def locate_smart_object(
    psd: PSDImage,
    layer_name: str | None = None,
) -> SmartObjectInfo:
    """Find a SmartObject layer.

    - If ``layer_name`` is given → exact case-sensitive lookup (Phase A).
    - If ``layer_name`` is ``None`` → auto-detect per Sprint P24 rules.

    Raises:
        NoSmartObjectError: layer missing or not a Smart Object.
        AmbiguousLayerError: auto-detect cannot pick a single layer.
    """
    if layer_name is not None:
        return _locate_by_exact_name(psd, layer_name)
    return _auto_detect(psd)

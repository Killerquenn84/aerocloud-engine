"""Composite background + warped design + overlay layers (BDD scenarios 7-8)."""
from __future__ import annotations

from PIL import Image
from psd_tools import PSDImage
from psd_tools.api.layers import Layer, SmartObjectLayer


def _iter_top_level(psd: PSDImage) -> list[Layer]:
    """Top-level layer list (groups stay grouped, but rendered via composite())."""
    return list(psd)


def _layer_contains(layer: Layer, target: Layer) -> bool:
    """Return True if `target` is `layer` itself or nested anywhere beneath it."""
    if layer is target:
        return True
    if hasattr(layer, "__iter__"):
        for child in layer:
            if _layer_contains(child, target):
                return True
    return False


def _composite_visible_subset(
    psd: PSDImage,
    include: list[Layer],
) -> Image.Image:
    """Composite only the given top-level layers — others temporarily hidden."""
    saved: dict[int, bool] = {}
    try:
        for layer in _iter_top_level(psd):
            saved[id(layer)] = layer.visible
            layer.visible = layer in include
        result = psd.composite(force=True)
        if result is None:
            result = Image.new("RGBA", (psd.width, psd.height), (0, 0, 0, 0))
        if result.mode != "RGBA":
            result = result.convert("RGBA")
        return result
    finally:
        for layer in _iter_top_level(psd):
            if id(layer) in saved:
                layer.visible = saved[id(layer)]


def render_composite(
    psd: PSDImage,
    warped_design: Image.Image,
    smart_layer: SmartObjectLayer,
) -> Image.Image:
    """Composite the final mockup PNG.

    Layer order: top-level layers BELOW the smart-object (background) → warped
    design → top-level layers ABOVE the smart-object (overlays). The top-level
    container holding the smart object itself is dropped (its smart-object
    content is replaced; sibling shapes inside the same group, if any, are
    intentionally skipped in Phase A — designers should put overlays in
    separate top-level groups per the PSD conventions doc).
    """
    top_levels = _iter_top_level(psd)

    container_idx: int | None = None
    for idx, layer in enumerate(top_levels):
        if _layer_contains(layer, smart_layer):
            container_idx = idx
            break
    if container_idx is None:
        raise ValueError("smart_layer is not contained in the PSD's top-level tree")

    background = top_levels[:container_idx]
    overlays = top_levels[container_idx + 1 :]

    canvas_size = (psd.width, psd.height)
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))

    if background:
        bg_img = _composite_visible_subset(psd, background)
        canvas = Image.alpha_composite(canvas, bg_img)

    if warped_design.size != canvas_size:
        raise ValueError(
            f"warped_design size {warped_design.size} != canvas {canvas_size}"
        )
    if warped_design.mode != "RGBA":
        warped_design = warped_design.convert("RGBA")
    canvas = Image.alpha_composite(canvas, warped_design)

    if overlays:
        ov_img = _composite_visible_subset(psd, overlays)
        canvas = Image.alpha_composite(canvas, ov_img)

    return canvas


def render_background_only(
    psd: PSDImage,
    warped_design: Image.Image,
    smart_layer: SmartObjectLayer,
) -> Image.Image:
    """Graceful-degradation fallback (Sprint P26 scenario 8).

    Composites *only* the background layers + warped design. Any overlay
    layers above the smart object are intentionally skipped, so a corrupt
    Frame/Glare/Shadow layer can no longer break the render. Output is
    visibly degraded but always produced.
    """
    top_levels = _iter_top_level(psd)

    container_idx: int | None = None
    for idx, layer in enumerate(top_levels):
        if _layer_contains(layer, smart_layer):
            container_idx = idx
            break
    if container_idx is None:
        raise ValueError("smart_layer is not contained in the PSD's top-level tree")

    background = top_levels[:container_idx]
    canvas_size = (psd.width, psd.height)
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))

    if background:
        bg_img = _composite_visible_subset(psd, background)
        canvas = Image.alpha_composite(canvas, bg_img)

    if warped_design.size != canvas_size:
        raise ValueError(
            f"warped_design size {warped_design.size} != canvas {canvas_size}"
        )
    if warped_design.mode != "RGBA":
        warped_design = warped_design.convert("RGBA")
    canvas = Image.alpha_composite(canvas, warped_design)

    return canvas

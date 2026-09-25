"""Perspective-warp helpers (BDD scenarios 5-6)."""
from __future__ import annotations

from typing import Literal

import cv2
import numpy as np
from PIL import Image

from .smart_object import TransformBox

FitMode = Literal["stretch"]


def warp_to_box(
    design: Image.Image,
    transform_box: TransformBox,
    canvas_size: tuple[int, int],
    fit_mode: FitMode = "stretch",
) -> Image.Image:
    """Warp a design image onto the 4-point transform_box of the PSD canvas.

    Args:
        design: Source design (PIL RGBA). If not RGBA, it is converted.
        transform_box: (x1,y1, x2,y2, x3,y3, x4,y4) — TL, TR, BR, BL.
        canvas_size: (width, height) of the target PSD canvas.
        fit_mode: only "stretch" implemented in Phase A — design fills the box.

    Returns:
        RGBA PIL.Image at canvas_size with the design warped to the box and
        all other pixels fully transparent (alpha=0).
    """
    if fit_mode != "stretch":
        raise NotImplementedError(f"fit_mode={fit_mode!r} not implemented in Phase A")

    if design.mode != "RGBA":
        design = design.convert("RGBA")

    src_w, src_h = design.size
    canvas_w, canvas_h = canvas_size

    src_pts = np.float32(
        [
            [0, 0],
            [src_w, 0],
            [src_w, src_h],
            [0, src_h],
        ]
    )
    dst_pts = np.float32(
        [
            [transform_box[0], transform_box[1]],
            [transform_box[2], transform_box[3]],
            [transform_box[4], transform_box[5]],
            [transform_box[6], transform_box[7]],
        ]
    )

    matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
    design_np = np.array(design)  # H,W,4 uint8
    warped = cv2.warpPerspective(
        design_np,
        matrix,
        (canvas_w, canvas_h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    return Image.fromarray(warped, mode="RGBA")

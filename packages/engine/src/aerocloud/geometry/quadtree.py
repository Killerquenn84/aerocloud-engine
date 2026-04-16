"""Quadtree spatial index for Stage 3 collision broadphase (D-08, GEO2-05).

Pure Python recursive quadtree over (N, 4) int32 AABB arrays. Splits a node
into 4 equal children when the item count exceeds ``split_threshold`` AND the
current depth is below ``max_depth``. The ``max_depth`` guard prevents infinite
subdivision on duplicate or heavily-overlapping AABBs (T-07-02-03).

Coordinate convention: (y, x) canonical ordering (D-14).
Column order: y_min, x_min, y_max, x_max.
Half-open intervals: [y_min, y_max) x [x_min, x_max).

References:
    - D-08: Quadtree (Stage 3) in new geometry/quadtree.py.
    - GEO2-05: Pure Python recursive quadtree; max_depth 8 recommended default.
    - T-07-02-03: depth < max_depth guard in _split_node prevents infinite split.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class QuadtreeNode:
    """A node in a 2-D quadtree spatial index.

    Each node covers a rectangular canvas region ``bounds = (y0, x0, y1, x1)``
    and stores a list of ``(index, aabb)`` pairs for all AABBs that intersect
    this region.

    An internal node has ``children`` set to a 4-element list (NW, NE, SW, SE).
    A leaf node has ``children = None``.

    Splitting occurs when ``len(items) >= split_threshold`` and
    ``depth < max_depth``.  When ``depth >= max_depth`` items accumulate in the
    leaf without further subdivision (T-07-02-03 mitigation).
    """

    bounds: tuple[int, int, int, int]  # (y0, x0, y1, x1) — inclusive min, exclusive max
    items: list[tuple[int, np.ndarray]] = field(default_factory=list)
    children: list[QuadtreeNode] | None = None
    depth: int = 0


def build_quadtree(
    bounds: tuple[int, int, int, int],
    max_depth: int = 8,  # noqa: ARG001 — stored in node for caller reference
    split_threshold: int = 8,  # noqa: ARG001 — stored in node for caller reference
) -> QuadtreeNode:
    """Create an empty quadtree root covering ``bounds``.

    Args:
        bounds: Canvas region ``(y0, x0, y1, x1)`` that the root covers.
        max_depth: Maximum subdivision depth (default 8 per GEO2-05). Passed
            to ``insert_aabb`` / ``_split_node`` at insert time — not stored
            on the root node itself.
        split_threshold: Minimum item count before a node splits (default 8).
            Passed to ``insert_aabb`` at insert time.

    Returns:
        An empty ``QuadtreeNode`` with no items and no children.
    """
    return QuadtreeNode(bounds=bounds, depth=0)


def _bounds_overlap(
    ay0: int, ax0: int, ay1: int, ax1: int,
    by0: int, bx0: int, by1: int, bx1: int,
) -> bool:
    """Return True iff two half-open rectangles overlap."""
    return ay0 < by1 and by0 < ay1 and ax0 < bx1 and bx0 < ax1


def _split_node(
    node: QuadtreeNode,
    max_depth: int,
    split_threshold: int,
) -> None:
    """Split ``node`` into 4 equal quadrant children and redistribute items.

    Creates NW, NE, SW, SE child nodes. Each existing item is reinserted into
    all children whose bounds intersect the item's AABB (an AABB may appear in
    multiple children if it straddles a quadrant boundary).

    Args:
        node: The node to split. Must be a leaf (``node.children is None``).
        max_depth: Passed through to recursive ``insert_aabb`` calls.
        split_threshold: Passed through to recursive ``insert_aabb`` calls.
    """
    y0, x0, y1, x1 = node.bounds
    y_mid = (y0 + y1) // 2
    x_mid = (x0 + x1) // 2

    # Guard: avoid creating zero-size children on very small bounds (T-07-02-03)
    if y_mid in (y0, y1) or x_mid in (x0, x1):
        return  # Cannot split further — stay as leaf

    node.children = [
        QuadtreeNode(bounds=(y0, x0, y_mid, x_mid), depth=node.depth + 1),  # NW
        QuadtreeNode(bounds=(y0, x_mid, y_mid, x1), depth=node.depth + 1),  # NE
        QuadtreeNode(bounds=(y_mid, x0, y1, x_mid), depth=node.depth + 1),  # SW
        QuadtreeNode(bounds=(y_mid, x_mid, y1, x1), depth=node.depth + 1),  # SE
    ]

    # Redistribute existing items into children
    saved_items = node.items
    node.items = []
    for idx, aabb in saved_items:
        for child in node.children:
            cy0, cx0, cy1, cx1 = child.bounds
            ay0, ax0, ay1, ax1 = int(aabb[0]), int(aabb[1]), int(aabb[2]), int(aabb[3])
            if _bounds_overlap(ay0, ax0, ay1, ax1, cy0, cx0, cy1, cx1):
                insert_aabb(child, idx, aabb, max_depth, split_threshold)


def insert_aabb(
    node: QuadtreeNode,
    idx: int,
    aabb: np.ndarray,
    max_depth: int = 8,
    split_threshold: int = 8,
) -> None:
    """Insert AABB ``aabb`` with index ``idx`` into the quadtree.

    If ``aabb`` does not intersect this node's bounds it is silently ignored.
    If the node has children, the AABB is forwarded to all children it
    overlaps.  If the node is a leaf and its item count reaches
    ``split_threshold`` and ``depth < max_depth``, the node is split first.

    Args:
        node: Root (or sub-root) of the quadtree to insert into.
        idx: Integer index into the original AABB array.
        aabb: Shape ``(4,)`` int32 AABB — ``(y_min, x_min, y_max, x_max)``.
        max_depth: Maximum subdivision depth (T-07-02-03 guard).
        split_threshold: Split when ``len(items) >= split_threshold`` and
            ``depth < max_depth``.
    """
    ny0, nx0, ny1, nx1 = node.bounds
    ay0, ax0, ay1, ax1 = int(aabb[0]), int(aabb[1]), int(aabb[2]), int(aabb[3])

    # Skip if AABB does not intersect this node's region
    if not _bounds_overlap(ay0, ax0, ay1, ax1, ny0, nx0, ny1, nx1):
        return

    # Internal node: forward to children
    if node.children is not None:
        for child in node.children:
            insert_aabb(child, idx, aabb, max_depth, split_threshold)
        return

    # Leaf node: store the item
    node.items.append((idx, aabb))

    # Split if threshold reached and depth allows
    if len(node.items) >= split_threshold and node.depth < max_depth:
        _split_node(node, max_depth, split_threshold)


def query_region(node: QuadtreeNode, region: np.ndarray) -> list[int]:
    """Return indices of all AABBs that overlap ``region``.

    Recursive traversal: prune subtrees whose bounds do not overlap ``region``.
    At leaf nodes, check each stored AABB against ``region`` (half-open
    interval semantics — no false negatives).

    Args:
        node: Root of the quadtree to query.
        region: Shape ``(4,)`` int32 AABB — ``(y_min, x_min, y_max, x_max)``.

    Returns:
        List of integer indices. May contain duplicates when an AABB spans
        multiple quadrant children (deduplicate at call site if needed).
    """
    ny0, nx0, ny1, nx1 = node.bounds
    ry0, rx0, ry1, rx1 = int(region[0]), int(region[1]), int(region[2]), int(region[3])

    # Prune: if region does not overlap this node's bounds, skip
    if not _bounds_overlap(ry0, rx0, ry1, rx1, ny0, nx0, ny1, nx1):
        return []

    # Internal node: recurse into children
    if node.children is not None:
        result: list[int] = []
        for child in node.children:
            result.extend(query_region(child, region))
        return result

    # Leaf node: check each stored AABB
    hits: list[int] = []
    for idx, aabb in node.items:
        ay0, ax0, ay1, ax1 = int(aabb[0]), int(aabb[1]), int(aabb[2]), int(aabb[3])
        if _bounds_overlap(ay0, ax0, ay1, ax1, ry0, rx0, ry1, rx1):
            hits.append(idx)
    return hits


__all__ = [
    "QuadtreeNode",
    "build_quadtree",
    "insert_aabb",
    "query_region",
]

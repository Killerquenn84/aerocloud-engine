# Phase 7: Geometry-v2 - Discussion Log (Assumptions Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-04-15
**Phase:** 07-geometry-v2
**Mode:** assumptions (--auto)
**Areas analyzed:** MAT Construction/Pruning, Collision Pipeline, Multi-Centric Placement, Bezier Paths

## Assumptions Presented

### MAT Construction and Pruning
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| MAT from SDF ridge, scikit-fmm for travel-time only | Likely | geometry/sdf.py exact EDT, FEATURES.md §5 |
| Pruning: radius threshold + CAT cleanup | Likely | FEATURES.md "major hurdle", D-42 budget pattern |

### Collision Pipeline
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Extend collision.py with new functions (D-02 lock) | Confident | collision.py function-based, D-02 locked |
| BVH as pure numpy binary tree + LRU cache | Likely | sdf_cache.py pattern, no rtree in pyproject.toml |

### Multi-Centric Placement
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Pre-pass partitions words to branches, reuses place_words per branch | Likely | placement.py modular helpers, D-38 per-word POI |

### Bezier Paths
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Per-glyph from pixel_buffer via OpenCV contours | Likely | GlyphBBox.pixel_buffer, opencv-headless in extras |

## Corrections Made

No corrections — all assumptions auto-confirmed (--auto mode).

## Auto-Resolved

- MAT Construction: auto-selected recommended (SDF ridge + scikit-fmm travel-time)
- MAT Pruning: auto-selected combined approach (radius pre-filter + CAT topology)
- BVH: auto-selected pure numpy + LRU pattern
- Multi-Centric: auto-selected pre-pass partition approach
- Bezier: auto-selected per-glyph OpenCV contour approach

## External Research Needed

1. scikit-fmm API for travel-time on masked domain (float32 compatibility)
2. Chordal Axis Transform implementation options in Python
3. EdWordle BVH split heuristic specifics
4. SAT gradient interaction — resolved: non-differentiable, geometry-only

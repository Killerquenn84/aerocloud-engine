# aerocloud-engine

Core Python engine for the AeroCloud self-learning word cloud rendering system. Implements the mathematical Blueprint: Zipf-normalized TF-IDF, BERT embeddings, Sinkhorn-Knopp Optimal Transport, SDF/MAT geometry, differentiable soft-rasterization, MAP-Elites Quality-Diversity, and sub-millimeter vector export.

## Module Layout

- `aerocloud.nlp` — TF-IDF-AP, Zipf normalization, spaCy tokenization (Phase 3)
- `aerocloud.geometry` — SDF, MAT, collision detection (Phases 4 + 7)
- `aerocloud.renderer` — PyTorch differentiable rasterizer (Phase 5)
- `aerocloud.optimizer` — Adam inner loop, MAP-Elites outer loop (Phases 6, 9, 11)
- `aerocloud.export` — Seam carving, Bezier SVG/PDF (Phase 12)
- `aerocloud.utils` — Determinism, config, logging, fonts (Phase 1 Foundation)

## Install

```bash
uv sync --package aerocloud-engine
```

For phase-specific optional dependencies:

```bash
uv sync --extra geometry    # Phase 4
uv sync --extra nlp         # Phase 3
uv sync --extra embeddings  # Phase 8
uv sync --extra gpu         # Phase 5 (requires CUDA toolchain for nvdiffrast)
uv sync --extra qd          # Phase 9
```

## Phase Status

| Module | Phase | Status |
|--------|-------|--------|
| utils (determinism, config, logging, fonts) | 1 | In Progress |
| nlp | 3 | Planned |
| geometry-v1 | 4 | Planned |
| renderer-v1 | 5 | Planned |
| optimizer-v1 (Adam) | 6 | Planned |
| geometry-v2 (MAT + full collision) | 7 | Planned |
| semantic vector (BERT + OT) | 8 | Planned |
| outer-loop-v1 (MAP-Elites) | 9 | Planned |
| self-play | 10 | Planned |
| outer-loop-v2 (BOP-Elites + CQD) | 11 | Planned |
| export + production | 12 | Planned |

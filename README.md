# AeroCloud Engine

Self-learning Word Cloud Engine with Quality-Diversity Optimization.

## Architecture

**Dual-Loop-Paradigma:**
- **Inner Loop (Exploitation):** PyTorch GPU-based Differentiable Rendering
- **Outer Loop (Exploration):** CQD-Metrik + MAP-Elites Self-Play

## LLM Wiki (Karpathy Pattern)

This project maintains a self-evolving knowledge base:

```
raw/sources/    → Immutable source documents
wiki/           → LLM-maintained markdown wiki
CLAUDE.md       → Schema and conventions
```

### Wiki Commands

```bash
npm run wiki:ingest raw/sources/paper.md   # Process new source
npm run wiki:query "optimal transport"      # Query knowledge base
npm run wiki:lint                           # Health-check wiki
```

## Development

```bash
npm install
npm run dev          # Start dev server
npm test             # Run tests
npm run typecheck    # TypeScript check
```

## Project Structure

```
src/nlp/         → TF-IDF-AP, Tokenization, BERT Embeddings
src/geometry/    → SDF, MAT, Quadtree, Collision Detection
src/renderer/    → Differentiable Rendering, Soft-Rasterization
src/optimizer/   → Adam, CQD Metric, MAP-Elites, BOP-Elites
src/export/      → Seam Carving, Bezier Export, SVG/PDF
scripts/         → Wiki tooling (ingest, query, lint)
wiki/            → Knowledge base (LLM-maintained)
raw/sources/     → Source documents (immutable)
```

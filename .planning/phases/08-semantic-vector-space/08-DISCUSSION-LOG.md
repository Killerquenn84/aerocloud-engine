# Phase 8: Semantic Vector Space - Discussion Log (Assumptions Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-04-18
**Phase:** 08-semantic-vector-space
**Mode:** assumptions (--auto)
**Areas analyzed:** BERT Integration, Cosine/Projection, Sinkhorn-Knopp, Warm-Start, pgvector Persistence

## Assumptions Presented

### BERT Embedding Integration Point
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Embed WordCandidate.surface strings via all-MiniLM-L6-v2 → (N, 384) float32 | Confident | nlp/pipeline.py WordCandidate model, pyproject.toml sentence-transformers dep, wiki/bert-embeddings.md 384-dim, archive_v1 vector(384) |

### Sinkhorn Output as InnerLoop Warm-Start
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| External semantic_warm_start() → (N, 4) params tensor, no InnerLoop API changes | Likely | renderer/_renderer.py params_n4 arg, inner_loop.py consumes renderer.params, ROADMAP "replaces Force-Directed init" |

### pgvector Persistence Scope
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| New word_embeddings table for per-word embedding cache, not archive_v1 | Unclear → auto-resolved | archive_v1 designed for MAP-Elites entries (bin_id), not vocabulary. SEM-07 says "BERT embeddings persisted" = individual word vectors |

### t-SNE vs UMAP Choice
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| UMAP primary, t-SNE fallback. Add umap-learn dep. | Likely | wiki/bert-embeddings.md "UMAP bevorzugt", determinism requirement, sklearn TSNE already available |

## Corrections Made

No corrections — all assumptions auto-resolved with recommended defaults.

## Auto-Resolved

- pgvector Persistence (Unclear → Alt 2): New word_embeddings table — caching individual word embeddings is the correct interpretation of SEM-07
- Sinkhorn Warm-Start (Likely → Alt 1): External function, no InnerLoop API changes
- UMAP vs t-SNE (Likely → Alt 1): UMAP primary with umap-learn dependency

## External Research Flagged

- POT log-space Sinkhorn API compatibility with pinned version range
- umap-learn cp311 wheels + numba/llvmlite compatibility with Python >=3.11,<3.12
- sentence-transformers model caching and offline deployment
- Sinkhorn cost matrix construction: word-to-position vs cluster-to-segment

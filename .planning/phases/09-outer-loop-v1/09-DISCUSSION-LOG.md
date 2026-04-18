# Phase 9: Outer Loop-v1 - Discussion Log (Assumptions Mode)

> **Audit trail only.** Decisions captured in CONTEXT.md.

**Date:** 2026-04-18
**Phase:** 09-outer-loop-v1
**Mode:** assumptions (--auto)
**Areas analyzed:** pyribs Archive, Fitness Function, Archive Persistence, Novelty/Monitoring

## Assumptions Presented

### pyribs Archive Type
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| GridArchive with 4 behavioral dims, 10 bins/dim | Likely | BehaviorDescriptor model, Blueprint Teil VIII, pyribs 0.9.0 |

### Fitness Function
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Composite quality metrics, not raw loss | Confident | OUTER-03 metrics list, Phase 6 D-01, CQD Phase 11 |

### Archive Persistence
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Extend archive_v1 + batch flush pattern | Likely | 0001_baseline.py, Phase 8 D-15, asyncpg pattern |

### Sync Pattern
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| In-memory primary, batch PostgreSQL flush | Likely | pyribs numpy backend, OUTER-05 ON CONFLICT |

## Auto-Resolved
- GridArchive (Likely → Alt 1): uniform bins, matches Blueprint
- Archive persistence (Likely → Alt 1): extend archive_v1 with new columns
- Sync pattern (Likely → Alt 1): batch flush every 100 evals

## External Research Flagged
- pyribs 0.9.0 GridArchive API + emitter selection
- Novelty search integration with pyribs
- Quality metric standard formulas (LC, LU, SS, Compactness)

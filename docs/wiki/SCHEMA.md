# AeroCloud Wiki Schema

## Page Format

Every wiki page uses YAML frontmatter:

```yaml
---
title: Page Title
tags: [tag1, tag2]
sources: [source-file.md]
updated: YYYY-MM-DD
---
```

## Operations

### Ingest
1. Place source in raw/sources/
2. Run: npm run wiki:ingest raw/sources/file.md
3. Updates: wiki page + index.md + log.md

### Query
1. Run: npm run wiki:query "search term"
2. Reads index, matches pages, outputs content

### Lint
1. Run: npm run wiki:lint
2. Checks: frontmatter, broken links, orphan pages, cross-references

## Nightly Deep Research (2:00-5:00 AM Berlin)
- Search internet for new papers, techniques, implementations
- Update relevant wiki pages with findings
- Append to log.md with timestamp and sources

## Categories
1. Engine — Core algorithms (SDF, MAT, Collision, Rendering)
2. Architecture — System design, infrastructure, microservices
3. Optimization — CQD, MAP-Elites, BOP-Elites, Adam
4. NLP — TF-IDF, BERT, Optimal Transport, Embeddings
5. Export — Seam Carving, Bezier, SVG/PDF
6. Quality — Metrics, testing, benchmarks
7. Research — Papers, state-of-art, competitive analysis

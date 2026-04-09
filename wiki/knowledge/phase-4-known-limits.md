# Phase 4 Geometry-v1 — Known Limitations (carried forward to Phase 7/12)

## place_words performance on VPS hardware (accepted v1 limit)

Measured on Hostinger shared 4-vCPU VPS 2026-04-09:
- compute_sdf 2048×2048: 0.588s mean (budget <1.0s) PASS
- place_words 100 words @ 1024×1024: 24.85s mean (budget originally 5.0s, retired to 60s)

Root cause: `scipy.ndimage.minimum_filter` on 1024×1024 canvas per word
(~0.25s × 100 words = 25s total). RESEARCH.md §12 R-6 predicted this before
implementation began.

Mitigation paths deferred to Phase 7 Geometry-v2:
1. Coarse-to-fine search: minimum_filter on 2-4x downsampled SDF, refine in
   small neighborhood (Gemini's recommendation, expected 6-12s on VPS)
2. Integral-occupancy map (amueller/word_cloud style, noted in CONTEXT.md
   deferred ideas)
3. Narrow the feasibility search region to a bounding box around the eps-band
   of the SDF (R-6 mitigation)

Validation status: Wave 5 3-KI review (2026-04-09):
- Claude APPROVED for v1 (algorithm correct, VPS not production hardware)
- Codex BLOCKED (phase exits against 5.0s contract)
- Gemini BLOCKED (hardware speedup insufficient, algorithmic fix required)

Jens approved retirement of the 5.0s gate to 60s (VPS ceiling) with explicit
re-validation planned at Phase 12 on production hardware (Celery worker with
GPU). The 60s ceiling is a regression guard — any commit that pushes above 60s
on the VPS is a performance regression that must be investigated.

## FreeType pin — transitional bypass removed (resolved in Wave 5)

The `AEROCLOUD_SKIP_FREETYPE_CHECK` env bypass and `conftest.py` monkeypatches
that masked a FreeType version mismatch during Phase 4 execution have been
removed in Wave 5 3-KI review. The pin is now 2.14.3, matching server reality
and golden corpus fixtures. This item is RESOLVED, documented here for audit
trail.

See: `.planning/phases/04-geometry-v1/adr-0006-freetype-pinning.md` (v2)

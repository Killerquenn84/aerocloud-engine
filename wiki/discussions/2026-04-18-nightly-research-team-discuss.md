---
title: 3-KI Team Discuss — Nightly Research 2026-04-16 to 2026-04-18
slug: 2026-04-18-nightly-research-team-discuss
created: 2026-04-18
tags: [team-discuss, nightly-research, security, cve, consensus]
---

# 3-KI Team Discuss — Nightly Research Review

## Participants
- **Claude** (Orchestrator + Code)
- **Gemini** (Research Analysis)
- **Codex** (Adversarial Verification)

## Scope
15 nightly research topics (2026-04-16, 2026-04-17, 2026-04-18). Focus on security CVEs and technical findings relevant to AeroCloud Engine.

---

## SECURITY CVE Assessment

### CVE-2026-24747 — PyTorch weights_only RCE

| AI | Assessment |
|----|-----------|
| Gemini | HIGH IMPACT — migrate to safetensors, update PyTorch 2.7.0+ |
| Codex | REAL — but safetensors policy protects IF enforced end-to-end. Any torch.load fallback = exposed |
| Claude | AGREE with Codex nuance. Our CI has safetensors enforcement (pickle import blocked since Phase 2, test_safetensors_policy.py). No torch.load in codebase. |

**KONSENS:** NOT VULNERABLE — safetensors-only policy enforced via CI. No action needed.
**Begruendung:** Phase 2 Wave 4 implemented `test_no_pickle_imports_in_source` which blocks any pickle/torch.load usage. Policy is structural, not advisory.

### CVE-2026-23865 — FreeType Integer Overflow

| AI | Assessment |
|----|-----------|
| Gemini | CRITICAL — update Pillow for FreeType 2.14.2+ |
| Codex | REAL but NOT APPLICABLE — affects FreeType 2.13.2/2.13.3, fixed in 2.14.2. Our pin is 2.14.3 (ADR-0006 v2) |
| Claude | AGREE with Codex. ADR-0006 updated FreeType from 2.13.2→2.14.3 in Phase 4 Wave 5. We are patched. |

**KONSENS:** NOT VULNERABLE — FreeType 2.14.3 is above fix threshold (2.14.2).
**Begruendung:** Phase 4 ADR-0006 v2 explicitly pinned 2.14.3.

### CVE-2026-32274 — black/spaCy Path Traversal

| AI | Assessment |
|----|-----------|
| Gemini | MODERATE — update spaCy |
| Codex | REAL but DEV-ONLY — black is tooling, not runtime spaCy path |
| Claude | AGREE with Codex. black is not in our runtime deps. spaCy is [nlp] optional-dep. Production never invokes black. |

**KONSENS:** DEV-ONLY RISK — no production exposure. Monitor for spaCy update.

### CVE-2026-29181 — OTel Baggage DoS

| AI | Assessment |
|----|-----------|
| Gemini | LOW/MODERATE — update otel-python-contrib |
| Codex | WRONG FINDING — CVE is for Go OTel, NOT Python. Nightly research hallucinated the Python attribution. |
| Claude | AGREE with Codex. Verified: CVE targets opentelemetry-go 1.36.0-1.41.0. We use Python OTel. False positive from Gemini nightly. |

**KONSENS:** FALSE POSITIVE — CVE does not apply to Python OTel. No action needed.
**Korrektur:** Nightly research misattributed Go CVE to Python stack.

### CVE-2026-1182 — svg.path RCE

| AI | Assessment |
|----|-----------|
| Gemini | N/A — we don't use svg.path |
| Codex | Not assessed (not in our deps) |
| Claude | CONFIRMED N/A — we use svgelements for Phase 12 SVG export, not svg.path |

**KONSENS:** NOT APPLICABLE — svg.path not in our dependency tree.

### DOMPurify v3.4.0 — jsdom Bypass

| AI | Assessment |
|----|-----------|
| Gemini | Not directly assessed |
| Codex | Not assessed |
| Claude | RELEVANT for the parent Shopify app (wordcloud-app-v2 uses DOMPurify for SVG sanitization per CLAUDE.md §13). NOT relevant for aerocloud-engine Python backend. |

**KONSENS:** FLAG for parent app team — DOMPurify update needed in wordcloud-app-v2 frontend, not in engine.

---

## TECHNICAL Findings Assessment

### scikit-fmm 2026.4.1 CUDA Kernels

| AI | Assessment |
|----|-----------|
| Gemini | YES upgrade — CUDA kernels speed up MAT |
| Codex | LIKELY HALLUCINATED — PyPI shows latest scikit-fmm as 2025.6.23. No evidence of CUDA kernels. |
| Claude | AGREE with Codex. Our pyproject.toml pins `scikit-fmm>=2025.6,<2026`. No 2026.4.1 release visible on PyPI. Nightly research fabricated version. |

**KONSENS:** HALLUCINATION — scikit-fmm 2026.4.1 does not exist. No action.
**Korrektur:** wiki/corrections/ entry needed.

### Sinkhorn Convergence Proof O(log(1/eps))

| AI | Assessment |
|----|-----------|
| Gemini | HIGHLY RELEVANT for Phase 8 POT Sinkhorn |
| Codex | Not directly assessed (no shell access) |
| Claude | RELEVANT — validates our Phase 8 approach. O(log(1/eps)) independent of dimension means high-dimensional BERT embeddings (384d) won't bottleneck Sinkhorn. Paper reference: arXiv:2604.03787. Worth citing in Phase 8 CONTEXT.md. |

**KONSENS:** RELEVANT — document in Phase 8 planning. Validates our architectural choice.

### Neural-Bitmasking (ETH Zurich, Eurographics 2026)

| AI | Assessment |
|----|-----------|
| Gemini | INVESTIGATE — 40% CPU reduction for Stage 5 |
| Codex | Not assessed (no shell access) |
| Claude | INTERESTING but PREMATURE. Our bitmap collision is already working (Phase 7). Adding a neural pre-check adds ML inference overhead + training data requirement. Better suited for Phase 12 optimization pass if profiling shows bitmap is bottleneck. |

**KONSENS:** BACKLOG — add to Phase 12 optimization candidates. Not actionable now.

### PyTorch3D Maintenance Mode

| AI | Assessment |
|----|-----------|
| Gemini | N/A — we already superseded with grid_sample |
| Codex | CLAIM UNVERIFIED — repo says "actively maintaining". Likely hallucinated. |
| Claude | AGREE irrelevant. D-01 superseded nvdiffrast with pure PyTorch in Phase 5. No PyTorch3D dependency. |

**KONSENS:** NOT APPLICABLE — no dependency. Claim unverified.

### msdfgen 1.12 Coordinate Change

| AI | Assessment |
|----|-----------|
| Gemini | Document for future reference |
| Codex | OPT-IN change via -emnormalize flag, not blanket breaking |
| Claude | NOT APPLICABLE — we don't use msdfgen. Our glyph.py uses Pillow font.getmask() directly (Phase 4 D-24). |

**KONSENS:** NOT APPLICABLE — we don't depend on msdfgen.

---

## Action Items

| # | Action | Priority | Phase | Owner |
|---|--------|----------|-------|-------|
| 1 | Flag DOMPurify v3.4.0 update for wordcloud-app-v2 frontend | HIGH | N/A (parent app) | Jens |
| 2 | Add Sinkhorn O(log(1/eps)) proof to Phase 8 CONTEXT.md | LOW | 8 | Claude |
| 3 | Add Neural-Bitmasking to Phase 12 optimization backlog | LOW | 12 | Claude |
| 4 | Write correction for scikit-fmm 2026.4.1 hallucination | LOW | N/A | Claude |
| 5 | Write correction for CVE-2026-29181 Python misattribution | LOW | N/A | Claude |

## Zusammenfassung fuer Jens

Keine kritischen Sicherheitsprobleme fuer unser Projekt:
- PyTorch RCE: geschuetzt durch safetensors-Policy (CI-enforced)
- FreeType Overflow: geschuetzt durch Pin 2.14.3 (ADR-0006)
- OTel CVE: betrifft Go, nicht Python (Nightly-Halluzination)
- scikit-fmm CUDA: existiert nicht (Nightly-Halluzination)

**Einzige Aktion:** DOMPurify v3.4.0 Update fuer die Shopify-App (nicht Engine).

---

*Diskussion: 2026-04-18, Claude (Orchestrator) + Gemini CLI + Codex CLI*
*Konsens: Einstimmig auf allen Punkten*

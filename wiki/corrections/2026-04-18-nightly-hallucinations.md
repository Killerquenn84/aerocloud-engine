---
title: Nightly Research Hallucinations — 2026-04-16 to 2026-04-18
slug: 2026-04-18-nightly-hallucinations
created: 2026-04-18
tags: [correction, hallucination, nightly-research]
---

# Nightly Research Hallucinations (April 16-18 2026)

Codex adversarial review entlarvte 2 Halluzinationen in Gemini Nightly Research.

## 1. scikit-fmm 2026.4.1 mit CUDA Kernels

**Behauptung (2026-04-17):** scikit-fmm 2026.4.1 drops Python 3.9, adds optimized CUDA kernels for distance fields.

**Realitaet:** PyPI zeigt scikit-fmm latest als 2025.6.23. Kein Release 2026.4.1. Keine CUDA-Kernel-Unterstuetzung in scikit-fmm. Die Behauptung ist komplett fabriziert.

**Quelle:** Codex Verifikation via PyPI Metadaten.

## 2. CVE-2026-29181 Python OTel Attribution

**Behauptung (2026-04-16):** CVE-2026-29181 (High) DoS via baggage header extraction in otel-python-contrib.

**Realitaet:** CVE-2026-29181 betrifft **opentelemetry-go** v1.36.0 bis v1.41.0, NICHT Python. Ubuntu CVE page und Debian tracker bestaetigen: Go-only. Nightly Research hat die Sprache falsch zugeordnet.

**Quelle:** Codex Verifikation via NVD, Ubuntu Security, Debian Tracker.

---

*Entdeckt: 2026-04-18 Team Discuss (Claude + Codex + Gemini)*
*Regel 7 Anti-Sycophancy: Codex hat beide Halluzinationen entlarvt, Gemini hat sie produziert.*

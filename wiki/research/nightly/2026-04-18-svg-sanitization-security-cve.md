---
title: "Nightly Research: SVG Sanitization Security CVE"
slug: 2026-04-18-svg-sanitization-security-cve
created: 2026-04-18
tags: [nightly, research, gemini, automated]
source: automated-nightly-cron
topic: "SVG Sanitization Security CVE"
---

# Nightly Research: SVG Sanitization Security CVE

**Datum:** 2026-04-18
**Automatisch erzeugt von:** scripts/nightly-research.sh
**Modell:** Gemini CLI

## Query

```
AeroCloud Engine Thema: SVG Sanitization Security CVE. Was ist neu seit gestern? Welche neuen Papers, Libraries, Best Practices, CVEs oder Breaking Changes sind seit April 2026 erschienen? Antworte kompakt auf Deutsch mit Datum-Verweis und konkreten Quellen (URLs oder Paper-Titel). Max 400 Worte. Falls nichts Neues: sag das ehrlich.
```

## Gemini Response

Seit gestern (17. April 2026) und in der unmittelbar laufenden Woche gab es signifikante Entwicklungen im Bereich SVG-Security, die für die AeroCloud Engine relevant sind:

### 1. Neue CVEs & Patches (Stand 18.04.2026)
*   **CVE-2026-25133 (October CMS):** Ein kritischer Bypass der SVG-Sanitization wurde gestern final dokumentiert. Angreifer konnten durch gezielte Regex-Manipulation `on*`-Eventhandler (wie `onload`) einschleusen. **Fix:** Update auf v3.7.14 / v4.1.10 zwingend erforderlich.
*   **CVE-2026-6216 (DbGate):** XSS-Lücke im Icon-String-Handler von DbGate (v7.1.4). Betrifft Anwendungen, die SVG-Icons dynamisch rendern.
*   **CVE-2026-22610 (Angular 19):** Da Angular 19 am 19. Mai 2026 EOL geht, wurde gestern ein "Mandatory Security Patch" (v19.2.18) veröffentlicht, der spezifische Script-Injection-Bypässe in SVGs schließt.

### 2. Library-Updates & Breaking Changes
*   **DOMPurify v3.4.0 (Release diese Woche):** Behebt einen kritischen Bypass im Zusammenspiel mit **jsdom** (fehlerhaftes Raw-Text Tag-Parsing) sowie eine Prototype Pollution Schwachstelle bei Custom Elements. Ein Update ist für alle Backend-Sanitizer auf Node.js-Basis dringend empfohlen.
*   **is-svg v6.0.0:** Diese Woche in Großprojekte (z.B. Nextcloud 33.0.2) integriert. Führt striktere Validierungsregeln ein, die ältere SVGs mit proprietären Namespaces als "invalid" ablehnen (Breaking Change).

### 3. Neue Forschung & Supply Chain
*   **OX Security Report (15.04.2026):** "The Mother of All AI Supply Chains". Der Report warnt vor RCE-Lücken im **Model Context Protocol (MCP)**. Maliziöse SVGs werden hier als "Zero-Click"-Vektor in AI-gestützten IDEs identifiziert, um Prompt Injections auszulösen.
*   **MDPI Paper (17.04.2026):** "Cyberattack Trends in MSPs" identifiziert unsanitisierte SVG-Assets in Multi-Tenant-Konsolen als Hauptvektor für Cross-Tenant XSS-Angriffe.

### Empfehlung für AeroCloud Engine:
1.  **DOMPurify** sofort auf **v3.4.0+** heben.
2.  SVG-Validierung auf den neuen **is-svg v6.0.0** Standard prüfen (Vorsicht bei Legacy-Files).
3.  Falls MCP-Integrationen genutzt werden: SVG-Payloads in Agent-Contexts isolieren.

*Quellen: NIST NVD, GitHub Advisory Database, OX Security Research, MDPI (April 2026).*

## Siehe auch

- [research/summary.md](research/summary.md) — Research Synthesis
- [research/stack.md](research/stack.md) — Stack Research
- [log.md](log.md) — Wiki Activity Log

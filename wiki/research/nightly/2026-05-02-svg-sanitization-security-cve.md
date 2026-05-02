---
title: "Nightly Research: SVG Sanitization Security CVE"
slug: 2026-05-02-svg-sanitization-security-cve
created: 2026-05-02
tags: [nightly, research, gemini, automated]
source: automated-nightly-cron
topic: "SVG Sanitization Security CVE"
---

# Nightly Research: SVG Sanitization Security CVE

**Datum:** 2026-05-02
**Automatisch erzeugt von:** scripts/nightly-research.sh
**Modell:** Gemini CLI

## Query

```
AeroCloud Engine Thema: SVG Sanitization Security CVE. Was ist neu seit gestern? Welche neuen Papers, Libraries, Best Practices, CVEs oder Breaking Changes sind seit April 2026 erschienen? Antworte kompakt auf Deutsch mit Datum-Verweis und konkreten Quellen (URLs oder Paper-Titel). Max 400 Worte. Falls nichts Neues: sag das ehrlich.
```

## Gemini Response

Seit gestern (01. Mai 2026) gab es keine massiven neuen CVE-Veröffentlichungen, aber die letzten 10 Tage (April 2026) waren für die SVG-Sicherheit kritisch. Hier sind die wichtigsten Neuerungen:

### **1. DOMPurify v3.4.0 Breaking Update (23. April 2026)**
Die wichtigste Maßnahme für die AeroCloud Engine ist das Update auf **DOMPurify 3.4.0**. Es adressiert drei kritische Bypass-Methoden:
*   **CVE-2026-41240:** Logikfehler in `tagCheck`, der das Einschleusen verbotener Tags ermöglichte.
*   **CVE-2026-41239 (Template Injection):** Betrifft Frameworks wie Vue 2; erlaubt XSS durch manipulierte Template-Ausdrücke in SVGs.
*   **CVE-2026-41238 (Prototype Pollution):** Angreifer konnten Regex-Prüfungen überschreiben, um Event-Handler durchzuschmuggeln.

### **2. Neue CVEs & Bedrohungen**
*   **Microsoft Threat Intelligence Report (30. April 2026):** Microsoft meldete eine Kampagne mit über **1,2 Millionen Phishing-Mails**, die SVG-Anhänge nutzen. Diese umgehen Scanner, indem sie CAPTCHAs innerhalb des SVGs rendern, um bösartigen Payload zu tarnen.
*   **CVE-2026-6861 (GNU Emacs, 23. April 2026):** Eine Schwachstelle in der Verarbeitung von SVG-CSS führte zu Speicherfehlern (CWE-193). Dies unterstreicht das Risiko komplexer CSS-Stile in SVGs.
*   **CVE-2026-29924 (Grav CMS):** XXE-Vulnerability (XML External Entity) durch SVG-Uploads im Admin-Panel.

### **3. Industry Trends & Best Practices**
*   **Secure SVG (SSVG) Proposal (Ende April 2026):** Sicherheitsforscher schlagen einen neuen Namespace (`xmlns=".../ssvg"`) vor. Browser sollen diesen als "Safe Mode" interpretieren, der Skripte und externe Ressourcen standardmäßig blockiert.
*   **SVGO Alert (April 2026):** Red Hat warnt vor DoS-Attacken auf den Optimizer **SVGO** durch rekursive XML-Entity-Expansion (Billion Laughs Attack), falls keine Limits gesetzt sind.

### **Empfehlung für AeroCloud Engine:**
1.  **Sofort-Update:** DOMPurify auf **v3.4.0+** anheben.
2.  **Content-Security-Policy (CSP):** `script-src 'self'` und `object-src 'none'` strikt erzwingen, um Inline-Skripte in SVGs zu neutralisieren.
3.  **MIME-Hardening:** Falls SVGs nicht interaktiv sein müssen, als `Content-Disposition: attachment` ausliefern oder serverseitig in WebP konvertieren.

**Quellen:**
*   *DOMPurify GitHub Security Advisories (April 2026)*
*   *Microsoft Threat Intel: "The SVG Phishing Surge" (30.04.2026)*
*   *NVD / CVE-Mitre Database (Einträge 2026-41238 bis 41240)*

## Siehe auch

- [research/summary.md](research/summary.md) — Research Synthesis
- [research/stack.md](research/stack.md) — Stack Research
- [log.md](log.md) — Wiki Activity Log

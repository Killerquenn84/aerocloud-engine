---
title: "Nightly Research: SVG Sanitization Security CVE"
slug: 2026-04-21-svg-sanitization-security-cve
created: 2026-04-21
tags: [nightly, research, gemini, automated]
source: automated-nightly-cron
topic: "SVG Sanitization Security CVE"
---

# Nightly Research: SVG Sanitization Security CVE

**Datum:** 2026-04-21
**Automatisch erzeugt von:** scripts/nightly-research.sh
**Modell:** Gemini CLI

## Query

```
AeroCloud Engine Thema: SVG Sanitization Security CVE. Was ist neu seit gestern? Welche neuen Papers, Libraries, Best Practices, CVEs oder Breaking Changes sind seit April 2026 erschienen? Antworte kompakt auf Deutsch mit Datum-Verweis und konkreten Quellen (URLs oder Paper-Titel). Max 400 Worte. Falls nichts Neues: sag das ehrlich.
```

## Gemini Response

Seit dem gestrigen Update (20. April 2026) gibt es keine völlig neuen CVEs, aber eine Verschärfung der Lage durch neue Details zu "Logic Bypasses" und ein frisches Whitepaper. Hier ist der kompakte Überblick für die AeroCloud Engine (Stand: 21.04.2026):

### 1. Neue Forschung: "The Namespace Confusion Attack" (20.04.2026)
Dieses gestern in Sicherheitskreisen diskutierte Whitepaper beschreibt eine neue Methode, um moderne Sanitizer (wie DOMPurify) zu umgehen.
- **Problem:** Angreifer nutzen verschachtelte Namespaces (z.B. `foreignObject` innerhalb von SVG, das wiederum HTML-Inhalte kapselt), um Parser in einen "Confusion-State" zu versetzen. Dabei "sieht" der Sanitizer harmlosen SVG-Content, während der Browser-Parser beim Rendering maliziöses HTML/JS ausführt.
- **Quelle:** *The Namespace Confusion Attack: Bypassing DOM Sanitizers via XML-in-HTML Serialization* (April 2026).

### 2. Update zu CVE-2026-33172 (Statamic & Laravel)
Zusätzlich zum bereits bekannten October-CMS-Bypass wurde gestern ein technisches Advisory für **Statamic (v5.73.14 / v6.7.0)** veröffentlicht.
- **Detail:** Der Exploit nutzt eine Schwäche im Asset-Reupload-Prozess. Da die AeroCloud Engine potenziell Assets überschreibt/aktualisiert, ist dies direkt relevant. Regex-basierte Filter für `on*`-Events werden hier durch Zeilenumbruch-Injektionen in Attributwerten umgangen.
- **Quelle:** *GitHub Advisory Database / Statamic Security Blog*.

### 3. "Recent" CVE-2026-4980 (Inkscape XInclude Disclosure)
Obwohl Ende März erstmals gemeldet, gab es am 20.04. neue Proof-of-Concepts (PoCs), die zeigen, wie via `xi:include` lokale Dateien (z.B. `/etc/passwd`) ausgelesen werden können, wenn SVGs serverseitig verarbeitet (z.B. gerastert) werden.
- **Relevanz:** Kritisch für AeroCloud, falls wir SVGs serverseitig für Thumbnails rendern.
- **Quelle:** *NVD / RedHat Security Advisory*.

### Zusammenfassung & Empfehlung (AeroCloud Engine):
*   **Wichtig:** Der Trend geht weg von Regex-Filtern hin zu **voller DOM-Parsing-Sanitization**.
*   **Aktion:** Prüfen, ob die AeroCloud Engine serverseitig SVGs mit `libxml2` oder ähnlichen Bibliotheken verarbeitet. Falls ja: **XInclude-Support explizit deaktivieren** (Schutz gegen CVE-2026-4980).
*   **Library:** Sicherstellen, dass **DOMPurify v3.4.0+** im Einsatz ist (behebt die im Log vom 18.04. erwähnten Bypässe).

Es gibt heute keine weiteren Breaking Changes bei den Kern-Bibliotheken (`is-svg`, `svgo`).

## Siehe auch

- [research/summary.md](research/summary.md) — Research Synthesis
- [research/stack.md](research/stack.md) — Stack Research
- [log.md](log.md) — Wiki Activity Log

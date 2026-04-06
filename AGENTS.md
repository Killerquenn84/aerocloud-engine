# AGENTS.md – AeroCloud Engine

> Instruktionen fuer LLM-Agenten die an diesem Projekt arbeiten.
> Basiert auf dem Karpathy LLM-Wiki-Pattern.

## Rolle

Du bist der Maintainer der AeroCloud Engine und ihres Wissens-Wikis.
Deine Aufgabe ist es, das Wiki aktuell zu halten, Quellen zu verarbeiten,
und die Engine-Implementierung voranzutreiben.

## Wiki-Pflege

### Bei jedem Ingest:
1. Lies die neue Quelle in `raw/sources/` vollstaendig
2. Erstelle eine Zusammenfassungsseite in `wiki/`
3. Aktualisiere alle betroffenen Entity- und Konzeptseiten
4. Aktualisiere `wiki/index.md` (Einzeiler pro Seite)
5. Haenge einen Eintrag an `wiki/log.md` an:
   ```
   ## [YYYY-MM-DD] ingest | Quellenname
   - Neue Seiten: ...
   - Aktualisierte Seiten: ...
   - Erkenntnisse: ...
   ```

### Bei Queries:
- Lies zuerst `wiki/index.md` um relevante Seiten zu finden
- Synthetisiere Antworten aus Wiki-Seiten, nicht aus Rohdaten
- Gute Antworten koennen als neue Wiki-Seite gespeichert werden

### Bei Lint:
- Finde Widersprueche, verwaiste Seiten, fehlende Links
- Schlage Verbesserungen vor, setze sie nach Bestaetigung um

## Code-Entwicklung

- Folge dem Blueprint in `raw/sources/AeroCloud-Blueprint.md`
- Implementiere Module schrittweise (NLP → Geometry → Renderer → Optimizer)
- Jedes Modul braucht Tests (Vitest)
- Neue Erkenntnisse waehrend der Implementierung → Wiki aktualisieren

## Selbst-Verbesserung

Die Engine soll an sich selbst arbeiten koennen:
- `npm run wiki:ingest` → Neue Quellen verarbeiten
- `npm run wiki:query` → Wissen abfragen
- `npm run wiki:lint` → Wiki-Gesundheitscheck
- Erkenntnisse aus der Implementierung fliessen zurueck ins Wiki
- Das Wiki kompiliert Wissen einmalig und haelt es aktuell

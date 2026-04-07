---
title: "TF-IDF mit Adaptive Position Weight"
tags: [tf-idf, nlp, adaptive-position, spacy, semantik]
sources: [AeroCloud-Blueprint.md]
updated: 2026-04-06
slug: tf-idf-ap
created: 2026-04-07

---

# TF-IDF mit Adaptive Position Weight (TF-IDF-AP)

## Formel

```
Score(t, d) = TF(t, d) * IDF(t) * P_weight(t, d)
```

- **TF(t, d)** - Term Frequency: Haeufigkeit des Terms `t` im Dokument `d`
- **IDF(t)** - Inverse Document Frequency: Seltenheit des Terms im Gesamtkorpus
- **P_weight(t, d)** - Adaptive Position Weight: Gewichtung basierend auf der Position im Text

## Adaptive Position Weight

Der P_weight-Faktor beruecksichtigt, dass Woerter am Anfang eines Textes (Titel, Einleitung) typischerweise relevanter sind:

- Woerter in Ueberschriften erhalten hoeheres Gewicht
- Erste Saetze eines Absatzes werden staerker gewichtet
- Exponentieller Abfall mit zunehmender Textposition
- Konfigurierbare Decay-Rate

## Ergebnis

- **+12.9% semantische Praezision** gegenueber Standard-TF-IDF
- Bessere Identifikation der thematisch zentralen Begriffe
- Relevantere Wortwolken-Darstellung

## NLP-Pipeline (spaCy)

Die Textverarbeitung durchlaeuft folgende Schritte:

1. **Tokenisierung** (spaCy) - Zerlegung in einzelne Tokens
2. **Lemmatisierung** - Rueckfuehrung auf Grundformen (z.B. "laufend" → "laufen")
3. **Stopword-Entfernung** - Filterung haeufiger Funktionswoerter
4. **POS-Tagging** - Wortarten-Erkennung fuer selektive Filterung
5. **TF-IDF-AP Berechnung** - Gewichtung mit Positions-Adaptierung

## Konfiguration

```python
nlp_config = {
    "language": "de",           # spaCy-Modell
    "min_df": 1,                # Minimum Document Frequency
    "max_df": 0.95,             # Maximum Document Frequency
    "position_decay": 0.85,     # Decay-Rate fuer P_weight
    "heading_boost": 2.0,       # Faktor fuer Ueberschriften
}
```

## Siehe auch

- [zipf-law.md](zipf-law.md) — Zipf-Normalisierung liefert die Gewichte fuer TF-IDF-AP
- [bert-embeddings.md](bert-embeddings.md) — BERT ergaenzt TF-IDF mit semantischer Distanz
- [knowledge/requirements-v1.md](knowledge/requirements-v1.md) — NLP-04 Requirement

---
title: "Font Licensing Decision: Inter + IBM Plex Serif"
slug: 2026-04-07-font-licensing
created: 2026-04-07
tags: [decision, phase-1, fonts, licensing, sil-ofl]
source: Phase 1 Wave 6 pre-check (T-6.1)
---

# Font Licensing Decision — Phase 1

## Decision

Bundle two font families in `packages/engine/assets/fonts/`:

1. **Inter** (Variable font, from Google Fonts) — sans-serif workhorse
2. **IBM Plex Serif** (Regular + Bold + Italic, from IBM's repo) — serif variety

Both fonts are licensed under the **SIL Open Font License v1.1** (SIL OFL 1.1).

## License Summary: SIL OFL 1.1

The SIL OFL is a free, libre, and open font license that allows:

- **Copying, studying, modifying, and redistribution** of the fonts
- **Embedding** the fonts in commercial products
- **Bundling** the fonts with software (commercial or open-source)
- **Modification** of the fonts (with restrictions — see "Reserved Font Name" clauses)

Key restrictions:

- The fonts must not be sold by themselves
- If a modified version is redistributed, it must be under a different name (the "Reserved Font Name" clause)
- The license text (`OFL.txt`) must accompany the font files

For AeroCloud Engine purposes: **unmodified bundling and distribution within our software product is explicitly permitted**.

## Verification Sources

- Inter: https://rsms.me/inter/ — "Inter is a free and open source font family. It is released under the SIL Open Font License."
- IBM Plex: https://github.com/IBM/plex — `LICENSE.txt` at repo root contains the full SIL OFL 1.1 text
- SIL OFL 1.1 text: https://openfontlicense.org/documents/OFL.txt

## Redistribution Checklist (Phase 1)

- [x] SIL OFL 1.1 text is committed alongside each font as `OFL.txt`
- [x] `packages/engine/assets/fonts/LICENSES.md` lists all bundled fonts, their versions, source URLs, and licenses
- [x] Fonts are unmodified (we use the upstream release directly, no subsetting or renaming)
- [x] The package description (`packages/engine/pyproject.toml`) does not claim to sell fonts standalone

## Risk Assessment

**Low risk.** Both fonts are widely deployed in commercial products (Inter ships with macOS Ventura+, IBM Plex powers IBM's entire brand). Neither license author has ever taken legal action against downstream users who complied with the OFL terms.

## Sign-Off

- Claude Code (orchestrator): approved based on SIL OFL 1.1 reading
- Review chain: This decision is a Phase 1 Wave 6 T-6.1 gate; it is not a 3-AI discussion but a direct licensing read. If any font usage becomes questionable in later phases (e.g., web font delivery from a CDN, subsetting for embedding), revisit this decision.

## Related

- [knowledge/phase-01-plan.md](knowledge/phase-01-plan.md) — Phase 1 Wave 6 tasks
- [knowledge/requirements-v1.md](knowledge/requirements-v1.md) — FOUND-12

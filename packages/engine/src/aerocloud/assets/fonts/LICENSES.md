# AeroCloud Engine — Bundled Font Licenses

All fonts bundled with AeroCloud Engine are licensed under the **SIL Open Font License v1.1 (SIL OFL 1.1)**.

## Inter

- **Version**: Variable (upstream latest)
- **File**: `Inter/Inter-Variable.ttf`
- **Author**: The Inter Project Authors (Rasmus Andersson + contributors)
- **Source**: https://rsms.me/inter/
- **Repo**: https://github.com/rsms/inter
- **License**: SIL OFL 1.1 — see `Inter/OFL.txt`
- **Usage**: Sans-serif workhorse for word cloud body text

## IBM Plex Serif

- **Version**: 3.006 (upstream @ IBM/plex `master`)
- **Files**:
  - `IBM-Plex-Serif/IBMPlexSerif-Regular.ttf`
  - `IBM-Plex-Serif/IBMPlexSerif-Bold.ttf`
  - `IBM-Plex-Serif/IBMPlexSerif-Italic.ttf`
- **Author**: IBM Corp. with Reserved Font Name "Plex"
- **Source**: https://www.ibm.com/plex/
- **Repo**: https://github.com/IBM/plex (`packages/plex-serif/fonts/complete/ttf/`)
- **License**: SIL OFL 1.1 — see `IBM-Plex-Serif/OFL.txt`
- **Usage**: Serif variety for contrast with Inter

## SIL OFL 1.1 Key Points

- Unmodified bundling and redistribution within software products: **permitted**
- Embedding in commercial products: **permitted**
- Modification (subject to Reserved Font Name rules): **permitted**
- Selling the fonts standalone: **prohibited**
- The license text must accompany each font

See `wiki/decisions/2026-04-07-font-licensing.md` for the full licensing assessment.

## How These Fonts Are Used

1. `packages/engine/src/aerocloud/fonts.py` discovers TTFs via `importlib.resources`
2. `register_fonts()` registers them ONCE per process (prevents canvas memory leak per Pitfall #2)
3. Phase 5+ renderer uses these fonts in the differentiable rasterizer

## Replacement Policy

If a font needs to be replaced or updated:

1. Verify the replacement is also SIL OFL 1.1 or compatible
2. Update this file with new version / source / license information
3. Re-run font discovery tests (`tests/unit/test_fonts.py`)
4. Commit the new font + updated `OFL.txt` together

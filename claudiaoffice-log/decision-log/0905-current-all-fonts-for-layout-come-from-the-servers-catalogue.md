---
id: D905
title: "Fonts for layout come from the server's catalogue, by hash; the server hands them out and can fetch a pinned starter set"
status: current
applies-to: all
date: 2026-11-12
round: "Pages, print preview and PDF (branch layouting)"
supersedes: []
superseded-by: []
---

# D905 · Fonts for layout come from the server's catalogue, by hash; the server hands them out and can fetch a pinned starter set

**The fonts a client lays out with are the font files of its server's catalogue (`claudia-fonts`), fetched by their SHA-256: `GET /api/fonts` lists every font that may be redistributed (family, style, weight, slant, variation axes, outline kind, hash, licence) and the substitutions; `GET /api/fonts/{sha256}` serves the file itself (TrueType or OpenType) and `GET /api/fonts/{sha256}.woff2` the same font as WOFF2 for showing text.** Files never change under their address and may be cached for good; a file that changed on disk since the catalogue read it is refused. The routes are public, like the web app's own files (D92). A server gets its fonts with `--fonts DIR` (default `STATE_DIR/fonts`); `python -m claudia_fonts fetch DIR` fetches a pinned starter set of open fonts (Inter, Fraunces, JetBrains Mono, Carlito, Caladea at a fixed commit of github.com/google/fonts, each file checked by SHA-256), which `./start.sh` does on first start and the Docker image does when it is built. A style's `font-family` is matched against the catalogue the CSS way (first family it has, nearest weight, italic); a family it lacks may be replaced by its metric-compatible substitute (Calibri → Carlito); generic names stand for Fraunces (serif), Inter (sans-serif) and JetBrains Mono (monospace); a family that is asked for and not there is named in the preview, with the one used instead.

**Notes.** The owner asked for it explicitly ("make the font server accessible to the client; that was a missing feature anyway"); E3.3 had built the catalogue but no routes. Layout needs the TrueType/OpenType bytes, not WOFF2: HarfBuzz cannot read WOFF2 and the PDF embeds the font itself, so the catalogue's hash is the file's (as D93 already said) and WOFF2 is a delivery format for display only. The routes are under `/api/fonts`, like every other route of the server, not the `/api/v1/fonts` E3.3 once planned. Liberation (Arial, Times New Roman, Courier New) is not in the starter set: its release files were not reachable from the development sandbox; an operator can add it as a collection. Only fonts with TrueType outlines are used for layout yet (CFF ones are skipped by the resolver).

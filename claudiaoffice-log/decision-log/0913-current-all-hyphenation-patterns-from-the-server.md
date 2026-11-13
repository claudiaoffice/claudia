---
id: D913
title: "Hyphenation patterns are TeX's, handed out by the server by hash"
status: current
applies-to: all
date: 2026-11-12
round: "Pages, print preview and PDF (branch layouting)"
supersedes: []
superseded-by: []
---

# D913 · Hyphenation patterns are TeX's, handed out by the server by hash

**Where a word may be broken is decided by Frank Liang's algorithm with the patterns TeX uses (hyph-utf8), implemented in the layout library (`text/hyphenate.ts`), with the pattern files handed out by the server like the fonts (D905): `GET /api/hyphenation` lists the languages (BCP 47 tag, other tags they stand for, name, licence, hash and size of the pattern file and the exceptions) and `GET /api/hyphenation/{sha256}` serves a file.** The files are pinned at one commit of github.com/hyphenation/tex-hyphen with every SHA-256 (`claudia_server/hyphenation.lock.json`): German in the 1996 spelling (`de`, MIT), British English (`en-GB`, MIT), American English (`en-US`, also standing for `en`; copying permitted with the notice kept). `python -m claudia_server.hyphenation fetch DIR` fetches them, `./start.sh` and the Docker image do it, and a server is given the folder with `--hyphenation DIR` (default `STATE_DIR/hyphenation`). A text's language picks its patterns: the same tag or alias, else the first (by tag) with the same language part (`de-AT` → `de`, `en-AU` → `en-GB`). The patterns' hash is recorded in the display list (`hyphenation`).

**Notes.** Chosen over Hunspell dictionaries (the LibreOffice ones mix licences) and over hyphenating in the browser (CSS `hyphens: auto` differs per browser and cannot be measured). Patterns assume the language's own minimum of letters on each side; the library applies its stricter limits (D912). The pattern files are not committed; the layout tests fetch them by the same lock.

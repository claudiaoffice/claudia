---
id: D93
title: "One font catalogue is the single source of truth for the engine and the browsers"
status: current
applies-to: all
date: 2026-11-03
round: "Fonts and typesetting services (sixteenth round)"
supersedes: []
superseded-by: []
---

# D93 · One font catalogue is the single source of truth for the engine and the browsers

**One font catalogue is the single source of truth for the engine and the browsers.** The same bytes are served as WOFF2 and shown to the engine. **Starter set** fetched through a lockfile; **no font binaries in git; no Microsoft fonts.**

**Notes.** The lockfile and `claudia-fonts fetch` are not built.

**Checked against the code, 2026-11-17 (`main` at `6814bac`).** Both are built since (D905): `claudia_fonts/starter.lock.json` pins the starter set and `python -m claudia_fonts fetch DIR` fetches it.

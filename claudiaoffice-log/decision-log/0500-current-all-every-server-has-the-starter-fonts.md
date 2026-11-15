---
id: D500
title: "Every server has the starter set of open fonts: it ships with claudia-fonts, and the fonts an operator adds come after it"
status: current
applies-to: all
date: 2026-11-15
round: "The three desktop clients: one server, files, printing (branch clients)"
supersedes: []
superseded-by: []
---

# D500 · Every server has the starter set of open fonts: it ships with claudia-fonts, and the fonts an operator adds come after it

**The pinned starter set of D905 (Inter, Fraunces, JetBrains Mono, Carlito, Caladea; OFL, about 6 MB) is part of the
`claudia-fonts` package (`claudia_fonts/builtin/`, `builtin_folder()`), byte for byte what `starter.lock.json` pins (a
test checks every file). Every server reads it first; the folders of `--fonts` (or `STATE_DIR/fonts`) come after it, and
a font of the same family and style there replaces the shipped one. So a server always has the fallback family and the
metric-compatible stand-ins for Calibri and Cambria, and printing never stops with "the server has no fonts": a family
it lacks is replaced and named in the preview, as before.**

**Notes.** Owner, 2026-11-15, choosing between three ways: shipping the set (taken), fetching it on the desktop server's
first start (needs the network, and printing fails until then), and the computer's own fonts on a loopback server
(real Arial and Calibri where installed, but pages that differ between computers, against "every Claudia document
renders the same wherever it is rendered"). Found on the desktop apps: their local server is started without `--fonts`
and nobody fetches anything for it, so every print said that the administrator should install fonts. The same file
found twice (the shipped set and an operator's fetched copy of it) is no longer reported as "replaced". The Docker image
no longer fetches the set; `python -m claudia_fonts fetch` stays for an operator who wants the files in a folder of
their own.

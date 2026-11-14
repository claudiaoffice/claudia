---
id: D441
title: "Downloading in the imported format patches the edits into the kept file"
status: current
applies-to: all
date: 2026-11-14
round: "Opening files from the computer (branch one-server)"
supersedes: []
superseded-by: []
---

# D441 · Downloading in the imported format patches the edits into the kept file

**`export_office` in the format a document was imported from, while its file is kept, answers that file with the
edits since the import patched in (`apply_edits_to_<format>(original, baseline, current)`, the baseline being the
state in `core.Import`), and says `patched: true`. In any other format, or when the file is not kept, it writes a new
file as before. When the edits cannot be patched in (a writer's `UnsupportedEdit`: moved paragraphs, a removed slide,
...), it writes a new file and adds the loss `not-patched` with the reason.**

**Notes.** This is the round trip D217 and D403 promised: what Claudia does not show (macros, charts, custom parts)
comes back byte for byte. The SHA-256 in `core.Import` makes sure the kept bytes are the ones imported.

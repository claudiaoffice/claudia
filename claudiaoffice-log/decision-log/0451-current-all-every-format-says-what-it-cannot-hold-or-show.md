---
id: D451
title: "Every format has an import list and an export list of losses"
status: current
applies-to: all
date: 2026-11-14
round: "Import and export wiring (branch import-export-wiring)"
supersedes: []
superseded-by: []
---

# D451 · Every format has an import list and an export list of losses

**Each of the six formats has both: what the model does not show of a file (`docx_import_losses`, `pptx_import_losses`, next to the existing odt, odp, ods and xlsx ones) and what a file cannot hold of the model (`docx_export_losses`, and the lists of xlsx, pptx and odp widened to the same codes: `authorship`, `notes-*`, `planned-time`, `layout`, `name`, `chart`, `object`...). The server hands the import list to the client when a file is opened, whatever its format.**

**Notes.** The Word and PowerPoint formats were the only two with no list at all, so opening a deck with tables and pictures said nothing about them. The lists describe the model, not the file: an edit exported with `apply_edits_to_<fmt>` keeps everything they name (D403).

---
id: D147
title: "Microsoft-format gaps that openpyxl/python-docx/python-pptx cannot write (xlsx pivot tables, docx tracked changes, pptx transitions) are closed by editing…"
status: current
applies-to: all
date: 2026-11-06
round: "Additive xlsx/docx/pptx extensions (twenty-fourth round)"
supersedes: []
superseded-by: []
---

# D147 · Microsoft-format gaps that openpyxl/python-docx/python-pptx cannot write (xlsx pivot tables, docx tracked changes, pptx transitions) are closed by editing…

**Microsoft-format gaps that openpyxl/python-docx/python-pptx cannot write (xlsx pivot tables, docx tracked changes, pptx transitions) are closed by editing the library's own already-written zip/element tree with `lxml`, never by forking the library.** Validated first as three standalone spikes (structurally consistent, read correctly by LibreOffice, and surviving a load-edit-save round trip through the library's own code), then built as three new workspace packages — `claudia-computes-io`, `claudia-composes-io`, `claudia-creates-io` — each depending on `claudia-core`, its one app package and its one format library (`openpyxl`, `python-docx`, `python-pptx`, as `>=` floors, matching the repo's existing pin style, not exact pins). Each package pairs a minimal base export from the app's own model (`workbook_to_xlsx`, `text_to_docx`, `slides_to_pptx`) with the one additive extension the spike covers (`add_pivot_table`, tracked changes folded into `text_to_docx` from `TextModel`'s own open suggestions, `add_transition`); `text_to_docx` is the one place a suggestion's `original`/`replacement` becomes real Word markup instead of being silently dropped. None of the three is in `scripts/api_surface.py`'s frozen `PACKAGES` list yet (same "first slice" status as `claudia_computes`/`claudia_composes`).

**Notes.** Resolves the brainstorm on import/export architecture: researched library gaps (not "openpyxl has no cell styling," which was a wrong premise, but real gaps in pivot-table write support, track changes and transitions), ruled out forking or a shared `python-xlsx` (no thin OOXML layer exists to extract; xlsx's own gaps are business-logic, not packaging), chose "extend additively" over the alternative of putting the format libraries inside `claudia-core` (refused by the kernel's own purity tests — `claudia-core` does no I/O and knows no format) via `AskUserQuestion`. `odfdo` is deliberately **not** a dependency of any of the three packages yet: D70 (see also D5, D67, D69) wants ods/odt/odp import and export before xlsx/docx/pptx in every app, and nothing here is that story — adding the dependency without a spiked ODF gap to extend would be dead weight. The full ODF-first, loss-reporting import/export of E6.9/E9.5/E10.3 remains open.

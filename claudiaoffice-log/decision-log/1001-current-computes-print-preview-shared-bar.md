---
id: D1001
title: "computes prints through the shared preview; its bar adds Contents, Scale and Sheet options"
status: current
applies-to: computes
date: 2026-11-14
round: "Printing sheets: the computes print preview (E6.19, branch computes-print)"
supersedes: []
superseded-by: []
---

# D1001 · computes prints through the shared preview; its bar adds Contents, Scale and Sheet options

**File ▸ Print… (Ctrl+P) in computes opens the preview composes and creates share (D918). computes adds three controls to the bar and nothing else: Contents (This sheet · Selection · Print area · Whole workbook), Scale, and Sheet options ▾. The bar reads: ← Print preview · Contents · Paper · Portrait/Landscape · Margins · Scale · Language · Page numbers · Sheet options ▾ · Download PDF · Print….** A page map (a button in the zoom group) shows the sheet as pages in print order.

**Notes.** A sheet differs from a text and a slide in two ways only: it is cut by rows *and* columns, and it holds things that sit on top of cells. A separate computes dialog was rejected for the same reason D918 gave: one place, one habit. `PrintSource` gains optional `contents`, `scale` and `options` the way it has optional `layouts`, so composes and creates are untouched. Screens: `notes/mockups/print-preview-computes*.svg`, agreed by the owner on 2026-11-14. Story split and the design in full: `notes/e6-19-print-sheets.md`.

---
id: D1004
title: "Orientation and scale are kept per sheet; paper, margins and page numbers per workbook"
status: current
applies-to: computes
date: 2026-11-14
round: "Printing sheets: the computes print preview (E6.19, branch computes-print)"
supersedes: []
superseded-by: []
---

# D1004 · Orientation and scale are kept per sheet; paper, margins and page numbers per workbook

**Per sheet: print area (D1003), orientation, scale, page order, repeated rows and columns, gridlines, row and column headings, purpose tints (D1007), the sheet name in the footer, charts and pictures, skip empty pages. Per workbook: paper, margins, page numbers and language.** Every change is a logged command with an exact inverse, one step for everybody, as D904 and D917 do for their setups; the assistant cannot change it (`people_only`, D63).

**Notes.** This is how XLSX and ODS divide it, so a round trip keeps it. The layout library takes both in one document and lets each printed sheet lie in its own orientation: a display page carries its own size, so a workbook may mix portrait and landscape pages.

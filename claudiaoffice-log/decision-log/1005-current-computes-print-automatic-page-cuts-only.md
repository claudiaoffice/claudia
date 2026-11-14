---
id: D1005
title: "Pages are cut automatically; manual page breaks wait, and so does View ▸ Page Breaks"
status: current
applies-to: computes
date: 2026-11-14
round: "Printing sheets: the computes print preview (E6.19, branch computes-print)"
supersedes: []
superseded-by: []
---

# D1005 · Pages are cut automatically; manual page breaks wait, and so does View ▸ Page Breaks

**For now a sheet is cut into pages by the paper, the margins and the scale only: no manual page breaks. View ▸ Page Breaks, which draws the cuts in the grid as dashed lines, comes after the preview works. Manual breaks come with composes' (E9.14).**

**Notes.** composes has no manual breaks either. XLSX breaks are therefore read and ignored, and not written. The order of the pages is a Sheet option: *down, then across* (Excel's default) or *across, then down*. A row taller than a page, or a column wider than one, gets a page to itself and is cut at the border (D182).

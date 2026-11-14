---
id: D1008
title: "A chart tab prints as one page; a chart on a sheet is cut with the page"
status: current
applies-to: computes
date: 2026-11-14
round: "Printing sheets: the computes print preview (E6.19, branch computes-print)"
supersedes: []
superseded-by: []
---

# D1008 · A chart tab prints as one page; a chart on a sheet is cut with the page

**A chart tab prints as one page, scaled to fit the paper inside its margins and centred, in the paper's orientation as it is. A chart or a picture on a sheet is part of the sheet: it is drawn where it sits and cut at the page's edge, like cells are.** When a cut does harm, the preview says so in its note row, offers *Show it on the sheet* (selects the object), and remembers *Not now* for the document (D71).

**Notes.** Charts are printed as the SVG picture the client makes of them (a figure's own SVG export), which the layout library draws as paths and glyph runs (D914). A chart for which the client has no picture is not drawn, and a note says why. Chosen by the owner on 2026-11-14.

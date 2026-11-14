---
id: D1009
title: "The grid paginator and the sheet adapter live in the layout library"
status: current
applies-to: computes
date: 2026-11-14
round: "Printing sheets: the computes print preview (E6.19, branch computes-print)"
supersedes: []
superseded-by: []
---

# D1009 · The grid paginator and the sheet adapter live in the layout library

**`@claudia/layout` gets `apps/computes.ts` with `layoutSheet`, like `layoutText` and `layoutSlides`: pure, in whole mpt, given the document in the wire form of a computes server (cells as shown, sizes, styles, print setup, objects) and the fonts `sheetFontsNeeded` names.** Cut rules: rows and columns are cut where the next one no longer fits the page at the chosen scale; rows and columns marked to repeat are drawn again at the top and the left of every page that starts after them; a page whose cells and objects are all empty is left out when the option says so; a text that does not fit its cell runs on over empty cells to its right and is cut at the page's edge. Each page of the result says which rows and columns it holds (`pageMap`), for the preview's page map.

**Notes.** Follows D902: the paginator is a new part beside `flow/`, and fonts, paragraphs, boxes, the display list and the PDF writer are reused as they are. Adding an adapter does not change what any existing document lays out as, so `LAYOUT_VERSION` stays `claudia-layout-3`.

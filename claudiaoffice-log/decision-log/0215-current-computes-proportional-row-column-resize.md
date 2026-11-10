---
id: D215
title: "Resizing a multi-line selection scales every line by the same percentage, anchored on the selection's top-most row or left-most column"
status: current
applies-to: computes
date: 2026-11-07
round: "Row height and column width (twenty-second round)"
supersedes: []
superseded-by: []
previous-id: D160
---

# D215 · Resizing a multi-line selection scales every line by the same percentage, anchored on the selection's top-most row or left-most column

**Resizing a multi-line selection scales every line by the same percentage, anchored on the selection's top-most row or left-most column** — dragging a border, or typing a size into the dialog, resizes that anchor line to the given value; every other line in the selection keeps its own current percentage-of-default, scaled by that same factor, rather than all being pushed to one shared pixel value. A line the scaling would push outside `MIN_ROW_HEIGHT`/`MAX_ROW_HEIGHT`/`MIN_COL_WIDTH`/`MAX_COL_WIDTH` is clamped into range rather than rejecting the whole change — settling the one open question D135 left behind. Only the border immediately after the selection's own anchor line triggers a whole-selection resize when dragged; any other border — including that same border when only one line is selected — resizes just the single line it belongs to. Patch 2 of two (the web half), client-only since Patch 1's `resize_lines`/`sizes` already take arbitrary per-line `[index, size]` pairs in one call: `web/app/lib/line-sizes.ts` (new — the size table, index/pixel conversion, `proportionalResize`), `web/app/lib/session.ts`, `web/app/components/SheetGrid.vue` (variable-size rendering, drag-resize with a live px/percentage tag, the header-menu event), `web/app/components/HeaderMenu.vue` and `web/app/components/LineSizeDialog.vue` (both new), and the wiring in `web/app/components/Workspace.vue`.

**Notes.** Agreed over four SVG mockups shown to and approved by the owner (per the project's design-before-code instruction), in two rounds of feedback — the first a misreading on the author's part (the live percentage belongs beside the drag's own readout, not only in the dialog), corrected in the second, which also added the drag interaction itself. The clamp-over-reject choice and the drag-border rule were the author's own call, not asked of the owner, since nothing here is destructive.

*Renumbered on 2026-11-10 from D160, a number that had been allocated twice by branches written in parallel (see `_rounds.md`, "One file per decision").*

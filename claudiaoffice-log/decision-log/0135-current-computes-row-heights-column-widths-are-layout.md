---
id: D135
title: "Row heights and column widths are sheet layout, not a cell style"
status: current
applies-to: computes
date: 2026-11-06
round: "Row height and column width (twenty-second round)"
supersedes: []
superseded-by: []
---

# D135 · Row heights and column widths are sheet layout, not a cell style

**Row heights and column widths are sheet layout, not a cell style** — resolves E6.13's open point ("whether row heights and column widths are style or sheet layout; proposal: layout"). Stored as sparse per-line overrides on the sheet (`Sheet.row_heights`/`col_widths`, pixels; a line not listed shows at the default, `DEFAULT_ROW_HEIGHT`/`DEFAULT_COL_WIDTH` = 26×96, matching the grid's current fixed size), set and undone through a new `computes.ResizeLines` command exactly like a structural edit — remapped by row/column insert and delete, restored when `Structure` or `RemoveSheet` is undone, conflict-checked against a colleague's own resize of the same line via `shifted_by()` — and independent of the not-yet-built CSS style system (E6.13), which governs cell/range/row/column appearance, not line size. Server: `sizes` (read) and `resize_lines` (write) methods, the latter on the AI's method allow-list alongside `set_cells`/`add_sheet`/`structure`. Patch 1 of two (model/command/server, fully tested); the web grid's variable-height rendering, drag-resize and the context-menu dialog are Patch 2, not yet built.

**Notes.** Chosen (over folding sizes into the E6.13 style system) via `AskUserQuestion`; the owner had no preference on including extras or on recording a decision, so both were the author's own call, flagged as such. Fixes two latent gaps the new state exposed: `RemoveSheet.apply()` and `Structure.apply()` previously restored cell content on undo but not row/col sizes, silently losing custom sizes on remove/delete-then-undo — fixed as part of this patch since the codebase's undo contract requires an exact inverse.

---
id: D1224
title: "A table is an in-flow object: one body, selected by its tab, moved between paragraphs, scaled in width, never turned"
status: current
applies-to: composes
date: 2026-11-18
round: "Object interaction in the three apps (branch object-interaction)"
supersedes: []
superseded-by: []
---

# D1224 · A table is an in-flow object: one body, selected by its tab, moved between paragraphs, scaled in width, never turned

**The object layer does not draw objects of kind `table`; `TableView` is the one body.** The table has a name tab above its top-left corner and a frame. A click on the tab or the frame selects it (one outline, one handle on the right edge); a click in a cell puts the caret there and does not select it. Dragging the tab moves the table between paragraphs, with a drop line showing where it will land, and release is one `move_object`. The right-edge handle sets the table's width in hundredths of a percent of the column (`TableInfo.width`), snapping to 100 %; there is no height handle (the layout's) and no turn handle. **`Esc` in a cell leaves the table completely**, for the text. **A faint frame and cell lines are always shown in the editor** as a non-printing aid, whatever the look; print and PDF show only the look.

**The table's context menu** (right press on the tab, the frame or inside a cell; the table is selected): *Name & describe…, Table options…, then Merge cells, Split cell, Sort ▸, then Delete table.* These are the commands the Edit menu no longer carries (menus workbook v4). Insert/delete and Height/width… stay on the row and column headers.

**Notes.** The owner, 2026-11-18, on the three bugs of tables in composes: a second violet frame, a dead "Options…" button, no visible borders. The cause of the first two was the object layer also drawing the table's object as an empty box over the table's caption. Escape was first proposed as a two-step; the owner chose "leave the table completely". The faint frame may become a View switch when the menu structure gets one.

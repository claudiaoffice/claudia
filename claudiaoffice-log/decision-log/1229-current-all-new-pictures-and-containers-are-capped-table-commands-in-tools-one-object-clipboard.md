---
id: D1229
title: "New pictures and containers are no bigger than 420 × 240 or themselves; the table commands are in Tools; one object clipboard"
status: current
applies-to: all
date: 2026-11-19
round: "Object interaction in the three apps (branch object-interaction)"
supersedes: []
superseded-by: []
---

# D1229 · New pictures and containers are no bigger than 420 × 240 or themselves; the table commands are in Tools; one object clipboard

The owner's answers of 2026-11-19 to the open points of D1228.

**A new picture or container is shown at the smaller of 420 × 240 and its own size,** so that an import does not fill the
screen or the slide by accident. *Pictures:* the client knows the file's pixel size (the browser decoded it for the
preview), so `pictureSize(aspect, 240, 420, natural)` caps it, in all three apps; a picture smaller than an object may be
(20 units) is shown at 20 with its proportions. *Containers:* the picture does not exist when the container is made, so the
frame is only a cap until it arrives: `add_rendering` takes `fit`, and the server's first `Render` of such a container is
shown at the picture's own size if that is smaller, as one more `ResizeObject` in the same batch (`RenderDesk`, kept in
memory: a server that stops in between leaves the frame as given). Only the first picture is capped; a width the person has
set is kept after that. The default container is 420 × 240 in all three apps (computes was 480 × 270). A text box turned
into a container (creates, D560) keeps its own frame and is not asked to fit.

**In composes the table commands are in Tools, not Edit,** as computes has its pivot table there: *Row ▸, Column ▸, Sort ▸,
Merge Cells, Split Cell, Table Options…*, on while the caret is in a table. The four that only composes has changed their ids
from `edit.*` to `tools.*` (`tools.merge-cells`, `tools.split-cell`, `tools.table-options`, `tools.sort-ascending`,
`tools.sort-descending`), their keys stay; Row and Column keep `edit.row-*` and `edit.column-*` because computes has them
under that name in Edit.

**The workbook is the source of truth for the words of the context menus** (`claudia-menus-5.xlsx`): *Name & describe…,
Edit text, Style…, Rotate by…, Wrap text…, Cut, Copy, Release from grid, Delete* and, for a table, *Name & describe…, Table
options…, Merge cells, Split cell, Sort ▸, Delete table*. The entries of the menu bar keep the manifest's words.

**A selected table is taken away with Delete (or Backspace),** however it was selected: the table takes the focus (its tab)
when it is selected and nothing in it has it. Esc leaves it.

**One object clipboard, for pictures, in all three apps** (`web/app/lib/object-clipboard.ts`). Cut and Copy (context menu,
Ctrl+X, Ctrl+C) hold a copy of the selected picture (its bytes, description, size); Paste (Edit ▸ Paste, Ctrl+V) puts it
where the app puts a new picture, through `add_image`: a place under the caret in composes, the selection's cell in
computes, the next place on the slide in creates. One step in the history. The system clipboard gets the picture's
description as text, which is what other programs make of it, and **is also how Paste knows the held picture is still the
last thing copied**: a paste whose clipboard says something else is a text paste. Text that is selected is copied as text,
and the held picture is forgotten. Not built: other kinds of object (a box or a shape has paragraph content the server
cannot yet copy), pasting a picture from another program (D-open: import from the clipboard).

**Notes.** Applies D1225 (the object menu) and D1228. The server's `fit` is additive: nothing changes for a client that does
not send it.

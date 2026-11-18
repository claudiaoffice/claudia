---
id: D1213
title: "A table box is edited in a field of its own, the table menus follow the box the caret is in, and a floating table is printed in the flow for now"
status: current
applies-to: composes
date: 2026-11-18
round: "Tables in composes (branch tables-in-composes)"
supersedes: []
superseded-by: []
---

# D1213 · A table box is edited in a field of its own, the table menus follow the box the caret is in, and a floating table is printed in the flow for now

**Editing.** The text of composes is one editable surface whose blocks are the paragraphs of the reading order. A box is not in the reading order (D1212), so it is not a block of that surface: a table is drawn as an island (`<table>`, not editable as part of the text) and every box is a one-line field of its own with a name for assistive technology ("Row 2, Beds"). Typing in a field is one `replace_text` on the box's id when the person leaves it (Tab, Enter, an arrow, a click elsewhere), so one box is one step in the history. The keys of the text editor do not reach a box and the keys of a box do not reach the text; the keys of the menus work in both. Tab in the last box adds a row (D603); Shift+Tab, Enter and the arrow keys move between boxes by the ids, never by a place on screen.

**The table menus follow the caret.** Edit ▸ Row ▸, Column ▸, Sort ▸, Merge Cells, Split Cell and Table Options… are on only while the caret is in a box of a table, for somebody who may edit, and only where they have something to do (no 101st row or 11th column, no last row or column deleted, nothing to merge). Row and Column are computes' entries with the same ids, words and keys (D130); the rest take the keys of D1208. The keys work while typing in a box. Insert ▸ Table… is composes' alone and puts the table after the paragraph the caret is in.

**Merge Cells** acts on the box the caret is in, not on a selection of several boxes (there is none yet): it joins the box with the one to its right, or, if that is not possible, with the one below. It never joins across the header, and a box that is merged already is split first. Joining a range chosen with the mouse is the next step and does not change the server.

**Print.** A table prints in the flow, between its rows across pages, with the header repeated when it is at most half a page. A *floating* table is printed in the flow below its paragraph, with a note, until E9.29 has text wrap. A number column is aligned right (decimal alignment is not built). The total row starts with the word the view shows ("Total" in the reader's language).

**Not built:** tagging the header cells of a table in a PDF; decimal alignment; a multi-box selection.

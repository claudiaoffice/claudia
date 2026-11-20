---
id: D1330
title: "The arrow keys lead out of a table and into it, as through the words"
status: current
applies-to: composes
date: 2026-11-20
round: "Bug fixes: tables and object sizes (branch fix-table-exit-object-sizes)"
supersedes: []
superseded-by: []
---

# D1330 · The arrow keys lead out of a table and into it, as through the words

**Decided 2026-11-20** (the owner accepted the proposals made after B5: nothing took the caret past a table).

A table in a composes text is on the same path for the arrow keys as the paragraphs around it:

- **Out, downwards:** the down arrow in the last row, and the right arrow at the end of the words of the very last box,
  go to the start of what follows the table: the next table hanging from the same paragraph, else the next paragraph.
  At the end of the text that paragraph is made first (D1331).
- **Out, upwards:** the up arrow in the first row, and the left arrow at the start of the very first box, go to the
  end of the paragraph the table hangs from, or into the table before it if two hang from the same paragraph.
- **In:** the down arrow on the last line of a paragraph that has a table after it goes into the first box; the up
  arrow on the first line of the paragraph after a table goes into the first box of its last row.
- **Backspace** at the start of the paragraph after a table does not join that paragraph to the one above the table
  (which would move its words above the table); it puts the caret at the end of the table's last box, as the left
  arrow does.
- Tab in the last box still adds a row (E9.32), and Esc still leaves the table for where the caret was before it.

What was typed in a box is put in before the caret leaves it, as it is when the caret moves to another box.

**Notes.** The words of a box are a field of their own (D1213), so the keys are the table's while the caret is in a
box and the text editor's while it is in a paragraph; both sides hand over at the edges. Delete at the end of the
paragraph *before* a table still joins the next paragraph to it, above the table; that was not part of B5 and is left as
it is.

---
id: D1212
title: "The words of a table box are one line on the wire and stay outside the reading order; the AI works in tables by ids"
status: current
applies-to: composes
date: 2026-11-18
round: "Tables in composes (branch tables-in-composes)"
supersedes: []
superseded-by: []
---

# D1212 · The words of a table box are one line on the wire and stay outside the reading order; the AI works in tables by ids

**A box is one paragraph (D1203), so the wire never makes a second one in it.** `replace_text` and `replace_words` take the box's id (`<table>/<row>/<column>`) where they take a paragraph's, and the range has to stay inside one box. A line break in the words written into a box (typing, `set_entries`, a search replacement) becomes a space; a field character is dropped, as everywhere. Composes has no soft line break yet; when it has, a box takes it and this decision is revisited.

**Boxes are not in the reading order.** `TextModel.reading_order` does not list them, so a box is never a list item, never a heading, never in the outline or a table of contents, and the numbering of lists is untouched by a table. The words of a box are reached through three doors instead: search (a kind `table`, with the place `{block, table, row, col}`), the AI's lens (`tables`, and the orientation and change reports), and export (D1210). If boxes ever need list items or headings, that is a change of this decision, not an extension of the reading order.

**The table methods are the assistant's.** Table methods (`add_table`, `set_entries`, `insert_rows`, `merge_cells`, … see `TABLE_METHODS`) are in the assistant's allow-list in *act* and, being changes, in none of *suggest* (people accept suggestions of words; there is no suggestion of a structure yet). Rows and columns are named by id, never by place, so a model that read `tables` an hour ago cannot hit the wrong row; and totals are derived, so it cannot make them wrong.

**Table ids** are random like those of objects (`t` and eight hex digits), not counted: the id of a table that was removed must not come back, or undoing its removal would collide with a newcomer. Row and column ids keep the counters of the definition (D1201).

**Notes.** Merging joins the words of the covered boxes to the first with a space, in one step, instead of refusing a merge that covers words: nothing is lost and undo gives the boxes back.

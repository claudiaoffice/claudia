---
id: D1214
title: "Tables in docx and odt: a regular table is an own table, every other table stays in the file, and a table is written as a real table with its look on the cells"
status: current
applies-to: composes
date: 2026-11-18
round: "Tables in composes (branch tables-in-composes)"
supersedes: []
superseded-by: []
---

# D1214 · Tables in docx and odt: a regular table is an own table, every other table stays in the file, and a table is written as a real table with its look on the cells

**What a regular table is** (one rule for both formats, `claudia_composes_io/_tables.py`; the formats only say what a cell and a span are). One to 100 rows and one to 10 columns, every row as wide as the grid, every cell at most one paragraph with words in it (no picture, note, comment, field, content control, list, heading, formula or nested table), merged cells that make non-crossing rectangles whose covered positions the file marks as covered, no cell spacing and no row that starts or ends short (docx), and a place in the flow: the table follows a paragraph of the text. A table before the first paragraph, after a table of contents or in a content control is not regular. Every table that is not regular stays in the file exactly as it was and is counted by the import as the loss `table` (nested ones count too).

**What the import makes of a regular table.** An own table named `t1`, `t2`... in the order of the file, shown by an object that hangs from the end of the paragraph it follows. The words of a cell are one line (a tab or a break is a space); the words of the cells a merge covers are joined to the first box with a space, as merging in the text does (D1213). Header rows are the rows the file marks as a header (`w:tblHeader`, `table:table-header-rows`). A column is a number column when every filled body cell reads as a number in the document's language, else text. Column widths are the proportions of the file's grid (not below 1/100 of the table), the table's width its percentage (`w:tblW` as a percentage or against the text width, `style:rel-width`). Boxes have the role styles of the look; **the look is not read**: the borders, fills, fonts and alignment a file gives its cells are not understood and a table comes in with the default look (D1206). Nothing of that is lost from the file, see below.

**What the export writes.** A real table after the paragraph the table hangs from: one cell per rectangle with its spans (`w:gridSpan`/`w:vMerge`; `table:number-columns-spanned`/`-rows-spanned` and a covered cell for every position it reaches over), header rows flagged so that programs repeat them, a fixed layout with the column proportions. A cell holds one paragraph in the style of its role (or the box's own style) and, for a number column below the header, with its words aligned right. The total row is written as an ordinary last row of words (as D1209 says). **The look is on the cells**: the lines and the fill of the role styles are the cell's own properties (`w:tcBorders`/`w:shd`; an automatic `table-cell` style), and the *paragraph* styles of the table roles are written **without** their box (lines, fill, padding), so that a cell is not drawn twice. A floating table is written in the flow (D1213). Two tables that hang from the same paragraph have an empty paragraph between them, because most programs make one table of two that touch. Written, a table is not a loss of an export and not one of the "not written" changes.

**Edit and re-export of a kept file.**
- *docx*: a table that changed, was moved to another paragraph, was removed or was added is replaced, removed or written in place (the tables of a paragraph are replaced together, right after it); every other table, the tables that are not regular, and all other parts stay as they were. A change of the look alone is not seen (the look of the file's table was never read). A baseline whose tables are not those the file holds is `UnsupportedEdit`.
- *odt*: a table nobody touched stays in the file as it is; a table that changed, moved, was added or removed makes the file be written anew (`UnsupportedEdit`, like a table of contents), because the odt patch rewrites whole lists and regions and has no stable place for a table in them.

**Not built:** the table's name, description and alt text are not written (`w:tblCaption`, `w:tblDescription`; `table:name` is `TableN`, not the object's name); a look of a file is not read; a row that must not split; tables inside list items are read where they stand in the flow but written after the item's paragraph; the odt patch mode for a changed table (above); a total row that carries a label of its own in a file.

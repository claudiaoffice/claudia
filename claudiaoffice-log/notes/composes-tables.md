# Tables in composes — own tables, linked tables, and how they relate to computes (plan)

**Status: proposal of 2026-11-18. Nothing is built or decided.** No decision numbers are taken here: the ids come from
the range the owner hands out for branch `tables-in-composes` (see "Questions"). Written against `main` at `23f7978`
and `floating-objects` at `2548335`. The branch `tables-in-composes` had no commits of its own, so "up to date with
main" is a fast-forward (86 commits); this patch only adds notes, mock-ups and stories.

Mock-ups, in `notes/mockups/`:

| File | Shows |
|---|---|
| `composes-table-screens.svg` / `.png` | A: an own table in Flow view with the chip, a caret cell and a colleague's locked cell. B: Insert ▸ Table…. C: Row, Column and Sort, with the keys computes already has. D: Table options. E: Page view / print / PDF across a page break. F: the four states of a linked table. G: keyboard, BITV, collaboration, files |
| `composes-table-architecture.svg` / `.png` | The class diagram: what is new or changed in `claudia_core`, the apps, the server, the layout library, the client and the file packages, and a table of where computes and composes meet and part |

## 1. What is there today (checked in the code)

| Fact | Where |
|---|---|
| Every document has a random `uid` in its plain manifest, found by exact lookup, kept when a file is placed, never twice on a server | D533–D536, `POST /api/docs/lookup` |
| A named range with a header row is a table: `NamedRange` (id `r…`, name, scope, `header`, `grows`, `purpose`, `column_purposes`, or a `SQL()` anchor) over cells of a sheet; written `Sales[Amount]`; in the one name space of objects, slides, sheets and chart tabs | D600, D603, D604, D607, D550, D552; `claudia_computes/names.py` |
| The slot table in core already has a thing `cell` with a box slot and a words slot, and says a later kind of thing joins by adding a row | `claudia_core/facets.py` (`SLOTS`), D311, D315 |
| An object is a shared body plus an app anchor; a text box's words are a `Paragraph`; a rendered container points at a definition by id; the object kinds are `text`, `shape`, `image`, `diagram`, `rendered` | D177, D181, D390, `claudia_core/objects.py` |
| A composes object hangs from a character (`BlockAnchor(block, offset, dx, dy)`) and follows the text | D179, D1023 |
| The kernel may not contain the words sheet, cell, workbook, slide or formula in an identifier | `claudia-core/tests/test_purity.py` |
| The formula engine, the number formats and typed input are in `claudia-computes`; composes depends on core and search only | `calc.py`, `numformats.py`, `entry.py`; `claudia-composes/pyproject.toml` |
| composes has no table model. A docx table is counted as the loss `table` and stays in the file; an odt table is reported the same way | `_IMPORT_LOSSES` in `docx.py`; E9.1 "Still not done: tables" |
| The layout paginates blocks of lines; a line is never split | `layout/src/flow/paginate.ts` |
| The links (E12.2) are not built: source uid, server hints, who accepted, pull as a logged export | D72, D535 "out of scope"; the earlier chat |
| `floating-objects` is not finished: the offset (D1023) and wrap decisions D1061–D1064 exist, wrap is not built; stage 1 is wrap in print only | `notes/composes-floating-object-layer.md` on that branch |

## 2. The position in one paragraph

A table is an **object** on the shared layer (identity, name, alt text, anchor, history, locks, redaction, export) whose
body points at a **table definition** the document keeps by id, as a rendered container points at its definition
(D390). The definition holds columns and rows with ids and, for each cell, a `Paragraph`. Computes and composes meet
at a small read-only protocol, **`TableSource`** (columns, row count, the text and the number of a cell, a version),
which a computes `NamedRange` implements through its sheet and a composes table implements through its own entries.
Everything that wants "a table" without caring where the cells live reads that protocol: a linked table, the bar
chart, `FROM`, the AI's `table` tool, export. They do not share storage, because a sheet's cells are positional,
typed and calculated and a text's cells are words with ids; they share **names, purposes, the commands a person
sees, the keys, the slots a style fills, the Region idea and the protocol**. A table is **placed in the flow by
default** and may be placed floating; both are the same object.

## 3. The model (as built, D1201–D1210)

In `claudia_core/tables.py` and `table_commands.py` (the identifiers avoid the guarded words), so that creates can use
the same body later (D177's lesson) and the model is tested without composes.

| Entity | Holds | Notes |
|---|---|---|
| `TableDef` | `id`, `columns`, `rows` (ids in order), `entries` (a box's `Paragraph` by (row id, column id)), `merges`, `header_rows`, `banded`, `look`, `placement`, `width`, and the counters `next_row`, `next_col` | At most 100 rows and 10 columns (D1207). The object's `name`, `description`, `decorative` and size are on the object body (D550) |
| `Column` | `id`, `kind` (`text`, `number`), `total` (`sum`, `mean`, `count`, `min`, `max` or none), `width` | A column's name is the text of its last header box (what `Sales[Harvest]` would say) |
| `Merge` | `row`, `col`, `rows`, `cols`: a rectangle from the box at (row, col) (D1205) | Grows and shrinks with inserted and deleted rows and columns; moving rows or columns that would tear one is refused |
| `TableLook` | `id`, name, and four paragraph styles: header, body, band, total | Three built-in looks (D1206): Rules (default), Grid, Plain |
| `TableSource` | a protocol: `source_id`, `column_count`, `row_count`, `header_rows()`, `text(row, col)` | Index-based, so the same reader serves a computes named range in patch 2 |
| `TableRegion` | table, row ids or all, column ids or all | A `Region` (D17): locks and presence; typing in a box holds that box |
| `ObjectBody.table` | the id of the definition | `OBJECT_KINDS` has `"table"`; redaction keeps the shape and the length of the words (D720) |

**A box is one paragraph (D1203) with the id `<table>/<row>/<column>` (D1210).** Typing in it is the ordinary
`core.InsertText` and `core.DeleteText`; a covered box takes no typing. **Numbers are text** read by the document's
language. **The header** is the first `header_rows` rows of boxes. **The total row** is not stored: it is derived from the
columns' `total`. **Placement** (`flow` or `float`), width, look and banding are fields of the definition, not of the
anchor, so they cannot clash with the floating-objects branch.

**Commands**, each with an exact inverse and per-author undo: `DefineTable`, `ForgetTable`, `SetEntries`,
`InsertRows`, `DeleteRows`, `InsertColumns`, `DeleteColumns`, `SetRowOrder`, `SetColumnOrder`, `SetColumn`,
`SetTableOptions`, `SetMerge`. Ids are never reused, so an undo cannot meet a colleague's new row. The composes state
schema is 15 (`"tables"`; an older text reads as having none).

## 4. Computes and composes, concern by concern

| Concern | computes (a name over cells) | composes (an own table) | What they share |
|---|---|---|---|
| Identity | `NamedRange`, id `r…`, name in the shared space | the table object: id, name in the same space | one name space, one `#` list, one rename rule (D550, D552) |
| Storage | cells of the sheet; the name is a rectangle | `TableDef` owns its entries by (row id, column id) | `TableSource` |
| Columns | a column of the sheet; the header is the first row of cells | `Column` with its own name | names and purposes (`input`, `data`, `calc`, `result`) |
| A cell | typed content: number, text, formula | a `Paragraph`: words, one style, authors, fields | the `cell` slots box and words (D311) |
| Numbers | typed, shown through a number format (D378) | words; read as a number by the document's language when a total, a sort or a chart needs it | computes keeps the formats |
| Formulas | the whole engine | none; a total per column | calculated columns live in computes and arrive linked |
| Structure edits | `StructuralEdit` maps positions (D603) | commands on ids | the same menu entries, keys and inverses |
| Look | style ranges in four layers (D307) | four role styles on the table; no cell formatting | slots, purposes tint (D604) |
| Region | `CellRegion`, by position | `TableRegion`, by id | both are Regions |
| Size | a sheet (E4.12) | tens of rows | a long table belongs in computes |
| Placement | the sheet owns the grid | in the flow, or floating | the object layer |

**Where it must not diverge** (so people do not meet two tables): the names, the purposes and their tint, "the table
grows with its last row" (Tab in the last cell), Edit ▸ Row / Column with the keys computes has (Shift+Alt+↑↓←→,
Ctrl+Alt+- and Ctrl+Alt+_), Describe Object, Reference in Chat, and "what is not meaningful is not shown": Row,
Column and Sort appear in Edit only while the caret is in a table.

**Where it should diverge, and why:**

1. **A cell is words.** Authorship, references and the AI's quoting tools (D681) all work on a `Paragraph`, and the
   owner's rule is one style per container's text (D181, D309). Several paragraphs, lists or pictures in a cell are a
   later decision; Enter starts a new line in the cell.
2. **Numbers are text.** What is typed is what is in the file and in a docx or odt. A total, a sort or a chart reads
   the value with the document's language (composes already has one, `SetLanguage`), which does not depend on the
   client's locale, so every client agrees. A column of numbers is aligned on the decimal separator by the layout;
   nothing reformats them unless somebody asks (a column command, undoable). A computes-style display format would
   hide what the file says.
3. **No formulas.** The engine is in computes; the kernel may not hold it (purity test); a mini-engine in composes
   would be a second one. A total row per column covers what a text needs, as Excel's total row does. A table with a
   calculated column is a computes table brought in linked (§8).
4. **Ids, not positions.** Rows and columns have ids that are never reused, like paragraphs (D681's reasoning applies:
   a model says "the Harvest column, the Roof beds row", never an offset). Locks, the AI and sorting survive edits by
   other people.
5. **The header belongs to the columns.** There is no first row of cells to retype; the column's name is the header.
   Spans are `HeaderGroup`s above it. A merged cell in the body does not exist (§9 for imports).
6. **Looks are roles.** Four styles, not per-cell formatting: the booktabs default (a heavy rule above and below, a
   thin rule under the header, a thin rule above the total) is a set of box properties on those slots.

## 5. Where it sits: an object, placed in the flow or floating

The owner's picture: a table is an object around which text wraps. **The object part is right; I would not make
"floating, text wraps around it" the main way a table sits.** A floating object has a fixed size and sits on one page
(print moves it up to stay on its page), and a table's height comes from its words and it must be allowed to run over
pages. Word and LibreOffice both treat a table as a block that splits between rows, with floating as the exception.
The lines of a paragraph that holds an object's anchor would also be split by the table ("above and below" works at
the anchor's line, D1061), which is wrong for a table between two paragraphs.

So one object, two **placements**, kept in the anchor beside `dx`/`dy` (it is composes-only, and `MoveObject` already
replaces the whole anchor):

- **In the flow** (default): the table takes its own place after the paragraph it hangs from, as wide as the text or a
  width the person set, and splits between rows across pages. The anchor still follows the text (`carry_objects`),
  so a joined or split paragraph takes its table along. `dx` and `dy` are not used.
- **Floating**: a narrow table beside text, with the wrap modes of D1061–D1064 once they are built.

That is a fifth value beside the four wrap modes that were decided (*over*, *around*, *above and below*, *behind*);
the one key Format ▸ Wrap Text cycles pictures and shapes through their four, and a table gets its placement in
Table options. It needs a decision (Question 1).

**Why not a table as a block in the paragraph list** (a `Table` beside `Paragraph` in `blocks`): every place that walks
paragraphs (reading order, numbering, the table of contents, search, the AI's `paragraphs` and `outline`, the
paginator) would have to learn a second kind of block. As an object, the cells' paragraphs appear in the reading order
as asides, like an object's words today (`ParagraphHost`), and only the layout and the editor learn the new
placement.

**In the editor** the flow view is the browser's: an in-flow table is a real `<table>` element between two paragraph
elements, so the browser lays it out and nothing is reserved by hand. Cells are edited in place the way a text box
is. The engine remains the one place that decides how a document prints (D901, D1062); the same few-pixel difference
the floating-object note describes applies, and is tested the same way.

**Order of work:** only the placement *floating* waits for `floating-objects`. The model, the server, the layout, the
editor, the in-flow placement and the files do not.

## 6. Totals, sorting, growing, the AI

- **Total row.** `Column.total` is a function; the row is derived, shown in the `total` look, exported as text with
  the cached value. Mean, count, min and max read numbers the way §4 says; a cell that is not a number is skipped and
  the total says how many were.
- **Sort.** `SortRows(table, column, descending)` reorders the rows with one command; row ids do not change; the
  inverse restores the order. A text column sorts by the document's language's collation.
- **Growing.** `grows` is D603's flag: Tab in the last cell adds a row; pasting several lines below adds that many.
- **The AI.** Allowed to read (`table(name)`: columns and rows as text) and to act or suggest on entries' words only
  (D640: words and paragraph styles); it names a column by its name and a row by its number or by the value of a key
  column, never by an offset (D681). The suggest mode puts a proposal in a scratch copy as for every command.
- **Search and replace** finds words in cells, the app naming the containers (D289).

## 7. Collaboration

A person's caret in a cell locks that cell (the ± n words rule, D11, applied to the cell's words). A command that
changes rows or columns (insert, delete, move, sort) is refused for everybody while another person is in the rows it
touches. Per-author undo (`shifted_by`) is the same as for names (D603): a table command is not shifted across an edit
of the cells it does not touch. **Redaction** (D720–D726) empties entries and the caption and keeps the shape: rows and
columns stay, the words go. The history shows "Added a table", "Sorted by Harvest", "Added a row".

## 8. Linked tables

A linked table is an own table with a source. The cells are a snapshot, the source is a remembered pointer, as agreed
in the chat of 2026-11-15 and built so far only as far as D533–D536:

```
source:  document uid · server hints · last-known document name
         object id inside the source (the range's id r…) · last-known name
         revision at the pull · who accepted it, and when
```

- **Pull** is done by the person's client, which opens both documents (D72): it reads the source through
  `TableSource` (for a computes name, an adapter over `NamedRange` and its sheet: header row, kinds read from the
  values, text as the cell shows it) and sends `DefineTable` with the link to the composes document. No server reads
  the other document. It is logged in the source like an unencrypted export.
- **A linked table's values are read-only**; its look, total row, caption, placement and name are the author's. A
  linked table has the purpose `result` by default. **Detach link** is one undoable step: the cells become editable and
  the source is forgotten.
- **Updating** compares revisions, shows old against new in a review dialog and changes nothing until an owner or an
  editor accepts; "Not now" is remembered until the source changes again.
- **States** (mock F): up to date, source changed, source not found (looked up by uid on the servers on the person's
  map; otherwise "Find replacement…", never automatic), source sealed (the person's own session or the Open dialog; no
  password is stored in the document).
- **Known edge, recorded in D535:** a server started without a list also hides its documents from lookup, so a link to
  a document there never heals. This note does not change it.

It is a separate story (E9.33) behind E12.2 because the link design (anchor of the pointer, the review dialog, the
logged pull) is shared by charts and text and should be built once. What this plan needs from the table model today is
only that a definition can carry a `source` later; it is left out of the first schema and added with an upcaster.

## 9. Files

From memory of what Word and LibreOffice write, to be checked against real files before any import code is written (the
owner has offered documents; `test-corpus` and `real-world-docs` exist), exactly as the floating-objects note did for
wrap:

| Claudia | docx | odt |
|---|---|---|
| table, its columns' widths | `w:tbl`, `w:tblGrid`/`w:gridCol` | `table:table`, `table:table-column` |
| name | the table's caption (`w:tblCaption`) | `table:name` (unique in the document) |
| description / alt text | `w:tblDescription` | `svg:desc` or the table's description |
| header row, repeated on every page | `w:tblHeader` on the first row | `table:table-header-rows` |
| a row that does not split | `w:cantSplit` | `style:may-break-between-rows` |
| header groups | `w:gridSpan` in the first row(s) | `table:number-columns-spanned` in the header rows |
| floating placement | `w:tblpPr` | the table's `style:table-properties` and its wrap |
| total row | written as an ordinary last row of text | the same |

**Import** reads a table as an own table only when it is regular: the same number of columns in every row, a header
row that is flagged or at least in the first row, no merged cells in the body, no nested tables. What is not regular,
and cell colours, borders and shading set by hand, stay in the file (odt is patched byte-exact outside edited
paragraphs; docx is restored around the edited parts) and are listed as not understood, as every table is today.
Where a regular table's formatting is consistent (a header row bold and shaded), the import offers the role styles
rather than keeping cell formatting, as for other imported formatting (E9.8).

**Export** writes real tables. docx has the problem listed in `import-export-coverage-2026-11-14.md` (C): adding a
paragraph can fall back to a fresh file, which already drops tables of the original; own tables are written with it,
the not-understood ones are not.

**Between apps:** Edit ▸ Paste As ▸ Table from a computes range gives an own or a linked table; the other way a
composes table pasted into computes becomes a named range with a header (D600), its text read as numbers by the
document's language.

## 10. The layout engine

`layout/src/flow/table.ts` (new): column widths from the words by integer arithmetic (`detmath`), a width the person
set winning, then each cell's paragraph laid out by `layoutParagraph` at its column's width. `paginate` is generalised
from "a block is made of lines" to "a block is made of items that do not split": the lines of a paragraph, the rows of
a table. The existing rules carry over (keep with next, space collapsing); new ones: header rows repeat on each page,
a row is never split unless it is taller than a page (then by its lines), a caption stays with its table. The display
list gets the rules (borders) from the slots' box properties, and the PDF writer tags header cells and the footer row.
Tests: the same widths and the same display list for the same input on every machine, golden files, as for the
paragraphs.

## 11. Slices, in order (TDD; each is a patch against `tables-in-composes`)

**Status 2026-11-18:** S0 and S1 are built and tested: the kernel, the text model, and the server (`claudia_server/tables.py`:
the wire methods, box typing through `replace_text`, search kind `table`, the AI lens and allow-list; D1212). S2, S3, S4
and S6 are not built; the owner's order is: layout and clients (S2, S3), then odt/docx (S4), then stop.

| Slice | What | Needs |
|---|---|---|
| S0 | `claudia_core/tables.py`: entities, commands with inverses, `TableRegion`, `TableSource`, the `table` slots, `ObjectBody.table`, redaction; tests first: round trips, exact inverses, ids never reused, sorting and undo, region shrink, purity | the decision range |
| S1 | composes model and server: `TableDef` in `TextModel`, the anchor placement, `composes_tables.py`, events, the wire protocol (versioned and documented), search, the AI lens | S0 |
| S2 | the layout: `table.ts`, row-wise pagination, header repeat, tagged PDF | S0 (data), not S1 |
| S3 | the client: Insert ▸ Table…, in-flow editing, Tab and arrows, chip and options, Row/Column/Sort entries and keys in the manifest of the three shells, German catalog, BITV table markup, a check in Firefox | S1, S2 |
| S4 | files: odt, then docx; regular tables in, loss list for the rest, round trip on real documents | S1 |
| S5 | floating placement | `floating-objects` finished, S3 |
| S6 | E9.33 linked tables: the `TableSource` adapter in computes, pull, review, states, detach | S1, E12.2 |

S0 and S2 can be built in parallel by two agents: they meet only at the data the layout reads.

## 12. Where I would disagree

1. **Floating as the main placement** (§5). The object is right, the default is the flow.
2. **"Exactly like a computes named range".** The manipulation, yes (§4, "must not diverge"). The storage and the cell,
   no: a named range is a view over someone else's cells, and the cells are the thing a composes table is.
3. **Waiting for `floating-objects`.** Only the floating placement waits for it.
4. **A correction to my own earlier message:** I suggested formulas in a composes table's own scope, "from the start,
   since the engine is shared". It is not shared: it is in computes, the kernel may not hold it, and composes does not
   depend on computes. The plan above has a total row and linked tables instead.
5. **A computes display format is not wanted in a text table** (§4.2), although the owner's list has "cell formats
   beyond style (%, €)" for computes: that is computes' own.

## 13. Decisions and what is still open

Decided by the owner on 2026-11-18 (decision ids D1201–D1210): placement in the flow by default and floating as the
second placement (D1202); the kernel in `claudia_core` (D1201); a box is one paragraph and numbers are text (D1203);
no formulas in the first version, totals and sorting instead (D1204); merged boxes are any rectangle of neighbouring
boxes, for Word's sake, and not a prominent option (D1205); a look is a named bundle (D1206); 100 rows and 10 columns
(D1207); keys are assigned and may change (D1208); linked tables are own tables with a source, built in a second patch
(D1209).

Still open:

1. **Keys.** The keys of D1208 are provisional (Ctrl+Shift+F/L/G/H/X/Y); the owner will ask another agent about
   cross-app consistency, and BITV for the new dialogs and the table markup is not settled.
2. **Whether E12.2** (the link, the review dialog, the logged pull) is built first as its own piece, with tables as its
   first user, or inside E9.33.
3. **Custom looks**: a later decision, once the three built-in ones have been used.

## 14. Found on the way (size: 1 huge, 2 medium, 3 small)

- **Size 3, a smell that grew with this work: fixed (D1211).** `ObjectBody` had five generations of field sets and
  five mutually exclusive pointer fields; it has one `ref` now, and the kind says where it is looked up. The error
  messages of the object checks stopped changing with every new kind as well.
- **Size 3, found in S1 (fixed in S1).** A rendered container on a slide was printed without its picture, because
  `printable` looked for a wire `image` that never existed; it resolves the picture from the definition now.
- **Size 3, open.** Boxes are not in `reading_order` (D1212): a box cannot be a list item or a heading. Nobody asked for
  either; say so if a box should hold a list.
- Nothing of size 1 or 2. (The docx import does report `table` today; `import-export-coverage-2026-11-14.md` still
  says "no loss list at all", which is out of date.)

## 15. Not verified

- The layout engine (TypeScript), the web client and the GTK shell have no table code yet; nothing has been looked at
  in a browser or in GNOME.
- The odt and docx element names for tables are from memory of the formats, not yet checked against real files; both
  exports report `table` as a loss until the writers exist.
- The mock-ups were drawn and rendered with `rsvg-convert` (Inter is installed here, Fraunces is not: the serif in the
  PNG is a stand-in).

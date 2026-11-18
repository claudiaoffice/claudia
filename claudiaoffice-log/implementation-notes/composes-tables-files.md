# Tables in docx and odt (E9.32, S4)

Where things are, and why. Decision: D1214.

## Layout of the code

- `claudia_composes_io/_tables.py` — *no format in it*. `read_table(FileTable)` decides what a regular table is and
  builds the `TableDef`; `write_grid(TableDef)` gives the rows and cells to write (role styles, number alignment,
  merges as `cols`/`rows`/`covered`, the total row as words); `cell_look` turns a role style into the lines and fill of
  a cell; `put_tables` puts the tables of a file into a model; `tables_after`, `table_changes` and `table_styles` are
  what the writers and the patch modes ask of a model. The two format modules only know elements.
- `_docx_tables.py` — `file_tables(document)` finds the `w:tbl` of the body with the paragraph each follows,
  `read_tables` gives each its definition (`t1`, `t2`... for the regular ones), `write_table` writes one.
- `_odt_tables.py` — the same for `table:table` (`file_table`, `read_tables`), the automatic styles a table needs
  (`TableStyles`) and `write_table`.
- `docx.py` / `odt.py` call them: import puts the tables after the objects, export writes them after the paragraph
  they hang from, the loss lists count what the text does not hold, patch mode keeps them in step (docx in place, odt
  by falling back to a fresh file when a table changed).

## Things that are easy to get wrong

- A merge's *continuing* cells differ by format. A docx row below the start of a merge has one `w:tc` that spans the
  merge's columns (`w:vMerge` without a value); an odt row has a `covered-table-cell` for **every** position.
  `write_grid` puts the merge's width on the leftmost continuing position, the docx writer drops the positions it
  reaches over, the odt writer ignores it.
- The paragraph styles of the table roles must not carry the box into a file: `look_for` clears it for
  `TABLE_STYLE_IDS`. Otherwise LibreOffice draws a paragraph border inside every cell border.
- python-docx's `cell.merge` joins the paragraphs of the merged cells, so a table made with it has a cell of two
  paragraphs and is not regular. That is correct, not a bug; a table made by Word or LibreOffice does not.
- The empty paragraph between two adjacent tables comes back as an (empty) block on the next import.
- A baseline for `apply_edits_to_docx` must be what `docx_to_text` made of the same bytes: the regular tables are
  matched to the file by order and compared with the baseline's, else `UnsupportedEdit`.

## Checking

`soffice --headless --convert-to pdf` on a written file, and `--convert-to odt:writer8` / `docx` for a round trip that
the readers can be pointed at (LibreOffice rewrites merged tables with a different grid; the reader copes with it).
Word was not available.

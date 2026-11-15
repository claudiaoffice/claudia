# Import/export wiring: bug list for QA (branch `import-export-wiring`)

Kept by the developer for the QA role; updated with every patch. IDs `IEW-nn` are this branch's own; QA can move any of
them to `bugtracker.md` with the tracker's ID scheme. *Evidence:* every item was reproduced by a test or by a program
(LibreOffice 24.2.7 for ods and xlsx; Excel was not available). **Each fixed item has a test that failed before the fix.**
Status: `open` · `fixed` (in this branch) · `limit` (a limit by design, listed so QA does not file it).

## Open

| ID | Where | What QA sees | Found in |
|---|---|---|---|
| IEW-01 | composes, docx patch | In a Word file, a paragraph that contains a hyperlink: edit its text and the link's words are written twice (`see [the link]` becomes `the linkSEE the link!`). Needs the hyperlink to be edited in place. Existed before this branch. | slice 4 |
| IEW-02 | composes, docx export | The file's metadata is python-docx's: author "python-docx", created 2013. odt has its metadata from the log (D411); docx has none. | audit |

## Fixed

| ID | Where | What QA would have seen | Fixed in | Test |
|---|---|---|---|---|
| IEW-03 | composes server, odt patch | Changes of an edited odt dated 1970 and `meta.xml` not updated: the server called the patch without `info` and `change_times`. | slice 3 | `test_server_import.py`, odt patch tests |
| IEW-04 | composes, docx patch | Editing the words of a paragraph removed pictures, note marks and fields that were in it (every run went). | slice 4 | `test_docx.py` (picture kept) |
| IEW-05 | composes, docx patch | Pressing Enter (adding a paragraph) in an imported docx made the server write a new file that dropped the file's tables and pictures (`not-patched`). | slice 4 | `test_docx_blocks.py`, `test_server_import.py` |
| IEW-06 | computes, xlsx import | A sheet-scoped name came in on the wrong sheet when a chart sheet was among the sheets before it (`localSheetId` counts all sheets). | slice 5a | `test_xlsx_names.py::test_a_name_of_a_sheet_counts_the_sheets_the_model_does_not_have_too` |
| IEW-07 | computes, xlsx patch | Editing a header cell of a table in an imported xlsx left the table's column name unchanged; Excel repairs such a file ("removed table"). The column is renamed now. | slice 5a | `test_xlsx_names.py::test_a_header_cell_that_is_edited_changes_the_name_of_its_column_in_the_table` |
| IEW-08 | computes, ods import | A formula that used a named range of an ods came in as its value (the names were not read), so it stopped being live; a readable named range was also counted as lost (`named-range`). | slice 5a | `test_ods_names.py::test_a_formula_that_uses_a_name_of_the_file_is_a_formula_in_the_model` |
| IEW-09 | computes, ods/xlsx export | Names and tables defined in Claudia were silently missing from every export (no loss listed in xlsx). | slice 5a | `test_ods_names.py`, `test_xlsx_names.py`, server tests |

## Limits (by design, for now)

| ID | Limit | Why |
|---|---|---|
| IEW-L1 | Blocks cannot be moved relative to each other in a kept odt or docx (the server writes a new file and says `not-patched`). | The model has no moves. |
| IEW-L2 | A new docx paragraph is never put on the far side of a table. | The model has no tables; it cannot say which side the author meant. |
| IEW-L3 | Only the first section of a docx and the first master page of an odt are read and written. | Page setup is per document in the model. |
| IEW-L4 | A custom paragraph style is written to the file but not read back as a style (it is a name only). | Import has no style definitions yet. |
| IEW-L5 | A paragraph that ends a docx section is only emptied when removed; it returns as an empty block. | Keeps the two sections apart. |
| IEW-L6 | Padding without a border is a `style` loss in docx. | docx has no padding without a border. |
| IEW-L7 | The native-shell menus (GTK, Neutralino) have no Format ▸ List. | Out of scope of this branch; the web menus have it. |
| IEW-L8 | A table column in a formula (`Sales[Amount]`) is written to ods as the cell's value (loss `formula:reference`). | OpenFormula and LibreOffice have no such reference. xlsx keeps it live. |
| IEW-L9 | A table's colours by purpose and whether it grows are not in any file (loss `name:purpose`); a `SQL()` result name is not either (`name:result`); a table of one sheet is a plain name of that sheet (`name:table-scope`). | Files have no such thing. |
| IEW-L10 | An xlsx table whose header cell is not text, or two of whose columns have one name, is written as a plain range (`name:table-header`). | Excel would repair the file. |
| IEW-L11 | A table of a kept xlsx whose columns change is matched by place: a column inserted in the middle keeps the table-column settings of the column that was there. | The model has no column identity. |
| IEW-L12 | The ods names of one sheet are written at the end of the `table:table`; the standard's schema was not checked for this place (LibreOffice reads it). | See D457. |

## What to try (QA)

*Slice 5a, names and tables.* In the spreadsheet: define a name for a cell and a table (Tools ▸ Names…); use both in a
formula; File ▸ Download as .ods and as .xlsx; open both in LibreOffice (and Excel, which this branch could not): the
names are in the Name Box / Name Manager, the formula calculates, an xlsx table has its header as column names. Open
an existing xlsx with a styled table, add a row and a name in Claudia, export again: the table keeps its style and
grows by the row, the file's other names (print area, names that are formulas) are still there. The download dialog
lists `name` losses for purposes, `SQL()` results and tables of one sheet.

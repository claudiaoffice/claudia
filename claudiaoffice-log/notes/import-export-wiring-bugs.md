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
| IEW-10 | computes, xlsx export | A column that had only a look (a style on the whole column) was written 13 characters wide, not at the sheet's default: it looked wider in Excel and LibreOffice than in Claudia. | slice 5b | `test_xlsx_layout.py::test_a_look_only_column_does_not_get_a_width_of_its_own` |
| IEW-11 | computes, ods/xlsx | A column width or row height set in Claudia was missing from every export (xlsx did not even list it as a loss) and was dropped by an edit-and-reexport of an imported file; the ods import counted any file with sized columns as `layout`. | slice 5b | `test_xlsx_layout.py`, `test_ods_layout.py`, `test_server_import.py::test_a_resized_column_is_in_the_patched_download_and_no_loss` |

| IEW-12 | creates, pptx/odp export | A turned object came out of Claudia upright: pptx fresh export wrote no rotation (the patch did), odp wrote none and left an object that somebody turned in a file out of the model (`rotated-object`). | slice 7 | `test_creates_rotation.py` |
| IEW-13 | creates, pptx patch | Giving a text box, shape or picture of an imported pptx another description (alt text) changed nothing in the file. | slice 7 | `test_creates_pictures.py::test_a_text_box_is_given_a_description_in_a_kept_pptx_too` |
| IEW-14 | creates, pptx/odp import | Pictures never came in, so a deck with pictures lost them from the preview and their alt text was invisible (BITV); the print layout, paper and language of a deck were never in a pptx, the language never in an odp. | slice 7 | `test_creates_pictures.py`, `test_creates_setup.py` |

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
| IEW-L13 | A line a file does not size comes in at Claudia's default (96 × 26 px), not at the file's (Excel 64 × 20). | The model has no default per sheet. |
| IEW-L14 | An xlsx width is in characters of the file's Normal font (7 px each is Calibri 11). Our own files have Body text as Normal, so Excel and LibreOffice show a width 10–25 % wider than Claudia (LibreOffice: 150 px as 184). | Font metrics are not known to the converter. |
| IEW-L15 | Only the first 256 columns and 10,000 rows have their sizes read from a file; none of the rest is reported. A patch keeps them. | A file sizes every column, nobody sees past the used ones. |
| IEW-L16 | A resized ods column or row gets a new style, so a page break set on its old style is lost. A size beyond Excel's limit (255 characters, 409.5 points) is written at the limit (`layout:beyond-excel-limits`). | ods styles are not merged; Excel has the limits. |
| IEW-L17 | An odp object turned by anything but a plain rotation (a real skew, a scale) is still left out (`rotated-object`). The turn is whole degrees. | The model has no skew; 20.4° is 20°. |
| IEW-L18 | A cropped, flipped or stretched picture, one that is not PNG/JPEG/GIF/BMP/SVG, or an odp picture whose bytes are not in the package, stays in the file and is listed as `picture`. A picture added or removed in a kept pptx still means a new file (`not-patched`). | An image object keeps the picture's own proportions. |
| IEW-L19 | A pptx has no place for margins (other than the paper's own) or page numbers of the print setup, an odp none for the print layout (`not-written` / `print_setup`). The language of a kept pptx is not rewritten (`not-written` / `language`); a rendered text container comes back as a plain picture. | Files have no such thing; a deck can mix languages. |
| IEW-L12 | The ods names of one sheet are written at the end of the `table:table`; the standard's schema was not checked for this place (LibreOffice reads it). | See D457. |

## What to try (QA)

*Slice 5a, names and tables.* In the spreadsheet: define a name for a cell and a table (Tools ▸ Names…); use both in a
formula; File ▸ Download as .ods and as .xlsx; open both in LibreOffice (and Excel, which this branch could not): the
names are in the Name Box / Name Manager, the formula calculates, an xlsx table has its header as column names. Open
an existing xlsx with a styled table, add a row and a name in Claudia, export again: the table keeps its style and
grows by the row, the file's other names (print area, names that are formulas) are still there. The download dialog
lists `name` losses for purposes, `SQL()` results and tables of one sheet.

*Slice 5b, widths and heights.* In the spreadsheet drag a column wider and a row taller (or Format ▸ Column width…);
File ▸ Download as .xlsx and as .ods: both open in LibreOffice (and Excel) with the same columns and rows, and no
`layout` loss is listed. Open an imported file with sized columns, widen one, download again: the other columns, the
cells' looks and the rest of the file are as they were. Give a size up (reset it): the line is at the default size in
the next download. A column over 255 characters wide (about 1,785 px) is written at 255 and listed.

*Slice 7, creates.* Turn a box, a shape and a picture in a presentation (Format ▸ Rotate…), download as .pptx and .odp,
open both in LibreOffice (and PowerPoint): the objects are turned like in Claudia and no loss is listed. Open an odp
or pptx with turned pictures: the preview shows them (alt text in the object's description), move one and download again:
the picture is the same file, its alt text and turn as you left them. Set File ▸ Print setup to 6 slides a page on A4
landscape and download as .pptx: PowerPoint's print dialog says handouts, 6 per page, and the file's notes page is A4
landscape; margins and page numbers are listed as not written. Set the language to German and download as .odp and
.pptx: spell-checking in LibreOffice uses German. Open a PowerPoint deck with coloured shapes and bold words: the
download dialog lists `look` and `formatting`.

# Import/export wiring: bug list for QA (branches `import-export-wiring`, `import-export`)

Kept by the developer for the QA role; updated with every patch. IDs `IEW-nn` are this branch's own; QA can move any of
them to `bugtracker.md` with the tracker's ID scheme. *Evidence:* every item was reproduced by a test or by a program
(LibreOffice 24.2.7 for ods and xlsx; Excel was not available). **Each fixed item has a test that failed before the fix.**
Status: `open` · `fixed` (in this branch) · `limit` (a limit by design, listed so QA does not file it).

## Open

None known. (IEW-01, IEW-02 and IEW-20 were fixed on 2026-11-17, see below.)

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
| IEW-15 | computes, xlsx import | A workbook downloaded from Claudia as .xlsx and opened again was reported as lost `protection`: the empty `workbookProtection` element the writer carries protects nothing. | slice 5d | `test_xlsx_real_world.py` (empty workbookProtection) |
| IEW-17 | composes, odt patch | Editing the words of any paragraph of a text Claudia had written to odt (and imported again) added a copy of each style of the text to the file's `styles.xml` under a second name (`Remark_2`, `Definition_2`...): bloat and, in LibreOffice, a long list of unused styles. | slice 6a | `test_odt.py::test_a_text_of_this_app_edited_in_its_words_gets_no_style_added_to_its_file` |
| IEW-18 | composes, docx/odt export | Pictures of a text (images, rendered text containers) were missing from every .docx and .odt download, and a picture of an imported file was not shown; nothing said so. Their alt text (BITV 1.1.1) was lost with them. | slice 6a | `test_composes_pictures.py`, `test_server_import.py::test_a_picture_of_a_file_is_an_object_…` |
| IEW-16 | computes, xlsx export/import | Charts of a spreadsheet were missing from every .xlsx download and nothing said so; a chart of an imported xlsx was a plain loss and never shown. | slice 5d | `test_xlsx_charts.py`, `test_server_import.py::test_a_workbook_with_charts_comes_back_patched_…[xlsx]` |
| IEW-19 | creates, odp import | The words of a text box or shape that hung over the edge of the slide were dropped as `off-slide-object` - typically the body (outline) placeholder of a deck converted from a taller layout (e.g. by LibreOffice from PowerPoint): the slide showed its title and no content. An unturned box is now cut back to the slide and listed as `overhanging-object`. | slice 6b | `test_odp.py::test_a_box_that_hangs_over_the_slide_is_cut_back_…` |
| IEW-21 | composes, docx import | A text box written by Word or LibreOffice (a drawing and the picture kept for old readers, `mc:AlternateContent`) was counted twice as a frame, so the `frame` loss count was one too high and a box could not be told from its fallback. | slice 6b | `test_composes_boxes.py` (LibreOffice-built `docx-boxes`) |
| IEW-22 | composes, docx/odt patch | Restyling an object's words to a style the file already had (`Shape label`, `Remark`) wrote the style again under a second name (`Shape label 2`) and the words kept the old one. | slice 6b | `test_composes_boxes.py` (restyled words) |
| IEW-01 | composes, docx patch | In a Word file, a paragraph that contains a hyperlink: edit its text and the link's words were written twice (`see [the link]` became `the linkSEE the link!`). The link is now kept where its words are (D468); a link whose words were removed is dropped and listed as `removed-link`. Existed before this branch. | slice 8 | `test_docx_links.py` (7 cases), `test_docx.py` |
| IEW-02 | composes/computes/creates, docx/xlsx/pptx export | The file's properties were the template's: author "python-docx", created 2013, title "PowerPoint Presentation". They are the log's now: title, creator, created, last modified by, modified; application "Claudia" (D466). | slice 8 | `test_properties.py`, `test_server_composes.py::test_a_docx_says_when_it_was_made_…` and the xlsx and pptx twins |
| IEW-20 | creates, odp/pptx import and fresh export | A deck opened from a file and downloaded as a *fresh* .odp or .pptx lost its colours and sizes, and its page colour. Fills, outlines, sizes, colours, bold, italic, alignment and the page colour are read into styles and written again (D467); `look` is listed only for what the model has no property for. Checked by round trip through LibreOffice 24.2.7: the shape, its outline and its words keep their colours. **Not fixed** (see IEW-L31, L35): the vertical anchoring of words and the placement on the layouts of a template. | slice 8 | `test_odp.py` (looks, page colour, unread kinds, fresh export), `test_pptx.py` (looks, theme colours, fresh export, unread kinds), `test_slides_unwritten.py` |

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
| IEW-L20 | A chart tab is written to ods as a sheet with the chart in it (`chart:tab`); a chart that follows a name is written as the cells the name is now (`chart:source`); a turned chart stands upright (`chart:rotation`); a chart that reads nothing is not written (`chart:empty`). | A file has no tab for a chart, no named source, no turned chart. |
| IEW-L21 | Only clustered, upright, two-dimensional bar charts over cells of one sheet are read as charts; any other chart of an ods stays in the file and is listed as `chart`. Colours, fonts and the look of a chart another program drew are not read; the chart is shown in Claudia with Claudia's colours. | The model has only bar charts. |
| IEW-L22 | A chart another program drew is kept as it is when only its numbers, place, size or description change; when its definition (range, titles, legend, gridlines, series direction) is changed in Claudia it is drawn the way Claudia draws a bar chart (`chart:look`). | The model does not hold the look. |
| IEW-L23 | An xlsx chart pinned by two cells and drawn by Excel has the size of the cells it reaches, which uses the column widths of the file (7 px a character); Excel's own layout may differ by a few pixels. | Excel states no size for the frame. |
| IEW-L24 | A picture of a docx or odt comes in only when it is an image the app decodes, not cropped or flipped, in its own proportions, turned by nothing but a rotation, and not in a table, a header, a footer or a text box; any other stays in the file, is not shown and is listed as `picture`. | The model has floating images with a size and a turn, nothing else. |
| IEW-L25 | A picture is written without wrapping: the words do not flow around it (the model has none), so in Word and LibreOffice it lies over the text at its character; an imported picture that wrapped the words stays in the file but comes in as one that does not. | No wrapping in the model. |
| IEW-L26 | odt has no mark for a decorative picture (ODF 1.3): it is written without description and `decorative` is listed; it comes back as a picture with no description. docx has the mark. | The format. |
| IEW-L27 | An SVG in a docx is written with a PNG fallback that is empty unless the server has a rasteriser (`rsvg-convert`); `svg-fallback` is listed. Word before 2016 shows the empty picture. | A PNG fallback must be a raster. |
| IEW-L28 | A text box or shape of a docx or odt comes in only when it holds one paragraph of plain words (or none), is anchored in a paragraph, is one of the three outlines (circle, rectangle, triangle; an ellipse is a circle only when round), is not mirrored and has no line, wrap or effect the model lacks; any other stays in the file and is listed as `frame`/`shape`. Groups, boxes in tables, headers and footers, multi-paragraph boxes and custom outlines are not held. | The model has one paragraph per box and three outlines. |
| IEW-L29 | The look of a box (fill, outline) is written from its style but not read: a box of a file always comes in as `plain-box` / `plain-shape`, and `look` is listed when the file's differs. A patch that restyles a box draws it anew and the file's look is lost. The formatting of the words (bold, colour, size) is not held either (`formatting`). | D407 (looks are read in a later step). |
| IEW-L30 | Word 2007 shows nothing of a box written without the legacy fallback Word 2010+ keeps (`mc:Fallback`): our docx has none. Boxes of every kind share one stacking order only within their kind (pictures below boxes). | Kept small; Word 2010+ and LibreOffice draw them. |
| IEW-L31 | A look is read from what the shape itself says. What a placeholder takes from its layout or master (pptx), the vertical anchoring of words (top, middle, bottom), insets, autofit, and a text box's own fill or line are not read; a text box that has a fill or line is listed as `look`. A deck therefore opens with its words at the top of the box where the file centred them. | The model has one look for a box and no anchoring. |
| IEW-L32 | One page colour for the deck: the first slide's (white where the file says none). A slide with another colour is listed as one `look`; a gradient or picture page is not read. | The palette has one `page`. |
| IEW-L33 | The words of a box take their look from its first paragraph with words and its first run. Other runs that are bold, italic or underlined are listed as `formatting`, and so is a paragraph that is wholly bold (its bold is read into the style as well). | The model has one paragraph style for the words of a box. |
| IEW-L34 | A pptx colour made lighter, darker or translucent (`lumMod`, `tint`, `alpha`...) is read as the colour it names and listed as `look`; pptx colours of a theme are read through the master's theme part (fonts: E3.13). odp: a stroke width in another unit than a length, `draw:opacity`, `draw:shadow` and a dash are listed as `look`. | The model holds a colour only. |
| IEW-L35 | A fresh odp or pptx has a bare default master (layouts of the file's template, its art and its placeholders are not carried): the objects keep their places and looks but are no longer placeholders. A download patched onto the kept file keeps everything. | Templates and layouts are not in the model (E10.4, D375). |

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

*Slice 5c, charts to ods.* Make a bar chart over a table (Insert ▸ Chart…, floating on the sheet), give it a title and an
alt text, download as .ods and open it in LibreOffice: the chart is at its cell, reads the table, has the title and
the same colours; edit a number in LibreOffice and the chart follows. Open an ods with a LibreOffice bar chart: it
shows in Claudia as a chart; move and resize it, download again: LibreOffice draws it as it was, only moved. Change its
title in Claudia: the download dialog lists `chart` / `look`. A chart tab downloads as an extra sheet and says so.
Other kinds of chart in an ods are still not shown and are listed as `chart`.

*Slice 5d, charts to xlsx.* As 5c, with .xlsx: a chart over a table downloads and opens in Excel or LibreOffice at its
cell with its title, legend and colours; an Excel or LibreOffice bar chart shows in Claudia and comes back as it
was after a move. A chart of another kind (line, pie, stacked) stays in the file and is listed as `chart`. An xlsx
downloaded from Claudia opens again without a `protection` loss.

*Slice 7, creates.* Turn a box, a shape and a picture in a presentation (Format ▸ Rotate…), download as .pptx and .odp,
open both in LibreOffice (and PowerPoint): the objects are turned like in Claudia and no loss is listed. Open an odp
or pptx with turned pictures: the preview shows them (alt text in the object's description), move one and download again:
the picture is the same file, its alt text and turn as you left them. Set File ▸ Print setup to 6 slides a page on A4
landscape and download as .pptx: PowerPoint's print dialog says handouts, 6 per page, and the file's notes page is A4
landscape; margins and page numbers are listed as not written. Set the language to German and download as .odp and
.pptx: spell-checking in LibreOffice uses German. Open a PowerPoint deck with bold words in the middle of a line: the
download dialog lists `formatting` (and, since slice 8, `look` only for what the model cannot show).

*Slice 6a, pictures in composes.* Insert a picture into a paragraph (Insert ▸ Picture…) and give it a description; download
as .docx and as .odt and open both in Word/LibreOffice: the picture is at its place in the paragraph, as large and as
turned as in Claudia, and its alt text is there (Word: Picture format ▸ Alt text). Mark one decorative: Word shows the
"decorative" box ticked; the odt download dialog lists `decorative`. Open a Word or LibreOffice file with pictures: they
show in the text (inline ones too); move one, resize it, give it another description and download again: the other
pictures and the rest of the file are as they were. Remove a picture and download: it is gone from the file (odt: from the
package as well). A cropped or stretched picture stays in the file and is listed as `picture`.

*Slice 6b, text boxes and shapes in composes.* Insert a text box and a circle, a rectangle and a triangle into a paragraph
(Insert ▸ Text box / Shape), type words in each, turn one, give one a description; download as .docx and .odt and open both
in Word/LibreOffice: they are at their place in the paragraph, as large and as turned as in Claudia, with their words,
fill and outline. Open a Word or LibreOffice file with such boxes: they show in the text; move, resize and reword one and
download again: the other boxes, the pictures and the rest are as they were. Delete a box: it is gone from the file. Open an
odp whose body text is in a placeholder: the body text shows on its slide (IEW-19).

*Slice 8, properties, links and looks.* Download a text, a spreadsheet and a presentation of Claudia as .docx, .xlsx and
.pptx: File properties in Word, Excel and PowerPoint (or `unzip -p file docProps/core.xml`) show the title, your name as the
author and last modifier, the dates of the log and the application "Claudia", not python-docx and not 2013. Open a Word
file with a hyperlink in a paragraph, retype the words around the link in Claudia and download again: the link is
there once, on its own words; delete the linked words: the link is gone and the dialog lists `removed-link`. Open an odp
or pptx with coloured shapes, coloured and bold words and a coloured page, download it again as a new .odp and as .pptx
and open both in LibreOffice (PowerPoint): colours, outlines, sizes and bold are those of the original, the words
sit at the top of their boxes (IEW-L31) and the layouts of the template are gone (IEW-L35); the dialog lists `look` only
for gradients, dashes, shadows, lightened colours and the pages of other slides. A deck of Claudia's has no `look` loss.

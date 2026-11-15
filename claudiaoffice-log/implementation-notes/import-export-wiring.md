# Import and export wiring (D450–D469, branch `import-export-wiring`)

The audit (`import-export-coverage-2026-11-14.md`) found functions of the three apps that never reach the formats.
The work goes in slices, each a patch against the branch.

## Slice 1 — unwritten changes and loss lists (D450–D452)
`claudia_odf_io.unwritten_changes` compares the facets of a model before and after and reports the ones a converter
does not write; each converter has a `*_WRITTEN` set that shrinks as slices land.

## Slice 2 — composes lists (D453)
* odt: `_odt_lists.py` reads `text:list` trees as items (`ListReading`), writes them (`ListFlow`, `ListNames`) and
  makes `text:list-style` elements. The patch (`_Patch._plan`) decides for each block whether its element is kept,
  written again as part of a "region" (a list whose items changed), or new.
* docx: `_docx_lists.py` (`Numbering`, `read_lists`, `ListWriter`). python-docx cannot make a numbering part, so
  `numbering_in(create=True)` loads one.
* Found on the way: untouched pieces of a list that a patch continues need an `xml:id`, which is only known after the
  first piece was placed; hence the late serialisation in `XmlPart`.
* Property tests (`test_odt_lists.py`, `test_docx_lists.py`): random edits of items and definitions; the file must say
  the same lists as the model, and what was not touched must be unchanged.

## Slice 3 — composes page, language, styles, palette (D454, D455)
* `_layout.py`: units and language tags shared by both formats. `_odt_setup.py` / `_docx_setup.py` read, write and
  patch the page and the language (the odt patch edits the first master page and the default style in place; the docx
  writes the first section and the document defaults and owns the parts that change).
* `_style_look.py` turns the CSS a style sets (palette roles already replaced) into a `Look` in points and
  `#RRGGBB`; what it cannot say goes in `Look.unsaid`. `_odt_styles.py` (`StyleNames`, `style_xml`) and
  `_docx_styles.py` (`WordNames`, `write_styles`) write it. A style that is written replaces what the file had of it;
  a custom style never takes a name a file already has.
* The patch writes a style again only when its `Look` (or parent) differs from the baseline's, a new style when a
  paragraph needs it. Palette roles are not in the files, so a changed colour rewrites the styles that name it.
* Found on the way: the server's odt patch lacked `info` and `change_times` (fixed); a default model exports without
  a loss, so docx hyphenation is the document setting and padding is only a loss for a style with no border at all.

## Slice 4 — docx patch: paragraphs added and removed (D456)
* `_docx_blocks.py` has the three small facts about the body of a docx: `place` (after the paragraph before, else before
  the paragraph after), `remove` (a paragraph that ends a section is only emptied) and `hidden_content` (what goes with
  a removed paragraph). `docx.py` has `_BlockWriter` (new and changed paragraphs, as `text_to_docx` writes them) and
  `_patch_setup` (page, language, styles); `apply_edits_to_docx` is now their order of work.
* The model-based test (`test_docx_blocks.py`, eight seeds) adds and removes blocks at random in a file with a table and
  asks for the blocks back in order, and the table once.
* Not done: moving blocks (odt has the same limit); a new paragraph is never put on the far side of a table.
* Found on the way: editing the words of a docx paragraph removed every run, pictures included (fixed: only runs of
  words go). Still open: a paragraph with a hyperlink gets the link's words twice when its text is edited, because
  `paragraph.text` counts them and the `w:hyperlink` stays; this needs the hyperlink to be edited in place.

## Slice 5a — computes names and tables (D457)
* `_named.py` is what every format holds of a name (`writable`, `is_table`, `unheld` with the three details `result`,
  `purpose`, `table-scope`). `ods_names.py` reads (`scan`, `read_names`), writes (`global_elements`,
  `local_expressions`) and patches (`NamesPatch`) the ods; `xlsx_names.py` writes through openpyxl (`write_names`) and
  patches the package (`XlsxNamesPatch`: defined names in `workbook.xml`, table parts, `tableParts`, relationships,
  content types). `xlsx_read.name_entries` is the one reader of names; it keeps each name's element for the patch.
* The ods import reads the names *before* the cells (`_tables`), so that a formula with a name is a formula; the
  names a sheet can use are the workbook's and its own (`from_openformula(..., names=...)`).
* The server needed nothing: it already adds `*_unwritten_changes` to the patch's own losses, so the patches do not
  report names twice.
* Checked against LibreOffice 24.2.7: a name and a table written here are read by it (`Rate*10` calculates; the
  names survive its own re-save); `Sales[Amount]` in an `of:` formula is `Err:508` there, which decided D457's note on
  table columns. Excel was not available.
* Found on the way: `localSheetId` was read against the worksheets only (IEW-06); a header edit in a kept xlsx left
  Excel a table to repair (IEW-07).


## Slice 5b — computes widths and heights (D458)
* `layout_sizes.py` is what both formats share (`fit_width`, `fit_height`, `changed_sizes`, the read caps);
  `xlsx_layout.py` the xlsx units, `column_runs` and the Excel-limit loss; `ods_layout.py` the lengths, `read_sizes`
  (the sizes the automatic styles give) and the two style builders. `OdsLookWriter.column_style` / `row_style` hand out
  the style names, the same way `cell_style` does.
* xlsx: `XlsxLookWriter.sheet` writes the `col` runs and the `row` heights; `xlsx_read._row_and_column_looks` reads
  them; `SheetPatch.resize_columns` / `resize_rows` patch them. ods: `_Looks.row_sizes` / `column_sizes` into
  `_rows_of` / `_columns_of`; `_scan_table` reads; `_Patch._patch_lines` is what was the tail of `_patch_table`, with
  the heights next to the cells and the default cell styles of the rows.
* `"layout"` is now in both `*_WRITTEN` sets of `_unwritten.py`; the old tests that used a resize as their example of
  "an edit the file cannot hold" use a name with a purpose instead.
* Found on the way: an empty `row` element is falsy in lxml, so `rows.get(n) or new_row(n)` would have written a row
  twice (a warning of lxml; fixed before it shipped); openpyxl writes 13 characters for a column that has only a look,
  which this slice would have read back as a width (IEW-10).
* Checked against LibreOffice 24.2.7 (`soffice --convert-to`): sizes survive xlsx to ods, ods to xlsx and each format
  to itself; a LibreOffice file from a csv comes in with its narrow columns, patches, and opens again.

## Slice 5c — computes: charts to ods (D462)
* `claudia_odf_io` 0.4.0: `NS["chart"]`, `new_package(extra=…)` takes folder entries (`None` data = manifest only),
  `update_manifest(parts, add=, remove=)` for a patch.
* `claudia_computes.WorkbookModel.chart_cells(diagram_id)` is the one answer to "which cells does this chart read",
  for a named source too; the writer, the loss list and the patch all ask it.
* computes-io is four modules: `ods_charts.py` (writer, reader, `chart_losses`, `written_charts`; `plan_of` mirrors the
  model's `chart_figure` convention, and the reader accepts a chart only when its plan equals the one the model would
  draw for the bounding box of what it reads), `ods_chart_files.py` (`file_charts`: which frames of a file are charts,
  where, in which cell, how big), `ods_chart_patch.py` (`ChartPatch`: add, remove, move, resize, describe, redraw in a
  kept `content.xml`; chart tabs added as sheets) and the glue in `ods.py` (`_held_charts`, `_Patch._patch_charts`).
* `_unwritten.py`: `charts` is in `ODS_WRITTEN`; its facet is `tab <id>` / `object <id>` (item + definition), and the
  `objects` facet leaves out diagram objects, so a chart is counted once.
* A chart "ours" is recognised by comparing the part with what we would draw for the baseline: only then is it drawn
  again for a changed size; a foreign chart keeps its drawing unless its definition changed (`chart:look`).
* Found on the way: a chart tab whose diagram is gone made the loss list raise (now `chart:empty`); mypy found
  `new_package(extra=…)` too narrow for odp (now a `Mapping`).
* Checked against LibreOffice 24.2.7: our charts open and come back from LibreOffice as the same four specs (columns,
  rows, no header, one series), pdf export draws them, and LibreOffice's own bar charts are held with identical
  definitions. Library cases: new `ods-charts` (built by LibreOffice from our file; `_build_fixtures.build_ods_charts`
  needs `soffice`), `ods-beyond-claudia-chart` now sees the chart as an object and still keeps its parts byte for byte.

## Slice 7 — creates: rotation, pictures, print setup, language, pptx loss lists (D459–D461)
* `odp_transform.py` is the whole of ODF's turn (`transform_of`, `turned_box`, `angle_of`); `odp._placing` writes a
  turned object's size and transform (pictures too), `_Patch._moved` decides what a patch sets and takes off.
  `XmlPart.set_attributes(remove=…)` (claudia-odf-io 0.3.0) is the one splice that needed to be new.
* Pictures: `pictures.py` (what is held, the import record), `pptx_pictures.py` and `odp_pictures.py` (reading a
  `p:pic` / `draw:frame`). `_classify` of both converters returns `image`; the pptx patch moved into `_patch_shape`
  (it also writes a changed alt text now, for every kind of object).
* Language: `claudia_odf_io.language` is the odt code of composes-io moved down (composes-io imports it and wraps the
  patch's `OdfError` into its own `UnsupportedEdit`). `pptx_setup.py` has the print layout / paper (`write_print_setup`,
  `read_print_setup`) and the language of runs (`speak`, `spoken`). `_unwritten.facets(keeps_print_layout=True)`
  reduces `print_setup` to what a pptx cannot hold (margins other than the paper's own, page numbers).
* `pptx_import_losses` adds `look`/`formatting`/`link` by comparing a shape with what `slides_to_pptx` writes for the
  default style (`_default_looks`, built once per call).
* Found on the way: `slides_to_pptx` never wrote a rotation (IEW-12); the pptx patch never wrote a changed alt text
  (IEW-13); LibreOffice writes `skewX (-5E-017)` before every rotation it writes.
* Checked against LibreOffice 24.2.7: both files open (pdf export), a pptx with a turned picture becomes an odp that is
  read back with the same box, turn and alt text, and the other way round; the language of a pptx run is written by
  LibreOffice into run styles, not the default style, so it does not come back from there as a deck language.
* Library cases: `pptx-picture-and-language` (built), `odp-rotated-picture` (LibreOffice's own file, checked in); the
  two `beyond-claudia-image` cases now see the picture as an object.

## Slice 5d — computes: charts to xlsx (D463)
* computes-io: `chart_plan.py` (the plan of a chart, shared by ods and xlsx: `Series`, `Plan`, `plan_of`, `plan_from`,
  `spec_of`, `chart_losses`, `with_id`), `xlsx_charts.py` (writer `chart_xml`, reader `read_chart`, `file_charts`,
  `written_charts`, the geometry of cells for a `twoCellAnchor`), `xlsx_chart_patch.py` (`Drawings`, `ChartPatch`,
  `patch_charts`), glue in `xlsx.py`. `_unwritten.py`: `charts` is in `XLSX_WRITTEN`.
* The server passes the loss log to the xlsx patch (`losses=found`), as it does for ods.
* Held charts are numbered `o{n}` / `c{n}` in the order of the file, so the baseline model and the file agree on ids.
* Checked against LibreOffice 24.2.7: our xlsx charts open and render (title, axis titles, legend, gridlines, colours);
  LibreOffice's own xlsx bar charts are held with identical definitions. LibreOffice pins a chart by two cells and also
  states the frame's `xfrm`: that is the size read (the cells alone gave 392 px for a 480 px frame, LibreOffice lays
  columns out differently from 7 px per character). Excel was not available: its charts are tested by hand-built XML.
* Library case: new `xlsx-charts` (built by LibreOffice from our file; `_build_fixtures.build_xlsx_charts`).
* Found on the way: IEW-15 (empty `workbookProtection`), IEW-16 (charts missing from xlsx downloads, no loss).

## Slice 6a — composes: pictures to docx and odt (D464)
* composes-io: `_pictures.py` (which objects are pictures, losses), `_docx_pictures.py` (reader, writer, `PictureEdits`
  for the patch), `_odt_pictures.py` (reader, `PictureWriter`, `PicturePlan` for the patch), glue in `docx.py` / `odt.py`;
  `_unwritten.py`: `pictures` is in `_WRITTEN_BY_BOTH`, the facet `objects` is split into `pictures` / `objects` /
  `shapes` (the last two stay unwritten until 6b).
* Moved to shared packages so that creates and composes read pictures one way: `claudia_core.raster` and
  `file_pictures`, `claudia_odf_io.transform` and `pictures`, `paragraph.frames_of` / `offset_of` / `detach`.
* The server passes `rasterise` (the renderings' rasteriser, as creates does) to the fresh and patched docx and odt.
* The patch cannot move a frame between two paragraphs without a copy: the copy of the file's frame goes into the
  paragraph the text now says, the original is taken out of the paragraph it was in (every paragraph with frames to
  change is rewritten in a copy; byte-splicing keeps the rest of `content.xml`).
* Checked against LibreOffice 24.2.7: our docx and odt pictures open and render at their place; LibreOffice's own docx
  and odt are read with the same anchors and descriptions (library cases `docx-pictures`, `odt-pictures`, built by
  LibreOffice from our file); patched files (a resized and turned picture and a new one) open and show all pictures.
  Word was not available: its pictures are tested by hand-built XML (inline pictures, crops, tables).
* Found on the way: IEW-17 (the odt patch wrote every style of the app's own file again under a second name after any
  edit).

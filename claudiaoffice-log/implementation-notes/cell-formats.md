# Cell formats and number formats from and to xlsx and ods (E6.14, E6.18; D378, D379)

Patches 3b and 3c of the `real-world-docs` branch. What came in, where it lives, and what is left.

## Number formats (D378)

* `claudia_computes.numformats` — the model and the renderer.
  * `NumberFormat` (id, name, code, `to_name`) and `NumberFormatBook`, kept on `WorkbookModel.number_formats` and in
    its snapshot (state schema 10). The server answers `number_formats` with the book.
  * `check_code`, `parse` (sections, tokens, colour, condition, locale), `kind_of`, `render(value, code, symbols)`
    and `describe(code)` for a provisional name. `BUILTIN` holds Excel's numbered formats; 14 is `SHORT_DATE`, shown
    as the reader's short date.
* `claudia_core.StyleDef.number_format` and `StyleBook.number_format(id)` (inherited) / `set_number_format`. Written
  into a style's data only when set, so composes and creates write what they wrote before.
* `web/app/lib/number-format.ts` — the TypeScript twin of `render`. Both run the cases in
  `packages/claudia-computes/tests/number_format_cases.json`; a case added there is checked on both sides.
* `SheetGrid.vue` shows a number through the format of the cell's words style, in the reader's locale; a format's
  colour (`[Red]`) is the text's ink.
* `TEXT(value, code)` renders with English separators (D372 is still open).

## Looks of cells (D379)

* `claudia_computes_io.cell_looks` — the same for both formats:
  * `Look` (full CSS, code, what no style holds) and `LookImport`, which makes styles and formats from looks: Body
    text from the default look, named styles by name (or the workbook's own, when it comes back), provisional styles
    named by `difference_words` (`colour_name` gives the colour words).
  * `Dressing` hands out the style of a file's look once per workbook and counts the `look` losses; `paint` turns a
    sheet's `SheetLooks` into style ranges (rows and columns as layers, cells joined into rectangles, at most
    `MAX_STYLE_RANGES`).
  * For writing: `LookExport` (a cell's box and words styles as one `CellLook`: nearest named style, CSS with palette
    roles made colours, code) and `sheet_styling` (cells, rows and columns of a sheet for a file without layers).
* xlsx: `xlsx_looks` reads `styles.xml` and the theme (theme colours with tint, the old indexed palette, Excel's
  Normal by `builtinId="0"` whatever its name); `xlsx_read` notes each cell's, row's and column's `s`;
  `xlsx_write_looks` writes Normal's font, named styles and direct formats through openpyxl.
* ods: `ods_looks` resolves cell styles through their parents and the default cell style; `odf_numbers` turns number
  styles into codes and codes into number styles (maps for sections, LibreOffice's "every number" map, elapsed time,
  seconds with decimals); `ods_write_looks` writes `Default`, named styles in `styles.xml` and `ce…` automatic styles.
* The `date` loss is now counted only for a date no date format shows (ods) and is gone for xlsx, where the format
  says it.

## Changed looks in an edited file (D380)

* `cell_looks.restyling` compares two states of a sheet: every cell with a style range or content, and the runs of
  rows and columns, as `CellLook`s of each workbook. `changed_styles` first finds the styles whose look in a file
  differs (CSS, format, the named style they are written as), so a sheet none of them reaches is skipped.
* xlsx: `xlsx_restyle.StylesPatch` appends to `styles.xml` (fonts, fills, borders, numFmts, cellXfs; named styles
  to cellStyleXfs and cellStyles) and never changes an entry; `SheetPatch.restyle`, `restyle_row`,
  `restyle_columns` point cells, rows and columns at the new entries.
* ods: `ods_write_looks.OdsRestyler` makes `claudia-ce…` automatic styles (named after the file's own named styles)
  and the named styles the file lacks; `_Patch` sets a cell's `table:style-name` (a look-only change leaves its
  content as it is) and cuts repeated rows and columns where a restyled run begins or ends.

## Checked locally (the files stay out of the repository)

The owner's two real workbooks, read straight and after LibreOffice converted them to ods:

| | xlsx | via ods |
|---|---|---|
| planning workbook: styles (provisional) / formats | 479 (468) / 70 | 445 (434) / 69 |
| planning workbook: import time | 12.1 s (11–12 s before) | 9.4 s |
| game workbook: styles (provisional) / formats | 70 (60) / 3 | 70 (60) / 3 |
| `look` losses | center-across 369, rotation 28, shrink 1 | rotation 28, shrink 1 |

LibreOffice opens the new xlsx and ods files, and its own xlsx export of a new ods keeps the named styles. Restyling a
few cells and changing one provisional style of the planning workbook and writing the edit back takes 1.3 s (xlsx) and
9 s (ods, mostly reading the file again); both open in LibreOffice and openpyxl, and the import's `look` losses are
the same before and after.

## Left for later

* The to-name list needs grouping for an import with hundreds of provisional styles (E9.7).
* Choosing a number format in the style dialog; column widths and row heights in a new file (E6.16).

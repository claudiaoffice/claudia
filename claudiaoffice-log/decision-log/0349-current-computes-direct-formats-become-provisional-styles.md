---
id: D349
title: "A file's direct cell formats become provisional styles named by what differs; named styles keep their names; a new file writes them back as named styles and direct formats"
status: current
applies-to: computes
date: 2026-11-13
round: "Real-world documents: cell formats and number formats (branch real-world-docs)"
supersedes: [D314]
superseded-by: []
---

# D349 · A file's direct cell formats become provisional styles; a new file writes styles back as Excel and LibreOffice keep them

**Reading an xlsx or ods file turns the look of its cells into styles** (`claudia_computes_io.cell_looks`):

* the file's default look (Excel's *Normal*, whatever a localized Excel calls it; LibreOffice's *Default*) becomes
  **Body text**: its font, size and colour, and vertical alignment at the bottom as both programs have it. A font
  gets its free metric twin after it (`Calibri, Carlito, sans-serif`), so a sheet keeps its line breaks on a system
  without the original;
* **each named style the cells use becomes a style of the same name**, based on Body text. A name the workbook has
  already gets a number (`Note 2`), unless the style is the workbook's own come back — same name, same look, its
  palette roles taken as the colours a file writes for them — which is then used as it is;
* **each different combination of direct formats becomes one provisional style** (`to_name`), based on the named
  style it deviates from and named by what differs, in the order a person reads a cell: `Body text · bold, light
  grey fill, line below, MWh`. Up to 60 characters; what does not fit ends in `…`; equal names get a number. They
  wait in the *to name* list (E9.7);
* the cells, rows and columns get those styles as style ranges in both slots (D311): a row or a column with a look of
  its own is a row or column range; a cell needs a range only where its look is not its row's or column's; runs of
  equal cells are joined into rectangles. When a sheet would hold more than `MAX_STYLE_RANGES` ranges, the largest
  rectangles are kept and the cells of the others counted as a loss (`look`: `too-many-ranges`).

Whatever a look has that no style can hold is counted per cell as a `look` loss naming it: `rotation`, `pattern`,
`gradient`, `center-across`, `fill`, `shrink`, `diagonal`, `superscript`, `double-underline`, `vertical-spread`,
`number-format`. A date shows as a date through its format, so a date is a loss (`date`) only where no date format
shows it. The original file still holds all of it: an edit written back with `apply_edits_to_xlsx` /
`apply_edits_to_ods` changes only the edited cells (D341, D413).

**A new xlsx or ods file writes the styles back the way the programs keep them**: Body text is the file's *Normal* or
*Default*; a style with a name a person gave it is a named cell style of the file; a cell's look is its words
style's nearest named style with the cell's own look on top as direct formats — so a provisional style goes out as
the direct formats it came from. Row and column ranges become row and column formats (xlsx) or default cell styles
(ods); the cells of other ranges are written one by one, up to `MAX_EXPORTED_CELLS` per sheet (`look`:
`too-many-cells` beyond). Palette roles are written as the colours they have now; a colour with transparency is laid
over white.

**Notes.** Asked of the owner while patch 3 was planned (2026-11-13): "Provisional styles (Recommended)" and "By what
differs (Recommended)". This supersedes D314 (no cell styles to or from xlsx in the styles round) and the part of
D306 that said an import lists a cell's direct formats as unmapped instead of making styles of them; the rest of
D306 — no direct formatting in claudia — stands, and is why the formats become styles. A real planning workbook
gives some 470 provisional styles: an import shows what the file really has, and the to-name list will need grouping
(by parent, by what differs) to stay usable — a follow-up for E9.7. Writing a restyled cell back into an *edited*
file (its `styles.xml` or automatic styles) is D350.

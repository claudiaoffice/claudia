---
id: D1233
title: "Computes writes the pictures floating on its sheets to XLSX and ODS, in a fresh export"
status: current
applies-to: computes
date: 2026-11-19
round: "Object interaction in the three apps (branch object-interaction)"
supersedes: []
superseded-by: []
---

# D1233 · Computes writes the pictures floating on its sheets to XLSX and ODS, in a fresh export

**Decided by the owner 2026-11-19 ("Computes needs to write floating objects as well to XLSX and ODS, in a patch of its
own"). Built.** Computes has no text boxes and shapes (D1232), so its floating objects are charts (written since D462/D463),
**pictures (an image, and a rendered container's picture, D390) and nothing else; pictures are what is written now.**

- *XLSX.* An `xdr:pic` in the drawing of the sheet, pinned by a `oneCellAnchor` to its cell with the size the picture is,
  in the same drawing as the sheet's charts and in the order they are stacked. A turn is the `rot` of its `a:xfrm`; the name
  and what it says are on its `cNvPr` (`name`, `descr`), and a decorative picture carries Office's mark. The bytes are a part
  of their own (`xl/media/`), one for what is shown however many pictures show it.
- *ODS.* A `draw:frame` with a `draw:image` in the sheet's `table:shapes` (where its charts are), with `draw:z-index` for the
  stacking, a `draw:transform` for a turn (`claudia_odf_io.transform_of`, the same words as odp and odt), `svg:desc` for what it
  says; the bytes are a part under `Pictures/`. ODF 1.3 has no way to say a picture is decorative: reported (`decorative`).
- *SVG.* Drawn as a PNG where the server has a rasteriser (as for composes and creates, D464). Without one, XLSX gets a blank
  picture with the SVG beside it (what Office 2016 and later write; others show it empty) and ODS gets the SVG itself;
  both say `svg-fallback`. A rendered container nothing has been drawn for is left out (`rendering-pending`).
- *Losses.* Pictures are no longer an `object` loss of a fresh export. **In an edit of an imported file they still are**:
  the patch of a kept file does not add pictures yet (tracker CODE-66), as it does not add pivot tables. A text box or a
  shape, which a model may hold but computes does not make, is reported as before.

**Not in this decision.** Reading pictures from an XLSX or ODS (they stay in the file, are counted as `picture` on import,
and survive an edit; tracker CODE-67).

**Notes.** Applies D390, D462, D463, D1232. Code: `claudia_computes_io/_pictures.py` (what both formats take from the model),
`xlsx_pictures.py`, `ods_pictures.py`; tests `packages/claudia-computes-io/tests/test_pictures.py`; scenarios
`specs/computes-pictures-in-files.md`.

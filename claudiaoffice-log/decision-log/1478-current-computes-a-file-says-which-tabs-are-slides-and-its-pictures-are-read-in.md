---
id: D1478
title: "An xlsx or ods file says in its custom property \"Claudia slides\" which tabs are slides and at what size; a tab it names that has kept its name and has no cells is read back as a slide; the pictures of a file are read in (CODE-67)"
status: current
applies-to: computes
date: 2026-11-24
round: "E6.31 Slides in computes, step 5b (branch e6-31-slides-in-computes)"
supersedes: []
superseded-by: []
---

# D1478 · The mark of the slides, and the pictures of a file

- **The mark.** A file written from a workbook with slides has the custom property "Claudia slides": in xlsx
  `docProps/custom.xml` (text, `vt:lpwstr`), in ods a `meta:user-defined` of the type string. Its value is
  `{"slides": [names of the slide tabs], "px_per_unit": 1.0}`. Office and LibreOffice show it under the file's custom
  properties and keep it when they save. A workbook without slides writes none.
- **Read back.** A tab the mark names is a slide while it has that name, no cells, and every drawing on it fits a
  slide at the size the mark says; its drawings are where they are on it, in units of the slide. A tab renamed or typed
  into in another program, or one whose drawings no longer fit, is a sheet, and its drawings hang at their cells.
- **Pictures (CODE-67).** The pictures of a file come in as image objects on sheets and slides alike, when the model
  can show them as they are (`claudia_core.file_pictures`: decoded, not cropped, not flipped, in their proportions),
  with the file's name, description, decorative mark and turn. Every other picture stays in the file and is reported as
  `picture`. Their ids follow the charts' (`o1`… are the charts, then the pictures).
- **Names.** A chart or a picture is written with its name (`cNvPr name`, `draw:name`) and read back with it, unless
  another thing of the workbook has that name.
- **Shared code.** The custom properties of a package are `claudia_opc_io.custom_properties` and
  `set_custom_properties`; the user-defined properties of an ODF file `claudia_odf_io.user_defined` and `new_meta`'s
  `properties`. What a DrawingML drawing says of itself (turn, crop, the part a picture draws, decorative) is
  `claudia_opc_io.drawingml`, which composes' docx readers use too; an ODF picture frame the model holds is
  `claudia_odf_io.held_frame`, with `graphic_styles` and `pixels`, which composes' odt readers use too.

**Why.** Agreed with the owner on 2026-11-24 (answers Q3, Q6, Q7 of step 5): without a mark a slide comes back as a
sheet; with a property every program keeps, a round trip through Claudia is exact and a tab someone else changed is
what they made of it.

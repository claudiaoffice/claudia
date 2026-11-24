---
id: D1480
title: "The presentation's odp and pptx converters take a box's elements, outlines and DrawingML marks from claudia_odf_io and claudia_opc_io (CODE-84); an automatic style wins over a common style of the same name"
status: current
applies-to: all
date: 2026-11-24
round: "E6.31 Slides in computes, CODE-84 (branch e6-31-slides-in-computes)"
supersedes: []
superseded-by: []
---

# D1480 · creates I/O on the shared box code

- **odp** draws a text box and the three outlines with `claudia_odf_io.outline_element` and `put_words`, fills and
  outlines them with `fill_and_line`, reads the graphic styles of a file with `graphic_styles`, what a style says with
  `odf_properties`, and the outline a custom shape names with `OUTLINES` (which knows the `ooxml-*` names LibreOffice
  gives PowerPoint's presets, now for texts and workbooks too).
- **pptx** names its outlines by `claudia_opc_io.PRESET`, marks a decorative object with `mark_decorative`, writes an
  SVG beside its picture with `add_svg` (computes' xlsx too), and reads a picture with `shown_part`, `turn_of` and
  `is_decorative`.
- **Stays in creates-io:** the readers of a shape's look (`_pptx_looks`, `_odp_looks`, D467), which turn theme colours,
  dashes and line widths into styles of the deck; `look_in` and `box_look` only say whether a box looks as its style.
- **Of two graphic styles of one name** (an automatic one in `content.xml`, a common one in `styles.xml`),
  `graphic_styles` keeps the automatic one, as odp did; composes' odt and computes' ods read it so too.
- **Written stroke width** of an odp shape is in points (`fill_and_line`), where odp wrote centimetres; a shape without a
  `stroke-width` says `0pt`, the thinnest line, as before it said none.

**Why.** CODE-84: one copy of the code of a box in a file, for the three apps (the owner asked for no duplication in
the export code, 2026-11-24).

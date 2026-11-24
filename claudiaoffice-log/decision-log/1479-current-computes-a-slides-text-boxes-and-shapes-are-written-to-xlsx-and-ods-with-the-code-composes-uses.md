---
id: D1479
title: "A slide's text boxes and shapes are written to xlsx and ods in the look of their styles and read back with them; the code of a box in a file is shared with composes"
status: current
applies-to: computes
date: 2026-11-24
round: "E6.31 Slides in computes, step 5c (branch e6-31-slides-in-computes)"
supersedes: []
superseded-by: []
---

# D1479 · Text boxes and shapes on a slide's tab

- **Written.** A text box and a shape that is a circle, a rectangle or a triangle on a slide is written on its tab
  where it is: xlsx an `xdr:sp` (preset `rect`, `ellipse`, `triangle`; a text box marked `txBox`), ods a `draw:frame`
  with a `draw:text-box`, a `draw:rect`, `draw:ellipse` or the triangle's `draw:custom-shape`. Its fill and line are the
  look its style gives it (D465). Its words are in the look of their style: in ods a named paragraph style called as the
  style is (`style:display-name` its name), in xlsx direct formatting of the run (font, size, bold, italic, underline,
  strike, colour) and the paragraph's alignment, since a drawing of an xlsx has no paragraph styles (owner, Q7′ (c)).
  A box on a sheet is still not written (`object`, D1232).
- **The mark** keeps, by the name of each box, its style and the style of its words (`styles` in "Claudia slides",
  D1478). Read back, a box gets them while the workbook has them and the file still shows the look of its style; a box
  restyled or renamed in another program has the plain style (`plain-box`, `plain-shape`) and the import says `look`
  (D465). A box of a tab that is read as a sheet stays in the file and is reported, as before.
- **Losses.** No `object` for a box on a slide; `authorship` for words of a box whose writers are known; in ods
  `decorative` for a decorative box (ODF 1.3 has no mark for it).
- **Shared code.** What a box looks like in a file (`BoxLook`, `look_of`, `is_written`) and its OpenDocument elements
  (`box_element`, `graphic_properties`, `held_box`, `box_look`, `odf_properties`) are `claudia_odf_io.boxes`; how
  DrawingML fills and outlines a shape and what a shape says of its look (`solid`, `outline`, `look_in`, `PRESET`,
  `SHAPE_OF`, `UNKNOWN`, `EMU_PER_POINT`) are `claudia_opc_io.drawingml`. Composes' docx and odt converters use them;
  they had them. The look sits beside the ODF layer, not in the core as the architecture of step 5 said: a look is
  counted in EMU, a unit of the packages, and the core knows no package.

**Why.** Agreed with the owner on 2026-11-24 (Q2, Q7′ (c)). Writing a box in the look of its style is what composes does
(D465); the mark makes a round trip through Claudia exact, and a box someone else changed is what they made of it.

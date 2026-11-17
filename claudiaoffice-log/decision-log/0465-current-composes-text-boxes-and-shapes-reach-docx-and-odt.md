---
id: D465
title: "Text boxes and shapes floating over a text are written to docx and odt as drawings at their character, and a drawing of a file is a box of the text when the model can hold it"
status: current
applies-to: composes
date: 2026-11-15
round: "Import and export wiring (branch import-export-wiring)"
supersedes: []
superseded-by: []
---

# D465 · Text boxes and shapes floating over a text reach docx and odt, and come back

**A text box or a shape (circle, rectangle, triangle) of a text is a drawing in the paragraph it hangs from, at the
character it hangs from, not wrapping the words. It is read back as the same kind of object with its words, size, turn
and description, and a kept file can add, remove, move, resize, turn, reword and describe boxes without touching the ones
nobody changed.**

**Notes.**

* *docx.* A `wps:wsp` in a `w:drawing` (`wp:anchor`, wrapNone), its outline `a:prstGeom` (`ellipse`, `rect`,
  `triangle`), its turn `a:xfrm rot`, its words one `w:p` in `wps:txbx/w:txbxContent` in the Word style of the words'
  style, `wp:docPr descr` for the description. A text box is flagged `txBox="1"`; an invisible rectangle with words
  (what LibreOffice writes for a text box) is read as a text box too. The drawing counter is shared with the pictures so
  that no two `wp:docPr` have one id. Word's legacy copy of a box (`mc:Fallback`) is not a second frame (IEW-21).
* *odt.* A text box is a `draw:frame` with a `draw:text-box`; the shapes are `draw:rect`, `draw:ellipse` (also read:
  `draw:circle`) and, for the triangle, a `draw:custom-shape` of type `isosceles-triangle`; the graphic style
  `Claudia_box_N` holds fill, outline, no wrapping, in front, and auto-grow off (LibreOffice would shrink a shape to its
  words otherwise).
* *Ids.* Boxes read from a file are `x{n}` in the order of the file (pictures stay `o{n}`), so the baseline model and the
  file agree on ids.
* *Looks.* Fill and outline are written from the resolved style of the object (`colour_of` over the page colour, EMU width)
  and not read back (as D407 for creates): a box of a file is `plain-box` / `plain-shape`, and `look` is listed when the
  file's fill or outline differs from the model's (`BoxLook.matches`, a width tolerance of a fiftieth of a point).
* *Patching.* A box that is gone is taken out; one that moved to another paragraph or whose paragraph was rewritten is
  lifted and put back; words, description, size, turn and the style of the words are changed in place; a change of kind,
  outline or object style draws the box anew (the foreign look is lost: `look`); a new box is written. `BoxEdits`
  (docx) and `BoxPlan` (odt) have the interface of `PictureEdits` / `PicturePlan`.
* *Shared code.* `points_of`, `colour_of`, `parse_colour` moved to `claudia_core.looks`, the three primitives and the
  styles of a box to `claudia_core.shapes` / `file_boxes`, `shapes_of` to `claudia_odf_io.paragraph`.
* *Unwritten changes (D450).* `objects` and `shapes` are now written by both formats, so they are no `not-written`
  facets.
* *Not here.* Groups, boxes in tables, headers, footers, multi-paragraph boxes, custom outlines, the formatting of the
  words of a box, wrapping, the stacking of boxes and pictures among each other (IEW-L28..L30).

*Found on the way (same slice):* an odp whose layout is taller than its slide (a body placeholder extending below the
bottom edge) lost the words of the box; an unturned box is now cut back to the slide and listed as `overhanging-object`
(IEW-19, in `claudia-creates-io`; the rule "an object is on the slide" of D412 holds for what is modeled).

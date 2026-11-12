---
id: D907
title: "Floating objects print where they hang, over the text and cut at their border"
status: current
applies-to: composes
date: 2026-11-12
round: "Pages, print preview and PDF (branch layouting)"
supersedes: []
superseded-by: []
---

# D907 · Floating objects print where they hang, over the text and cut at their border

**A floating object of a text is printed with its top left at the character it hangs from (D179), moved only as far as needed to stay inside the margins across and above the bottom margin, over the text (which does not wrap around it) and cut at its border (D182).** Its size is in CSS pixels. Text boxes and shape labels are laid out by the same paragraph code as the text; shapes are drawn from their outline (arcs as curves, computed the same in every engine); pictures in PNG, JPEG, GIF (the first frame) and BMP are embedded, decoded by the library itself. SVG pictures and charts cannot be printed yet: the preview draws a dashed frame and says so. composes' server gains the read methods `objects`, `images` and `shapes`, which the preview asks for when it opens.

**Notes.** The composes web client does not show floating objects in the text yet (they arrive by import); the preview is the first place they are drawn in composes, so where an object goes on a page had to be decided here. Rotation is whole degrees, from a table of sines (D910).

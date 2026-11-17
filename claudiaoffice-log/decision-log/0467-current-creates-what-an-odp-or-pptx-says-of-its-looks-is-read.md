---
id: D467
title: "The looks of the objects of an odp or pptx, and the colour of its page, are read into styles of the model, and a fresh export writes them again"
status: current
applies-to: creates
date: 2026-11-17
round: "Import and export wiring (branch import-export), IEW-20"
supersedes: []
superseded-by: []
---

# D467 · Looks of an imported deck are read (the "later step" that D407 and D465 left)

**A fill, an outline, a size, a colour, bold, italic, a font name and a text alignment that a file says of a text box or a
shape are read into styles of the model, one style for each look the deck has; the colour of the first slide's page
is the palette's `page`. A fresh odp or pptx writes them (and the page colour) again, so a deck opened from a file and
downloaded anew keeps its colours. What the model has no property for is said once for each object: `look`.**

**Notes.**

* *Why.* QA opened an odp, downloaded it as a *fresh* odp and found the colours gone (IEW-20). D407 (styles by name only, for odt) and
  D465 had left looks of files unread because the model had nowhere to put them; but the model has styles, and a style is what a look is.
* *`LookBook` (`_file_looks.py`).* Makes `file-outline-N` (kind `outline`) and `file-paragraph-N` (kind `paragraph`)
  styles, based on the built-in style of the object's kind (`plain-shape`, `body-text`, `shape-label`...), once for each
  distinct look. A property that the base style already says (same colour once resolved over the page, size within
  0.3 px, same first font) is not repeated, so a file that Claudia wrote comes back with the styles it had and no
  `file-*` style at all.
* *odp (`_odp_looks.py`).* A `StyleIndex` of the named styles of `content.xml` and `styles.xml` (parents followed): the
  graphic style of the shape and, for words, the presentation style, the paragraph style and the first span's text style,
  the nearer one winning. The page colour comes from the drawing-page style of the slide, else of its master page.
* *pptx (`_pptx_looks.py`).* The shape's own `spPr` fill and line, else the theme colour its `p:style` points at; the first
  run's size, bold, italic, colour, font (`a:latin`), the paragraph's alignment, the `fontRef` colour (white words in
  a PowerPoint shape). `Theme` resolves `schemeClr` and `sysClr` through the master's theme part. The page: the
  slide's `p:bg`, else its layout's, else its master's.
* *One page colour for the deck.* The palette has one `page`; it is the first slide's, white where a file says none.
  A slide whose page differs from it counts as one `look`.
* *Fresh export.* odp: `fo:font-weight`, `fo:font-style`, `fo:font-family` (not the built-in stack, which nobody chose),
  a drawing-page style with the page colour on each `draw:page`. pptx: bold, italic, font name, paragraph alignment,
  slide background. Both already wrote fill, outline, size and colour.
* *`look` means "not shown".* It is listed when a file says something the model has no property for (a gradient,
  a picture or a pattern fill, a dash, a shadow or glow, a colour made lighter or translucent: the colour it names is
  read, and the variant is listed), when a text box has a fill or line (the model has none for boxes), or when a slide's
  page differs from the first slide's. The download dialog lists it as before. A claudia-made deck has none.
* *Not here.* Vertical anchoring of words, insets, autofit, what a placeholder takes from its layout (only what the shape
  says itself is read), theme fonts (`+mn-lt`), the formatting of runs after the first (still `formatting`), per-slide
  page colours, gradients (IEW-L31..L35). The layouts and masters of the file are still not carried by a fresh file.

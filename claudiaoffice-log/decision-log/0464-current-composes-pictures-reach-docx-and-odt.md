---
id: D464
title: "Pictures floating over a text are written to docx and odt as pictures at their character, and a picture of a file is an object of the text when the model can show it as it is"
status: current
applies-to: composes
date: 2026-11-15
round: "Import and export wiring (branch import-export-wiring)"
supersedes: []
superseded-by: []
---

# D464 · Pictures floating over a text reach docx and odt, and come back

**An image object of a text (and a rendered text container, which is the picture last drawn from its text, D394) is a
picture in the file: a drawing in the paragraph it hangs from, at the character it hangs from, not wrapping the words
(that is what the model has). It is read back as the same object, with its description, its size and its turn, and a
kept file can add, remove, move, resize, turn and describe pictures without touching the ones nobody changed.**

**Notes.**

* *The model.* Objects hang from a character of a block (`BlockAnchor(block, offset)`) and never change their
  paragraph: moving one to another paragraph is a delete and an insert. Imported pictures are `o{n}` in the order of the
  file, so the baseline model and the file agree on ids.
* *docx.* `wp:anchor` (wrapNone, offset 0 from column and paragraph; an inline picture is also read, as a floating one),
  `wp:docPr descr` for the alt text and Word's decoration mark (`adec`) for decorative; `a:xfrm rot` for the turn. An
  SVG is `asvg:svgBlip` with a PNG next to it that every program draws (`rasterise` draws it, else it is empty and
  `svg-fallback` says so). Positions follow python-docx's `paragraph.text`.
* *odt.* `draw:frame` with a `draw:image`, `text:anchor-type="char"`, the graphic style `Claudia_20_picture`
  (no wrapping, in front); `svg:desc` is the description; `draw:transform` the turn. ODF 1.3 has no mark for decoration:
  a decorative picture is written without a description and `decorative` says so. An SVG is written as itself (a
  rendered container as a PNG when there is a `rasterise`).
* *What is read.* A picture of a file is the model's when it is an image the app decodes whose bytes are in the package,
  not cropped, not flipped, in the proportions of the picture itself and turned by nothing but a rotation. Everything
  else stays in the file and is `picture` in the import losses (`frame` stays for what is no picture). The shared
  code moved: `claudia_core.file_pictures` / `raster` (how a picture becomes an image object), `claudia_odf_io.pictures` /
  `transform` (frames and turns), used by creates as well.
* *Patching.* docx: a paragraph whose words are written again gets its pictures as marks inside the writer; the pictures
  of a paragraph left as it is are put in place afterwards (a run is cut only where one must be). The package keeps its own
  relationships and content types when pictures were added or removed (orphan media stays, as `reconcile` cannot drop
  parts). odt: the paragraph is copied, its held frames taken out, its words written, then each frame put at the offset
  the text says (a copy of the file's frame, changed only in what changed); media and manifest follow; an image no frame
  shows any more leaves the package.
* *Losses.* New: `decorative` (odt), `svg-fallback` (docx), `svg-picture` (odt, a rendered container nothing could draw
  as a PNG), `rendering-pending` (a rendered container nothing has been drawn for is left out), `picture`.
  `pictures` is written by both formats, so it is no `not-written` loss.
* *Not here.* Text boxes and shapes of a text (slice 6b); pictures in tables, headers, footers, text boxes; cropped,
  flipped, stretched pictures; wrapping.

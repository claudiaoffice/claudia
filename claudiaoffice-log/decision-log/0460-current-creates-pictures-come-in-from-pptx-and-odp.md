---
id: D460
title: "Pictures of a pptx and an odp come in as image objects and are edited in the kept file"
status: current
applies-to: creates
date: 2026-11-15
round: "Import and export wiring (branch import-export-wiring)"
supersedes: []
superseded-by: []
---

# D460 · Pictures of a pptx and an odp come in as image objects and are edited in the kept file

**A picture of a file the model can hold as it is shown becomes an image object with its asset, its alt text and its
turn. Every other picture stays in the file and is reported as `picture`. In a kept file a picture can be moved,
resized, turned and described; its bytes are never rewritten.**

**Notes.**

* *Which pictures.* The bytes are an image the app decodes (PNG, JPEG, GIF, BMP, SVG), it is not cropped (pptx
  `srcRect`, odp `fo:clip`) or flipped, it has the picture's own proportions (the model's image objects keep them; a
  stretched picture would change on the next write) and, in an odp, its bytes are in the package. A pptx picture with an
  SVG beside its fallback (how PowerPoint 2016 and our export write one) comes in as the SVG.
* *What the file says.* The alt text (`descr`; `svg:desc`, else `svg:title`) is the description; PowerPoint's
  decorative mark makes the object decorative. Text boxes and shapes of a pptx get their alt text read the same way
  (they are written already). A file has no importer of ours: the import record says `file`, the file's own name for
  the picture and no time (1970), which the model needs and nothing shows.
* *Ids.* Objects are numbered by their place in the deck over text boxes, shapes *and* pictures now, so the ids of a
  deck with pictures differ from before. Nothing stores them across an import: the baseline of a kept file is
  made from the file again.
* *Patching.* pptx: `_patch_shape` (position, size, turn, and the alt text when it changed, for every kind of object;
  an image has no words or look to write). odp: the frame's attributes and `svg:desc` (written, replaced or taken off).
  The picture part and its relationship are not touched.
* *Not done.* A picture added or removed in a kept pptx still makes the server write a new file (`not-patched`):
  that limit of the pptx patch is the same for every object. Rendered text containers (D390) are pictures in a file:
  they come back as plain pictures, without their source.

---
id: D459
title: "A turned object is turned in the files: rotation is written to odp and pptx, read from both, and patched"
status: current
applies-to: creates
date: 2026-11-15
round: "Import and export wiring (branch import-export-wiring)"
supersedes: []
superseded-by: []
---

# D459 · A turned object is turned in the files: rotation is written to odp and pptx, read from both, and patched

**The turn of an object (`RotateObject`, whole degrees clockwise) reaches both presentation formats on every path: a fresh
file, an import and a patch of a kept file. An odp object that is turned only by a plain rotation is no longer left
out of the model.**

**Notes.**

* *pptx.* `slides_to_pptx` never wrote the turn (the audit had it right for the patch only): it sets `rot` of the shape's
  `a:xfrm` now. Import and patch already did.
* *odp.* ODF turns an object with `draw:transform="rotate (a) translate (x y)"` and no `svg:x`/`svg:y`: the object is
  drawn at its size with its top left corner at the origin, turned about that corner, then moved. `a` is in radians and
  counts counter-clockwise. The model's box `(x, y, w, h)` is the box *before* the turn, and the object turns about its
  centre, so the corner moves to `centre − R(a)·(w/2, h/2)` (`odp_transform.py`). Checked against LibreOffice 24.2.7
  both ways: a pptx shape turned by 30° comes out of it as `rotate (-0.5235…) translate (…)`, and what we write is read
  back with the same box.
* *What is read.* `rotate`+`translate`, optionally after LibreOffice's `skewX (-5E-017)` (a skew of nothing). Anything
  else (a real skew, a scale, a translation alone, a turned object that also has `svg:x`) is still left out as
  `rotated-object` and stays in the file.
* *Rounding.* The model turns by whole degrees: a file turned by 20.4° comes in as 20°, and an edit-and-reexport of
  an object whose turn did not change leaves its transform as it was (a patch writes only what changed).
* *Patching.* A turned object has its whole place in its transform, so when its place, size or turn changes the
  patch writes `draw:transform` and the size and takes `svg:x`/`svg:y` off (and the reverse when it is turned back
  to upright). `XmlPart.set_attributes` can take attributes off for that (claudia-odf-io 0.3.0).
* *Losses.* None for a turn. Pictures are turned too (D460).

**Checked against the code, 2026-11-17 (`main` at `6814bac`).** The arithmetic lives in `claudia_odf_io/transform.py` (`transform_of`, `turned_box`), shared by odp and odt; there is no `odp_transform.py`.

---
id: D213
title: "A creates image object is exported to pptx as a real picture, its asset's own bytes embedded unchanged; a picture in an imported pptx still stays beyond-claudia"
status: current
applies-to: creates
date: 2026-11-10
round: "Word, Excel and PowerPoint out of every app, and pictures in a PowerPoint (thirty-seventh round)"
supersedes: []
superseded-by: []
---

# D213 · A creates image object is exported to pptx as a real picture, its asset's own bytes embedded unchanged; a picture in an imported pptx still stays beyond-claudia

**A creates image object is exported to pptx as a real picture, its asset's own bytes embedded unchanged; a picture in an imported pptx still stays beyond-claudia.** `slides_to_pptx` calls `add_picture` with `ImageAsset.data` at the object's box, so python-pptx reads the format from the bytes as it would from a file on disk; an object whose asset is missing is left out rather than drawn as a box. Before this an image object fell through to the shape branch and came out as an empty rectangle. Import is deliberately not symmetrical yet: decoding an arbitrary embedded picture back into an `ImageAsset` is separate work, so `pptx_to_slides` keeps treating a picture like a table (D219).

**Notes.** Written as "D206" on the local branch and renumbered for the same reason as D212. The branch's own colour handling in `_rgb` (reading `rgba()` and dropping the opacity) was **not** carried over: D211 already resolves roles and flattens a translucent colour over the page, which is the better of the two answers to the same bug.

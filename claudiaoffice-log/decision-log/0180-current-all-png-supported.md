---
id: D180
title: "PNG is a supported image format, APNG included"
status: current
applies-to: all
date: 2026-11-08
round: "PNG, and an object's words as a paragraph (thirty-second round)"
supersedes: []
superseded-by: []
---

# D180 · PNG is a supported image format, APNG included

**PNG is a supported image format, APNG included.** `SUPPORTED_IMAGE_FORMATS` becomes `("jpeg", "png", "gif", "bmp", "svg")`. The size comes from the IHDR chunk, which a PNG must open with; `animated` is whether the file carries the APNG control chunk `acTL`. An animated PNG gets a still `first_frame` the same way an animated GIF does, and it costs almost nothing to make: dropping the three animation chunks (`acTL`, `fcTL`, `fdAT`) and copying every other chunk byte for byte, CRC included, leaves exactly the default image a viewer without APNG support would already have shown — nothing is re-encoded and no CRC is recomputed. The chunk walk is strict in the same way the GIF sub-block walk is: a file whose chunks end without `IEND`, or whose declared length runs past the end, is refused rather than read as a shorter file. The client's `IMAGE_FILE_ACCEPT`, its format→MIME map and the properties dialog's label all learn `png`.

**Notes.** The owner's own omission, found when a PNG was refused during the end-to-end check of the creates insert bug. Worth recording because the omission was invisible: nothing in the code said "no PNG", it simply was not in a five-element tuple, and PNG is the format a person is most likely to reach for. Verified against real Pillow-written PNGs in all four colour types (truecolour, alpha, palette, greyscale), not only hand-built ones — a hand-typed sample used earlier in the session turned out to be corrupt, and the strict walk caught it, which is the behaviour working rather than failing.

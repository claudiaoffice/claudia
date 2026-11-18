---
id: D1067
title: "Where an object hangs in DOCX and ODF: the offset from its anchor character"
status: current
applies-to: composes
date: 2026-11-18
round: "The floating object layer in composes (branch floating-objects)"
supersedes: []
superseded-by: []
---

# D1067 · Where an object hangs in DOCX and ODF: the offset from its anchor character

**`dx`/`dy` (the top-left corner of the object from the anchor character, right and down positive, in pixels) is written as an offset *from the character* across and *from the line* down, and read back from the same two relations; a position in any other relation is read as 0.** DOCX: `wp:positionH relativeFrom="character"` and `wp:positionV relativeFrom="line"`, each with `wp:posOffset` in EMU (9525 per pixel). ODF: `svg:x`/`svg:y` on the frame, with `style:horizontal-pos="from-left"`, `horizontal-rel="char"`, `vertical-pos="from-top"`, `vertical-rel="line"` in the graphic style.

**The one surprise.** With `vertical-rel="line"` LibreOffice counts `svg:y` against the line *upwards*: a frame with `svg:y="1cm"` is drawn a centimetre above the line's top (checked by rendering, and by LibreOffice's own export of a frame it was given; the PDF positions are in `test_composes_offset_io.py`'s notes). So the file gets `-dy` and the reader negates it. Word and LibreOffice agree on the DOCX side (`posOffset` is down-positive).

**Rotated frames** carry the offset in the `translate` of `draw:transform` (the same `transform_of`/`turned_box` that creates uses), not in `svg:x`/`svg:y`.

**A kept file** moves an object by changing only those two attributes of its own frame (and the graphic style when the relation is missing), through a derived graphic style (D1066), so the objects sharing a style do not move. An unmoved object's file is byte for byte what it was.

**Not verified.** Word itself was not available; the DOCX side is checked by LibreOffice's rendering and by the schema order, not by Word.

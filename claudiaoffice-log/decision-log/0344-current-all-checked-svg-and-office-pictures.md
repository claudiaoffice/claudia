---
id: D344
title: "Rendered SVG is checked as a drawing, and office files get a PNG when one can be made"
status: current
applies-to: all
date: 2026-11-13
round: "Rendered text containers (branch containers)"
supersedes: []
superseded-by: []
---

# D344 · Rendered SVG is checked as a drawing, and office files get a PNG when one can be made

**Every result is checked against an element allowlist (a plugin may add elements in its manifest) and sanitised. `<use>` survives only in a *checked drawing*, with local references only (a typeset page is made of them), and the `xlink` prefix is kept (LibreOffice ignores `ns1:href`).** `ObjectModel.picture_of(body)` is what every drawing and export asks: an object's own image, or its definition's.

**Office export.** ODP and PPTX write the picture. With a rasteriser (`rsvg-convert`, 2×, at most 4000 px, 20 s) they write a PNG, because LibreOffice draws Mermaid's SVG as black blocks (it ignores the style sheet). Without one, ODP writes the SVG and PPTX an svgBlip with a blank PNG behind it. Losses: `rendering-pending`, `svg-picture`, `svg-fallback`. Alt text comes from the SVG title, else the type and first words (BITV 1.1.1).

**Notes.** Not yet done: the source text inside the Office file, native formulas, `rsvg-convert` through the sandbox.

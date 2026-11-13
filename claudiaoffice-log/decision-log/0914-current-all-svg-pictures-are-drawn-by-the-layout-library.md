---
id: D914
title: "SVG pictures are drawn by the layout library, as what they are made of, for every app"
status: current
applies-to: all
date: 2026-11-12
round: "Pages, print preview and PDF (branch layouting)"
supersedes: []
superseded-by: []
---

# D914 · SVG pictures are drawn by the layout library, as what they are made of, for every app

**An SVG picture is drawn by the layout library (`svg/`), not by the browser: it is read by an XML reader of the library's own (no DOM), and turned into the display list's paths, glyph runs and images, so the preview and the PDF show exactly the same thing and computes and creates can draw their charts, formulas and pictures the same way.** Drawn: the basic shapes and paths (every command, arcs included), groups, `use` and `symbol`, nested `svg` with `viewBox` and `preserveAspectRatio`, transforms, fill and stroke (colours, `currentColor`, linear and radial gradients with their opacities, dashes, line ends and corners, miter limits, fill rules), opacity of a whole group, clip paths, style sheets with simple selectors, text in the server's fonts (with `tspan`, `text-anchor`), and pictures inside the SVG given as data URLs (PNG, JPEG, GIF, BMP, and SVG). Left out, and said so in the preview: filters, masks, pattern fills, markers, `foreignObject`, text on a path, pictures linked from outside the file, and style rules with other selectors. The display list gains what this needs, and the PDF writer and the preview painter draw it: gradients (PDF shading patterns, with a soft mask when the opacity varies), a transform per group, clip paths, transparent layers (PDF transparency groups), and stroke details.

**Notes.** The tests compare four SVGs — shapes, paints, groups, and a formula made by `pdftocairo` (glyphs as paths used by reference, as the typesetting service makes them) — drawn by librsvg with our PDF drawn by poppler: the mean difference per colour value is below 1.2 of 255 everywhere. Every number is computed with plus, minus, times, divide and square root (arcs and rotations by the library's own sine), then rounded to whole mpt (D910). A picture inside an SVG gets the id `svg-<sha256>` (the library's own SHA-256), and its bytes travel with the layout (`TextPages.embedded`).

---
id: D391
title: "The picture comes back through the ordinary image path, and SVG is the narrow waist"
status: current
applies-to: all
date: 2026-11-13
round: "Rendered text containers (branch containers)"
supersedes: []
superseded-by: []
---

# D391 · The picture comes back through the ordinary image path, and SVG is the narrow waist

**The result of a render is a normal `ImageAsset` (SVG) the document keeps, and every plugin returns SVG and nothing else.** A document therefore opens, prints and exports on a machine without the renderer, and a plugin cannot invent a new way for pictures to enter a file.

**Notes.** SVG is the narrow waist: one checked format in, every export out. Source text is kept next to it, so a native translation (LaTeX to OMML or MathML, Mermaid to shapes) can be added later where a standard exists, without touching the plugins. Rejected: PDF or PNG results (they lose scaling and text), and HTML results (they run code).

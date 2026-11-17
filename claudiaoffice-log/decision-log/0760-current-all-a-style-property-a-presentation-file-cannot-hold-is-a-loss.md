---
id: D760
title: "A style property a presentation file cannot hold is a loss, named by the property"
status: current
applies-to: all
date: 2026-11-17
round: "Stabilisation of main, second round (CODE-58, CODE-60, PROC-27)"
supersedes: []
superseded-by: []
---

# D760 · A style property a presentation file cannot hold is a loss, named by the property

The pptx and odp converters write a style's font, size, colour, weight, slant and alignment, and a shape's fill and
outline. A style may say more: line height, letter spacing, a border, padding, margins. Until CODE-58 the `styles` facet
counted as written, so an export said nothing about them. Now `style-property` is a loss, with the property as its
detail and the number of objects it touches as its count, in `pptx_export_losses`, `odp_export_losses` and both
`*_unwritten_changes` (`claudia_creates_io._styling.unwritten_properties`).

**A property is judged against the built-in style it comes from**, not against nothing: `line-height: 1.3` of Body text
is the file's default in every deck and is no loss, and an edit of a kept file reports only what changed since it was
read. A style the deck made is compared with the nearest of its parents that a fresh deck has.

**Not decided here:** to *write* the properties. Mapping them is the better end (pptx `a:lnSpc`, `spc`, insets; odp `fo:`
equivalents) and the loss entries are the list of what is left; each property that gets written leaves the list.

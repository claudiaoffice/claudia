---
id: D316
title: "A slot takes every style whose kind can hold all the facets the slot reads"
status: current
applies-to: all
date: 2026-11-10
round: "Styles as facets, slots and bundles (styles round)"
supersedes: []
superseded-by: []
---

# D316 · A slot takes every style whose kind can hold all the facets the slot reads

**A style fits a slot when its kind can hold every facet the slot reads.** A box slot (a text box's box, a cell's box, a diagram's box) reads only the Box facet, so it takes a `box` style *and* a `paragraph` style, which may hold a box and of which it reads only that part. A words slot (Text + Paragraph) and a composes paragraph (Text + Paragraph + Box) take only `paragraph` styles; an outline slot only `outline` styles. A slot that reads nothing (a picture's box) takes only styles of its own kind. Each slot still has a kind of its own: the kind of a style made for that slot alone (`plain-box` for a text box's box).

**Notes.** This is what D309 and D311 need: one named bundle (a `paragraph` style such as a cell's "Header", with a background and a bold font) fills both slots of a cell or a text box, and each slot reads its part. With the narrower reading of D305 — a slot takes only a style of exactly its own kind — a bundle could never fill a box slot, and D311 could not be built. Worked out while building step 1.2 of the styling-suite plan (`claudia_core.facets.fits`); it follows from D309 and D311, which the owner confirmed on 2026-11-10, and is recorded here so that the rule has one place. The owner may still narrow it.

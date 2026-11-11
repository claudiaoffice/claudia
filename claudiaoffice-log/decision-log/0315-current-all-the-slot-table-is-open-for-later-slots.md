---
id: D315
title: "The slot table is open: later slots (slide, page, diagram parts, chart tab) are added as rows"
status: current
applies-to: all
date: 2026-11-10
round: "Styles as facets, slots and bundles (styles round)"
supersedes: []
superseded-by: []
---

# D315 · The slot table is open: later slots (slide, page, diagram parts, chart tab) are added as rows

**The slot table in `claudia_core` is open: a kind of thing that can be styled is added by adding its row (its slots, the facets each reads, the kind offered), without changing the style model, the server's style API or the style UI.** Known future rows, not built in this round: a creates **slide** (its background), a composes **page**, the **parts of a diagram** (titles, axes, series colours) and a computes **chart tab**. A future row may need a new facet (a page's size and margins, say); facets are added the same way, with an allow-list version bump.

**Notes.** Found while checking the owner's list of styleable things (image, shape, paragraph, text, text box, cell, diagram) against the code: that list is complete for what has a style today, and these four have none yet. The owner: "no, later, but good catch — our architecture needs to support these too later." So the plan's step 1 includes a test that a new thing kind and slot can be registered and styled through the API without touching the core style code. Confirmed by the owner on 2026-11-10.

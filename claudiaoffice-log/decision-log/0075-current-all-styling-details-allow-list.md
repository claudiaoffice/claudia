---
id: D75
title: "Details of styling, accepted as proposed"
status: current
applies-to: all
date: 2026-11-03
round: "Styling and Edit menu (twelfth round)"
supersedes: []
superseded-by: []
---

# D75 · Details of styling, accepted as proposed

**Details of styling, accepted as proposed.** (1) a defined, versioned allow-list of properties and value types; no `url()`, no `@import`, no `@font-face`, no external references, no scripts. (2) Number and date formats, page layout and slide layouts are **not** CSS and have their own definitions. (3) A deviation creates the new style at once under a provisional name derived from its parent and puts it in the "to name" list, so naming never blocks typing. (4) A new style stores only its differences from its parent; changing the parent changes the child where it has not overridden. (5) Named styles map to named ODF styles; every export lists what could not be mapped. (6) One shared dialog: style picker first, then "Change this style…" and "Deviate…".

**Notes.** Built as `claudia_core.css` (`CSS_VERSION` 1) and `claudia_core.styles`. The allow-list v1 is wider than the first proposal: padding and per-side borders are in, plus `fill`, `stroke`, `stroke-width` for shapes. Open: deleting a style that other styles are based on.

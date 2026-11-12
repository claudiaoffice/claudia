---
id: D312
title: "The style kinds are `paragraph`, `box` and `outline`"
status: current
applies-to: all
date: 2026-11-10
round: "Styles as facets, slots and bundles (styles round)"
supersedes: []
superseded-by: []
---

# D312 · The style kinds are `paragraph`, `box` and `outline`

**The kinds of D305 are `paragraph`, `box` and `outline`.** A `paragraph` style may hold Text, Paragraph and Box properties and is offered for a composes paragraph and for the words of a text box, a shape's label and a cell; `box` holds Box properties (a text box's box, a cell's box, a diagram, a picture); `outline` holds Outline properties (a shape).

**Notes.** The facets note had proposed `words` for the first; "paragraph" is the word the code already uses (`Paragraph`, `paragraph_for`, `set_paragraph_style`) and D305's own, and a person never sees the kind's name. The facets note is corrected. Confirmed by the owner on 2026-11-10.

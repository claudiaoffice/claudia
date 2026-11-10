---
id: D309
title: "A named style is one purpose bundle; each slot reads only its facets; "change the box only" deviates one slot"
status: current
applies-to: all
date: 2026-11-10
round: "Styles as facets, slots and bundles (styles round)"
supersedes: []
superseded-by: []
---

# D309 · A named style is one purpose bundle; each slot reads only its facets; "change the box only" deviates one slot

**A named style is one bundle for one purpose** ("Definition", "Quote", "Callout"): it can hold properties of several facets, and the slot that applies it reads only the facets it understands (D304). Pointing a container at two separately named styles (one for its box, one for its paragraph) is **not** the model: a text box has one style id for its box and a paragraph with its own style id, as D181 already says.

**Deviating changes one slot.** "Change the box only" on a selected thing makes a new style from the thing's style for that slot (provisionally named, `to_name`, D75) and points only that slot at it; the dialog says which slot is being changed. The editor shows one section per facet, so a bundle's box and text parts are edited side by side.

**Notes.** Considered and not chosen: separate references to a Text style, a Paragraph style and a Box style (more flexible, but every thing then carries three style ids and a user has to name three things for one purpose, which is the opposite of "mark by what it is for", D62). Taken as the recommended option when the owner said "this is all good" on 2026-11-10.

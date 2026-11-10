---
id: D304
title: "A container has a box (or outline) style, its content has a paragraph style, and each slot reads only the facets it understands"
status: current
applies-to: all
date: 2026-11-10
round: "Styles as facets, slots and bundles (styles round)"
supersedes: []
superseded-by: []
---

# D304 · A container has a box (or outline) style, its content has a paragraph style, and each slot reads only the facets it understands

**Wherever styled content appears there are two *slots*: the container's (a Box or an Outline style) and the content paragraph's (a Paragraph style, whose text properties are its defaults for the characters in it).** Each slot reads only the facets it understands and ignores the rest:

  | Where | Container slot | Content slot |
  |---|---|---|
  | composes paragraph | Box (a Definition has a background and a left border) | Paragraph + Text |
  | creates / computes text box | Box | Paragraph + Text |
  | shape | Outline | label Paragraph + Text |
  | computes cell | Box | Paragraph + Text (D307) |
  | picture, chart | Box (a chart); none for a picture | none |

**Notes.** This is D181 ("the words of an object are a paragraph; the object's own style is its box") generalised: the same two slots now exist for a composes paragraph and for a cell. A cell uses the very same Box style as a creates text box, and the same text properties as composes. Replaces `StyleHost.parts: {words, box}` with the list of facets the slot reads; controls for facets a slot lacks are still left out, not disabled (D209).

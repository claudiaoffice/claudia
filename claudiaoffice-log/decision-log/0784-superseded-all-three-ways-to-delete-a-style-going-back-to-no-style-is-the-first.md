---
id: D784
title: "Three ways to delete a style, going back to no style first and by default"
status: superseded
applies-to: all
date: 2026-11-18
round: "Deleting and hiding styles (E1.10)"
supersedes: []
superseded-by: [D785]
---

# D784 (superseded by D785) · Three ways to delete a style, going back to no style first and by default

**Superseded 2026-11-18 by D785**: the owner saw the three ways and found *keep their look* a mishappened rename (same look, same parent, a new name); *go back to no style* became a case of *assign another style*. **Decided 2026-11-18** by the owner, who checked standard office software: when a style is deleted, whatever had it falls back to the body paragraph. Before: D226 knew two ways and held every look.

**Three ways, offered in this order, the first one preselected:**

1. **Go back to no style** (`fall_back`). In Claudia everything always has a style, so "no style" is the plain one of its kind: *Body text* for a paragraph, *Plain box* for a box, *Plain image* for a picture. What had the deleted style gets that one and looks like it. A style that was based on the deleted one is based on the deleted style's own parent instead, and loses what the deleted one said. **This is the one way that changes looks**, so the dialog counts them first: "14 paragraphs and 1 style will look different".
2. **Re-base on another style** (`rebase`). What had the style keeps looking exactly as it does, but is built on a style the person chooses: it follows that style from now on, except where the deleted one differed. Example in the dialog: "Quote is italic and indented. Re-based on Note it stays italic and indented, and takes on any later change to Note's font and size." A stand-in is made for what had the style itself (D781).
3. **Keep their look** (`keep`). The same, with the deleted style's own parent as the new base. The stand-in is "<name> (kept)".

**What "no style" is.** `StyleBook.fallback(style)`: the built-in root of the style's own chain if it has one of its own kind, otherwise the first built-in root of that kind (a box has two roots, so a box style of no built-in lineage goes to *Plain box*).

**Amends D226.** D226 said a deletion never changes how anything looks. That still holds for ways 2 and 3. Way 1 changes looks on purpose, says how many in words before anything happens, is one step in the history and is undone as one (D782). It never leaves a dangling reference.

Everything else of D780–D782 stands: only document styles are deleted, the others are hidden; a style somebody began to use in the meantime refuses the whole step.

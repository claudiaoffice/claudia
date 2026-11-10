---
id: D209
title: "One style menu for all three apps, and what it offers follows from what the thing actually has"
status: current
applies-to: all
date: 2026-11-09
round: "The styling dialogs: one menu, three apps (thirty-sixth round)"
supersedes: [D125]
superseded-by: []
---

# D209 · One style menu for all three apps, and what it offers follows from what the thing actually has

**One style menu for all three apps, and what it offers follows from what the thing actually has.** `StyleHost` gained `parts: {words, box}`: a paragraph has words, a shape has words and a box (`fill`, `stroke`, `stroke-width`, D178), a picture has neither, and a chart has a box but no words. The controls for a group a thing does not have are **left out, not disabled**. `objectStyleHost` makes the selected floating object a host, so creates and computes reach the very same `StyleMenu`, `StyleSpec` and `StylesDialog` composes has used all along; the Format menu in each app now lists that app's styles instead of the inert "No styles yet" stub (D125 is retired). New `deviate_object_style` on the server is the mirror of composes' `deviate_style`: "change this shape only" makes a style from the one the object has and points the object at it, provisionally named and `to_name` until somebody names it (D75).

**Notes.** The alternative was a second, object-shaped style menu beside composes' paragraph one. `style-host.ts` had said since it was written that "a text is one host; cells and shapes will be others", and taking it at its word cost one interface field and one adapter per app. What is left out rather than greyed out follows the rule already written for an image's context menu: an empty control that can never do anything is worse than no control. The per-object items *are* disabled rather than hidden when nothing is selected, which is different — there the control will work, as soon as there is something for it to be about.

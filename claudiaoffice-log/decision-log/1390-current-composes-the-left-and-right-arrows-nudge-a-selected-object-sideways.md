---
id: D1390
title: "The left and right arrows nudge a selected object in composes, by the same step as in creates"
status: current
applies-to: composes
date: 2026-11-21
round: "Bug fixes after SEC-12: the red CI (branch main)"
supersedes: []
superseded-by: []
---

# D1390 · The left and right arrows nudge a selected object in composes

**Decided 2026-11-21** while making the end-to-end script `objects.cjs` pass (UX-62). The contract
(`notes/object-interaction-contract.md`, "Arrow keys") already said that the arrow keys nudge the selected object and
that in composes the up and down arrows hang it from the previous or next paragraph and the left and right arrows
"change the offset". Only up and down were built.

**Left and right move a selected object in composes off the character it hangs from by 10 units; with Shift by 1.** It
stays hung from the same paragraph and character: what changes is the offset the model keeps (`dx`), the one a drag also
changes. This is the step creates takes for every arrow key (10, with Shift 1); both apps read it from one place now
(`NUDGE` and `NUDGE_FINE` in `lib/geometry.ts`). Up and down are as before (D1228): they hang it from the previous or
next paragraph.

**Assumption.** The step is the one creates already has; nobody has tried 10 units on a composes page. If it is too much
or too little next to a line of text, the value in `lib/geometry.ts` is the only place to change.

**Not changed.** The keys of a dialog that sits inside the grid or the slide (Rotate by…) are the dialog's, not the
object's (UX-56): the grid and the slide ignore a key that comes from inside a `role=dialog`.

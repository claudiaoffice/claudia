---
id: D782
title: "A deletion is one undoable step; if somebody uses the style meanwhile it is refused, and nothing changes"
status: current
applies-to: all
date: 2026-11-17
round: "Deleting and hiding styles (E1.10)"
supersedes: []
superseded-by: []
---

# D782 · A deletion is one undoable step; if somebody uses the style meanwhile it is refused, and nothing changes

**One step.** The commands of a deletion (the stand-in, the styles that move, what moves to the stand-in, then the removal) are one batch: one entry in the history, one undo, and all or nothing. Undoing puts the style back *where it was* in the style list, with everything pointing at it again.

**Two authors.** The batch is planned against what the document was; the removal at its end is refused while anything has the style. So if somebody else begins to use the style between the plan and the removal, the deletion is refused with a sentence ("in use") and the whole batch is rolled back: nobody's work is moved without their knowing. A change of the deleted style by somebody else (`ChangeStyle`, `RenameStyle`, a heading level, a numbering, a re-base) drops a stale deletion as the existing commands do.

**Who.** Any role that may write, as for every style command (`delete_style` and `hide_style` are write methods). The assistant may not: they are not on its list of methods (SEC-10), in act or in suggest mode; a person decides what goes.

**Notes.** A viewer may ask what a deletion would do (`style_deletion`), so a dialog can say it before anything happens.

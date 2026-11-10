---
id: D46
title: "Undo is per author and never overwrites a colleague"
status: current
applies-to: all
date: 2026-11-02
round: "Kernel and server (sixth round)"
supersedes: []
superseded-by: []
---

# D46 · Undo is per author and never overwrites a colleague

**Undo is per author and never overwrites a colleague.** If a colleague wrote the same region after my step, my undo is refused (`UndoConflict`) and nothing is consumed.

**Notes.** Implemented by `Command.shifted_by`: the stored inverse is moved through everything that ran since; `None` means "changed by somebody else".

---
id: D291
title: "Random numbers are a function of the workbook's seed, its draw number and the cell — never of a clock"
status: current
applies-to: computes
date: 2026-11-13
round: "Random numbers, alternatives and following a computation (branch random-in-computes)"
supersedes: []
superseded-by: []
---

# D291 · Random numbers are a function of the workbook's seed, its draw number and the cell — never of a clock

**A random number in a cell is computed, not drawn: it is a pure function of the workbook's `seed`, its `draw` number, the cell (sheet, row, column), the number of the call inside the cell and the position inside the call (`claudia_computes.draws`, BLAKE2b).** Every user, every client, a recalculation after a restart and a replay of the history therefore see the same numbers, which is what multi-user mode needs; no generator has a state that could differ.

`Resample` (Tools ▸ Resample, F9) raises the draw number by `steps` and is **relative** (the inverse is the same command with the opposite sign), so two people resampling at once count both and one author can undo theirs after colleagues did other things. `SetRandomSeed` fixes the seed so a model can be reproduced. Both are logged, undoable commands; seed and draw number are part of the workbook state (schema 8), and `RandomChanged` tells clients.

**Notes.** Rejected: a per-session generator (users would see different numbers), a seed taken from the log position (every edit would redraw). A cell that is edited keeps its numbers: the draw number, not the edit, makes new ones.

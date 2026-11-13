---
id: D81
title: "A new presentation starts with one slide, `s1`; ids of slides and objects are chosen by the server, random and never reused"
status: current
applies-to: creates
date: 2026-11-03
round: "Claudia creates, first draft (fourteenth round)"
supersedes: []
superseded-by: []
---

# D81 · A new presentation starts with one slide, `s1`; ids of slides and objects are chosen by the server, random and never reused

**A new presentation starts with one slide, `s1`; ids of slides and objects are chosen by the server, random and never reused.**

**Notes.** Two clients opening an empty document at once must not both create the first slide. Never reusing ids means an undo of a removal cannot collide with something added later.

---
id: D48
title: "Restoring a checkpoint forks"
status: current
applies-to: all
date: 2026-11-02
round: "Kernel and server (sixth round)"
supersedes: []
superseded-by: []
---

# D48 · Restoring a checkpoint forks

**Restoring a checkpoint forks.** The document continues on a new line `restore-N`; the old future stays under its unchanged revision ids on a hidden side line until an owner discards it. **`switch_to` is the way back.** Nothing is ever truncated.

**Notes.** Locks and presence are cleared; views get `BranchSwitched` and `Rebuilt`. Rules for a live session: D51, D52.

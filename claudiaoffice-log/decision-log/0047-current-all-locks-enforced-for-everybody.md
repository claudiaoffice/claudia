---
id: D47
title: "`execute` enforces locks for everybody, the `ai` user included"
status: current
applies-to: all
date: 2026-11-02
round: "Kernel and server (sixth round)"
supersedes: []
superseded-by: []
---

# D47 · `execute` enforces locks for everybody, the `ai` user included

**`execute` enforces locks for everybody, the `ai` user included.** A command that touches a region a colleague holds is refused (`RegionHeld`, code `locked`) and changes nothing.

**Notes.** Undo checks the same rule. `check_free` stays public so a UI can ask in advance.

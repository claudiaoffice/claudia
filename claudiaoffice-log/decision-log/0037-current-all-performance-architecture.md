---
id: D37
title: "Performance architecture"
status: current
applies-to: all
date: 2026-11-01
round: "Security, calculation and extensibility (second round)"
supersedes: []
superseded-by: []
---

# D37 · Performance architecture

**Performance architecture:** incremental recalculation with a persistent dependency graph; the output range of a function is owned by it; inputs are not locked (a worker computes on a copy at revision r and its result is discarded if the inputs changed); results of worker functions stored in the log as commands with final values; two tiers (core and quick vectorised inline, heavy or slow in warm workers with timeouts); the kernel stays free of I/O; dragging uses an unlogged what-if preview; cells get a "calculating" state.

**Notes.** The incremental graph is built (`calc.py`). **The worker tier is not**: everything runs on the event loop.

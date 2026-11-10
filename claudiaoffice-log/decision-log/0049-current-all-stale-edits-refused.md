---
id: D49
title: "An edit made against a view that is no longer on the active line is refused"
status: current
applies-to: all
date: 2026-11-02
round: "Kernel and server (sixth round)"
supersedes: []
superseded-by: []
---

# D49 · An edit made against a view that is no longer on the active line is refused

**An edit made against a view that is no longer on the active line is refused** with `StaleEdit` (code `stale`) and changes nothing.

**Notes.** `Document.execute(command, base=revision)`; the server's `apply` takes `base`; clients reload and try again.

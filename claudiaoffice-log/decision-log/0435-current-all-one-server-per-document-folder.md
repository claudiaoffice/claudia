---
id: D435
title: "A document folder is used by one server at a time"
status: current
applies-to: all
date: 2026-11-14
round: "One server, app modules (branch one-server)"
supersedes: []
superseded-by: []
---

# D435 · A document folder is used by one server at a time

**A server takes an exclusive lock on its `--dir` or `--plain-dir` (the file `.lock` in it) before it starts, and
refuses to start when another process holds it. The lock is the operating system's (`fcntl.flock`, `msvcrt.locking`
on Windows), so it goes away with the process, however the process ends.**

**Notes.** Nothing stopped two servers from writing the same sealed files before; with three desktop apps sharing
one local server (and old launchers side by side with new ones) it became likely. Two writers on one journal would
corrupt documents that cannot be repaired (they are encrypted).

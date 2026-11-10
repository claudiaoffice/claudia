---
id: D38
title: "UserFunctions are installed by the server admin"
status: current
applies-to: all
date: 2026-11-01
round: "Security, calculation and extensibility (second round)"
supersedes: []
superseded-by: []
---

# D38 · UserFunctions are installed by the server admin

**UserFunctions are installed by the server admin** in version 1, from a folder on the server, and run in workers. A document declares what it requires (name, version, digest), like fonts. On a localhost setup adding a function must be really simple.

**Notes.** Same trust rule everywhere: whoever controls the server's folder controls the functions. No executable code travels inside documents.

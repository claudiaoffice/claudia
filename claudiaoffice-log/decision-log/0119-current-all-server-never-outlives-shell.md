---
id: D119
title: "The server never outlives its shell"
status: current
applies-to: all
date: 2026-11-03
round: "Native clients (eighteenth round)"
supersedes: []
superseded-by: []
---

# D119 · The server never outlives its shell

**The server never outlives its shell.** It has its own process group, which the shell ends with the window, and it asks Linux for `SIGTERM` when the shell dies for any reason.

**Notes.** Linux only; Windows and macOS need their own mechanism (job object, lifeline).

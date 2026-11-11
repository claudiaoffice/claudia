---
id: D262
title: "Proposal: the Windows shell stops the local server by ending its whole process tree"
status: undecided
applies-to: all
date: 2026-11-11
round: "E5.11 Windows client: three apps, command line, server flow (branch `win-client-complete`)"
supersedes: []
superseded-by: []
---

# D262 · Proposal: the Windows shell stops the local server by ending its whole process tree

**Proposal: when its window closes, the Windows shell ends the local server with `taskkill /pid <pid> /T /F` (the process and all its children), and falls back to `process.kill()` if `taskkill` cannot be run.** `uv`'s virtual environment on Windows starts `.venv\Scripts\python.exe` as a launcher stub that spawns the real interpreter as a child; ending only the stub leaves the server process alive and the port taken. Node's `ChildProcess.kill()` does not touch grandchildren on Windows and has no softer signal (D161).

**Notes.** This is an implementation choice made without asking the owner, hence a proposal. It improves the ordinary stop path only: D161 (a shell killed outright leaves the server orphaned; no Job Object yet) stays as it is, and is the likelier place for a Job Object later. The tests mock `taskkill`; the real `taskkill /T` against a real uv interpreter has not run. If the owner prefers a Job Object now, this decision is replaced by that one.

---
id: D430
title: "One server process hosts all three apps as modules"
status: current
applies-to: all
date: 2026-11-14
round: "One server, app modules (branch one-server)"
supersedes: [D84]
superseded-by: []
---

# D430 · One server process hosts all three apps as modules

**A Claudia server is one process that hosts computes, composes and creates together. Each app is a module: its
document model, its method table, its assistant and its own place in the document folder. The modules share one
origin, one port, one certificate, one set of administrators and settings, the fonts, the hyphenation patterns, the
web app and the worker pool. `python -m claudia_server` serves all three by default; `--apps` names fewer.**

**Notes.** Until now one process served one `--model` (D134's premise), so `./start.sh all` started three servers on
8765–8767 and a client could not list the documents of all apps in one place: three origins, and D170 forbids
cross-origin fetches. The file-management work of 2026-11-13 (one list of "my documents", collections, places) needs
that list, which is what decided it. Measured the same day: importing the server already loads all three app
packages, so each of the three processes idled at ~110 MB; one process serves all three in the same ~110 MB. The
installed size does not change (`claudia-server` always depended on every app).

Inside the process each module keeps its own `Hub` (`suite.py`, `Suite` routes to them): the hub, its threading rule
(D16) and its tests stay as they were. D134 stays in force for what it says about the pool (one per process, in
`claudia-server`); only its premise "one process per app" no longer holds, so the one pool now serves all modules.

What this costs and is tracked (E3.12): one failing module stops every app until the modules run in their own
processes (D436); a server update restarts every app's sessions; the AI model is still per server and now shared by
the apps that have a lens (the AI server, D2/E7.1, is a separate piece of work).

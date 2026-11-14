---
id: D433
title: "The old ways of starting a server keep working"
status: current
applies-to: all
date: 2026-11-14
round: "One server, app modules (branch one-server)"
supersedes: []
superseded-by: []
---

# D433 · The old ways of starting a server keep working

**`python -m claudia_server --model module:Class` starts a server with that one module and keeps its documents where
it always did (`--dir DIR` holds `docs/` directly). `CLAUDIA_APP=<app>` in the container image does the same.
`./start.sh <app>` starts the whole server and opens that app's page in the browser; `./start.sh all` starts the
same single server. `--model` and `--apps` cannot be given together.**

**Notes.** Owner, 2026-11-14: old commands keep working. `./start.sh composes` is read as "I want to work on texts",
which the full server serves just as well; a server cut down to one app is what `--model` and `CLAUDIA_APP` are for
(scripts and containers that start the same way every time). The ports 8766 and 8767 are no longer used by
`./start.sh all`.

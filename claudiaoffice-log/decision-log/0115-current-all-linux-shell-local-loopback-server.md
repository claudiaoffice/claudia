---
id: D115
title: "The Linux shell shows a local server on the loopback address, which serves the frontend itself"
status: current
applies-to: all
date: 2026-11-03
round: "Native clients (eighteenth round)"
supersedes: []
superseded-by: []
---

# D115 · The Linux shell shows a local server on the loopback address, which serves the frontend itself

**The Linux shell shows a local server on the loopback address, which serves the frontend itself** (`--host 127.0.0.1 --no-tls --web <frontend>` on a free port), so page and WebSocket share one origin and no `--allow-origin` is needed.

**Notes.** Replaces the custom-scheme plan, which cannot work with the unchanged web app because `OpenDialog.vue` derives the server address from `location.host`. Plain HTTP is acceptable because the socket never leaves the machine. **Side effect:** the port changes every start, so the page's `localStorage` does not survive a restart.

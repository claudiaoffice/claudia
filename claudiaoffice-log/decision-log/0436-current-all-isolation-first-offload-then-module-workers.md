---
id: D436
title: "Isolation in two steps: offload heavy jobs to the pool first, run each module in its own process later"
status: current
applies-to: all
date: 2026-11-14
round: "One server, app modules (branch one-server)"
supersedes: []
superseded-by: []
---

# D436 · Isolation in two steps: offload heavy jobs to the pool first, run each module in its own process later

**First, stateless heavy work (Office import and export, rendering, rasterising, PDF) is submitted to the worker pool
(D134), so it neither blocks the event loop nor takes the server down when it crashes. Later, each module runs as a
long-lived worker process that owns its hub and its documents, behind the main process, which keeps the web app,
fonts, hyphenation, administration and the sockets and passes frames on; a supervisor restarts a module that dies,
and its documents come back from their journals. A switch chooses in-process modules (the desktop) or module workers
(a server).**

**Notes.** Owner, 2026-11-14: "offloading first, but medium term" the module workers. The pool cannot host a module
as it is: it runs functions in short-lived processes, while a document is long-lived state touched from one thread
only (D16). In the module-worker step logins happen inside the worker that owns the document, so document keys never
cross a process boundary. Until then one module's crash or a long computation affects every app (tracked in E3.12).

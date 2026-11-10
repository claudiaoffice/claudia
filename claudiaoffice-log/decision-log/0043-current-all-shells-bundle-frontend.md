---
id: D43
title: "bundle the frontend"
status: current
applies-to: all
date: 2026-11-02
round: "Web views and the panel (fourth round)"
supersedes: []
superseded-by: []
---

# D43 · bundle the frontend

The desktop clients **bundle the frontend** and load it from the local package, never from a remote server.

**Notes.** A shell's native API must only be reachable from bundled content. Servers must accept older frontend protocol versions; how old is open. Qualified by D115: the Linux shell lets its own local server serve the bundled frontend, so page and socket share an origin.

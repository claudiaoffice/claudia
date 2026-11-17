---
id: D2
title: "Each app is separately installable: its own doc server, a GTK desktop client and a web client"
status: current
applies-to: all
date: 2026-11-01
round: "Product and UX"
supersedes: []
superseded-by: []
---

# D2 · Each app is separately installable: its own doc server, a GTK desktop client and a web client

Each app is separately installable: its own doc server, a GTK desktop client and a web client. A fourth, shared AI server serves all three.

**Notes.** The AI server can be scaled up (for example when cloud-hosted).

**Checked against the code, 2026-11-17 (`main` at `6814bac`).** Partly overtaken (DOC-03): one server hosts the three apps (D430) and the desktop apps share one local server (D445); the Linux package holds all three apps (D247), and Windows and macOS have a Neutralino client, not GTK (D42, D660). The AI is not a fourth server but a package inside the server (`claudia-ai`, E7.1, E3.6). What stands: each app is its own window and launcher, with the web client beside it.

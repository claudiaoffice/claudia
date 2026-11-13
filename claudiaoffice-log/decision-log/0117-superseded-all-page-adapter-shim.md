---
id: D117
title: "The web app is not changed for the shells (yet); a page adapter speaks the contract for it"
status: superseded
applies-to: all
date: 2026-11-03
round: "Native clients (eighteenth round)"
supersedes: []
superseded-by: [D121]
---

# D117 · The web app is not changed for the shells (yet); a page adapter speaks the contract for it

**The web app is not changed for the shells (yet); a page adapter speaks the contract for it.** The shell injects `shim.js` into its own pages, carries out actions by using the web app's menus as a person would, reads which items are enabled or ticked, and hides the web menu bar. When the web app implements the contract itself, the adapter is deleted.

**Notes.** The owner asked that the web app not be changed: "that is a separate cleanup". A drift-guard test fails when a web label a route uses is renamed. **Cost:** a DOM click path is fragile, and states are polled every 750 ms (UX-09).

*Superseded by D121.*

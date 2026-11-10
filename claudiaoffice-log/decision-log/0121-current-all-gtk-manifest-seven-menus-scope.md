---
id: D121
title: "Scope of the E5.1/E5.10 pass"
status: current
applies-to: all
date: 2026-11-05
round: "Menu redesign and accessibility baseline (nineteenth round)"
supersedes: [D117]
superseded-by: []
---

# D121 · Scope of the E5.1/E5.10 pass

**Scope of the E5.1/E5.10 pass:** the Linux GTK manifest (`manifest.py`) is rebuilt to the full seven-menu schema rather than staying collapsed to D4's four, and is extended to computes and creates, which have no GTK manifest at all today. `shim.js` is retired in the same pass — the web app will speak the shell contract directly, reaching D117's own stated exit condition rather than deferring it further. UX-03 (`Modal.vue` → native `<dialog>` + `showModal()`) ships alongside UX-01/04/05 instead of being sequenced after.

**Notes.** Supersedes the "not changed for the shells (yet)" half of D117; D117's versioned-contract mechanism itself stands.

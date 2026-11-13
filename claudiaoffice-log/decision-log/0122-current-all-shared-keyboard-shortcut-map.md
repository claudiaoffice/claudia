---
id: D122
title: "Keyboard shortcuts move to one shared, structured map"
status: current
applies-to: all
date: 2026-11-05
round: "Menu redesign and accessibility baseline (nineteenth round)"
supersedes: []
superseded-by: []
---

# D122 · Keyboard shortcuts move to one shared, structured map

**Keyboard shortcuts move to one shared, structured map**, replacing the three near-identical hardcoded `keydown` handlers in `TextWorkspace.vue`, `DocumentFrame.vue` and `Workspace.vue`, with GNOMEish defaults — e.g. Redo is Ctrl+Shift+Z only, dropping today's extra Ctrl+Y binding. Config ▸ Shortcuts shows this read-only for now; an editable remapping UI is deferred.

**Notes.** Groundwork for shipping "typical" per-OS shortcut sets later, per the owner.

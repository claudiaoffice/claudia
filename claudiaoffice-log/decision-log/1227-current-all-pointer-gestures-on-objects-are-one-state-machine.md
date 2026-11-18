---
id: D1227
title: "A press, a drag and a turn on an object are one state machine, the same in all three apps"
status: current
applies-to: all
date: 2026-11-18
round: "Object interaction in the three apps (branch object-interaction)"
supersedes: []
superseded-by: []
---

# D1227 · A press, a drag and a turn on an object are one state machine, the same in all three apps

**What the pointer does to an object is written once** (`web/app/lib/object-gestures.ts`, wrapped by `web/app/lib/object-interaction.ts`): a press on the object, a handle or the turn handle begins a gesture; nothing changes until the pointer has travelled 3 screen pixels (a turn needs no distance); the preview follows the pointer; the release sends **one** change (move, resize or rotate) or none, and the preview stays until the server has answered, so a refusal snaps the object back. Each app only says where its area is, what its objects' frames, angles, aspect and grid are, and how to send a change.

**Esc drops what is being tried** (a drag, a resize, a turn, a Rotate by… preview) and the object is as it was; only when nothing was being tried does Esc leave the selection. This is new in creates, where Esc during a drag used to deselect while the drag went on.

**A picture's properties are reached from its *Style…*** (menus workbook, "To decide" #13): the style popover shows a "Picture properties…" link for a picture; the context menu no longer has a "Properties" entry of its own.

**Notes.** Follows D1221 (one contract) and D1225 (one menu). The geometry functions take an explicit `Bounds` (the slide by default), so composes and computes pass their own area. Still open with the owner: the menu says "Describe…" and "Edit Text" (the repo's wording and Title Case) where the workbook says "Name & describe…" and "Edit text"; "Name & describe…" follows once the dialog has a name field (workbook #12).

---
id: D1230
title: "In computes an object is pressed, dragged, sized, turned and menued as in the other apps, and lands on the nearest cell"
status: current
applies-to: computes
date: 2026-11-19
round: "Object interaction in the three apps (branch object-interaction)"
supersedes: []
superseded-by: []
---

# D1230 · In computes an object is pressed, dragged, sized, turned and menued as in the other apps, and lands on the nearest cell

**The sheet uses the shared gesture module** (D1221) through a host of its own (`web/app/lib/sheet-object-host.ts`, used by
`web/app/components/SheetGrid.vue`). What the person does is what she does in creates and composes (the contract note's table):

- **Press selects** the object, shows the frame with its handles and the turn handle (`ObjectFrame.vue`), and never reaches
  the cell below: pointer events with capture, and `mousedown` stopped on the object so that the cell selection does not
  fire from the compatibility event. Touch and pen now behave as the mouse.
- **Drag moves a preview**; on release the anchor becomes the cell under the object's top left corner (`nearestLine`, the
  nearer of the two lines at a cell border) and the object **keeps its own width and height** (E6.17). One history entry;
  Esc drops a drag in progress (D1227).
- **Handles scale** with the picture's proportions kept (corners; a rendered container keeps no fixed aspect, as in the
  other apps); **the turn handle turns**, Shift snaps to 15°, and *Rotate by…* asks for degrees (`RotatePopover.vue`).
  `rotate_object` is now in `session.ts` for the sheet as it already was for the others.
- **A right press selects the object and opens the object's own menu** (D1225: *Name & describe…, Edit text (where the kind
  has it), Style…, Rotate by…, Wrap text… (not in computes: no text flows round an object in a cell grid), Cut, Copy, Release
  from grid (not in computes), Delete*, as `contextMenuItems` builds them). **The root cause of the pass-through was the
  order of handlers:** the viewport's `@contextmenu.capture` (cell and header menus) ran before any handler on the object;
  `onHeaderContext` now returns at once for anything inside `[data-object]`, and so does the menu key.
- **Keyboard:** Ctrl+Alt+PageDown / PageUp step through the objects (as before); on the selected object arrows move it by
  one cell (Shift: five), Enter or F2 edits a container, Delete removes it, Esc drops what is in progress. Tab stays with
  the cells (Edit ▸ Select Next Object, decided in D1063 and D1222, is not built yet: UX-46).
- **The object clipboard (D1229) pastes a picture into the selected cell** (`SheetGrid.paste`, tried first by
  `Workspace.pasteFromClipboard`), so Edit ▸ Paste and Ctrl+V do the same here as in the other two apps.
- **A change is announced to screen readers** (*Turned to {degrees}*, the existing msgids), and a selected object has its
  name as accessible name (BITV).

**Not changed:** an object still keeps its pixel size when rows or columns are inserted or resized (E6.17); the anchor is a
cell, so the preview's free position is lost on release by design. Read-only documents show the frame without handles and
refuse the commands with the usual notice.

**Notes.** Applies D1221, D1225, D1227, D1229. No new msgid.

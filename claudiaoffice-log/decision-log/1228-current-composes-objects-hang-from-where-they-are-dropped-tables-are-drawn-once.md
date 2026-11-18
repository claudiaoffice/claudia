---
id: D1228
title: "In composes an object hangs from where it is dropped, and a table is drawn once, in the flow"
status: current
applies-to: composes
date: 2026-11-18
round: "Object interaction in the three apps (branch object-interaction)"
supersedes: []
superseded-by: []
---

# D1228 · In composes an object hangs from where it is dropped, and a table is drawn once, in the flow

**A dropped object hangs from the paragraph nearest its top left corner, at the character the browser says that point is over (the start of the paragraph where it is not over words), and floats at the offset that is left over** (D1023, D1221). Dragging within a paragraph therefore re-hangs the object from the character under the drop; what the person sees stays where it was dropped. A handle on the top or left edge changes the size and, as a second step, the offset: the model has no single step for both, so it is two entries in the history.

**The object layer does not draw a table.** A table is an object of kind `table` (D1201) whose only body is `TableView.vue`, in the flow after its paragraph; the layer used to draw a second, empty box of the same kind at its anchor, which covered the table's *Options…* chip (the button did nothing), looked like a dark violet "selection" with no meaning and blocked every press. The table has a faint frame that is always on (D1224 follow-up, owner 2026-11-18), a name tab that selects it and moves it (drag the tab; a line shows the paragraph it will follow), and a menu on the right button on the tab, the frame or a box (*Describe…, Table Options…, Merge Cells, Split Cell, Sort ▸, Delete Table*). Edit keeps its table entries for now: removing them needs the same change in the desktop clients' menus (`manifest.py` and the generated menus), which is not part of this decision.

**A right press on an object or a table is theirs.** The paragraph menu does not open; `TextEditor.vue` steps aside for anything inside `[data-object]`. Shift + right button is still the browser's own menu.

**The composes object menu leaves out what composes cannot do yet,** rather than showing it dead: *Edit text* is offered for a rendered container only (the server has no step that writes the words of a text box or shape in a text), and *Cut* and *Copy* for a picture are not offered (there is no clipboard for objects in a text). Both come with the feature, not with this decision.

**Notes.** Applies D1221 (one gesture module), D1225 (one menu) and D1226 (the bounding box for the wrap, not built yet: no object is turned on screen in composes before this patch, and the text still goes round the unturned frame until D1226 is built).

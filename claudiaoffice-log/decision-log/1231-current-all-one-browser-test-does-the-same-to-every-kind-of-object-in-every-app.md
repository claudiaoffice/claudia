---
id: D1231
title: "One browser test does the same to every kind of object in every app, and a new kind has to be given its row"
status: current
applies-to: all
date: 2026-11-19
round: "Object interaction in the three apps (branch object-interaction)"
supersedes: []
superseded-by: []
---

# D1231 · One browser test does the same to every kind of object in every app, and a new kind has to be given its row

**`web/e2e/objects.cjs` (`npm run e2e:objects`, in the CI job of the other browser tests) makes one object of every kind an
app can have and does the same to each, expecting the same** (the contract of D1221–D1230): a press selects it, shows one frame
and is not heard by what is below (the active cell, the caret); a right press selects it and opens its own menu, exactly the
entries of D1225 for that kind and app, and no cell, header or paragraph menu beside it; a drag shows a preview, changes the
document once on release and is taken back by Esc; the corner handle scales it (proportions kept for a picture and a shape);
the turn handle and *Rotate by…* turn it, one entry each (not offered for a chart); an arrow nudges it, Esc deselects, Delete
removes it, Undo brings it back. A second person is in the document and sees every one of these. Composes' tables have their
own run: the name tab selects, *Options…* is reachable, the table's menu, the drop line while the tab is dragged between
paragraphs, one entry on release, Esc leaves the table, Delete removes it.

**The kinds are the rows of its `KINDS` table, and `tests/test_object_kinds_agree.py` fails when a kind of
`claudia_core.OBJECT_KINDS` has no row, or a row says nothing about one of the three apps:** a function that makes the
object, or the reason the app cannot have it. A new kind of object therefore cannot arrive without somebody pressing,
dragging, turning and right-clicking it.

**Known limits.** The run needs a browser and three servers; it was written where neither exists, so *its first run is the
test of the test* (selectors that do not match show up as timeouts with a screenshot in `SHOTS`). A container is made only
where the server has its tool (the entry is disabled otherwise, and the run says "skipped"). What a second person sees while
somebody *holds* an object (outline and name tag) is not asserted yet; only that the object, its removal and its return are
the same on both screens.

**Notes.** Applies D1221–D1230.

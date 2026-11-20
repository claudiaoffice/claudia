---
id: D1352
title: "The anchor of an object is shown, and moves with it while it is dragged"
status: current
applies-to: composes
date: 2026-11-20
round: "Bug fixes: stale tests, the caret, dragging objects (branch fix-stale-tests-caret-drag)"
supersedes: []
superseded-by: []
---

# D1352 · The anchor of an object is shown, and moves with it while it is dragged

**Decided 2026-11-20**, as the owner asked when reporting the drag bug ("when I start dragging, the program shows me the
place where the anchor of the object is, and when I start moving the anchor moves with it; when I let go, the object
drops into its new anchor place"). Mock: `notes/mockups/composes-object-anchor-drag.svg`.

- **The anchor mark**: a caret bar as high as the line with a small ring on top, in iris (the colour of selection), at
  the character the object hangs from, joined to the object's top left corner by a dotted line. It is drawn while the
  object is selected and while it is dragged; never printed, never in an export.
- **While dragging** the mark goes to the character nearest the object's top left corner (D1023), into another paragraph
  too (D1351), and a label says where that is ("Paragraph 3 · after “allotment”"). The place it hung from is shown
  faintly. Nothing is sent while the button is held, and the words around do not move yet: they flow round the object
  once it is dropped. Esc puts the object and its mark back.
- **On release** the object hangs from that character: one step in the history.
- **A table** moved by its name tab goes after the paragraph it is dropped on, the line that shows where it goes stays
  as it is (D1229).
- **Screen readers** hear where a selected object hangs with its name ("hangs from Paragraph 1, after ‘year: ’"); the mark
  itself is hidden from them.

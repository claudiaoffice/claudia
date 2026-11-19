---
id: D1243
title: "Tables in the web client: words typed in a box arrive once and in the right box, and Insert ▸ Table… uses the caret as it was when it was chosen"
status: current
applies-to: composes
date: 2026-11-19
round: "Spec-first end-to-end tests (branch main, pilot: tables in composes)"
supersedes: []
superseded-by: []
---

# D1243 · Words typed in a box arrive once and in the right box; the table goes where the caret was

Found by driving the real page with the keyboard as fast as it allows (the first run of the table specs), fixed in the same
work, each with a scenario that fails without the fix. **Built.**

- **B1 (size 1): the words were doubled** ("A" + Enter gave "AA"). Enter commits the box, and leaving it commits again; the
  second commit looked at the table's words before the server's echo had changed them and put the words in a second time.
  Now a commit looks at what the box has when its turn comes (commits run one after the other) and the session shows the
  words in the box at once after the server took them (`TextSession.setBox`).
- **B4 (size 2): words went into the wrong box, or were lost.** The caret waited for the server's answer before moving to the
  next box, so the next word was typed into the old one; and every redraw of the table (any event) put the stored words
  back into the boxes, wiping words typed and not yet committed. Now the caret moves at once, the commit follows, and a box
  is drawn from what was typed (`drafts` in `TableView.vue`) until its words are in.
- **B2 (size 2): the table was put after the wrong paragraph.** The page reports a caret move to the app a moment late
  (`selectionchange` is queued), so a key that came straight after a click used the caret of a moment before. Insert ▸
  Table… now reads the caret from the page when it is chosen (`TextEditor.syncCaret`) and keeps that place for the dialog.
- **B3, the table drawn twice** was fixed by D1228 (merged earlier) and is checked by the specs: "the table is between "Before"
  and "After"" also looks again after a moment, and a screenshot is taken at the end of every scenario.

**Notes.** Scenarios: "A table goes where my caret is, also when my hands are quick", "Typing without pauses puts every word
in its own box, once", "Enter takes what I typed…" (`specs/composes/tables.feature`); unit test
`web/tests/text-session-tables.test.ts`. The desktop clients show the same web page (Neutralino, GTK web view) and take the
fix with the build.

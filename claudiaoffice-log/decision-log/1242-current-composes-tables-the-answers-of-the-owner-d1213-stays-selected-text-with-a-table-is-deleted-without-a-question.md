---
id: D1242
title: "Tables: D1213 stays (the last body row and the only column cannot be deleted); a selection with a table in it is deleted without a question, as one undo"
status: current
applies-to: composes
date: 2026-11-19
round: "Spec-first end-to-end tests (branch main, pilot: tables in composes)"
supersedes: []
superseded-by: []
---

# D1242 · Tables: what the owner answered to the review of the table specs

**Decided by the owner 2026-11-19.**

- *Q10: D1213 stays.* Deleting the last body row or the only column does **not** remove the table: the entries are off, as
  D1213 says. (I had proposed that it removes the table, as a table "is not worth keeping empty". The owner wants to use
  it first and judge.) Two scenarios in `specs/composes/tables.feature` say so.
- *N4: a selection with a table in it.* Select text across a table and delete: the table goes with the text, **without a
  question**, in **one** undo that brings back both (as D1225 for an object and Q13 for a table).
- *N2: where the row and column commands live.* D1224 leaves "Insert/delete" to row and column headers, which composes
  tables do not have yet. The owner: the test comes first and fails, and somebody else adds the header UI. The rule
  "I add and take away rows and columns" is `@pending:N2`; it presses the keys of D1208 (Shift+Alt+arrows to add,
  Ctrl+Alt+- and Ctrl+Alt+_ to delete), which stay when the headers are added. Until then it is expected to fail.
- *Q0: B1, B2 and B4 are fixed in this work* (D1243).

**Notes.** Applies D1213, D1224, D1225. Spec: `specs/composes/tables.feature` and `tables.review.md`.

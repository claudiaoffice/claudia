---
id: D1209
title: "A linked table is an own table with a source; its values are a read-only snapshot pulled on request"
status: current
applies-to: composes
date: 2026-11-18
round: "Tables in composes (branch tables-in-composes)"
supersedes: []
superseded-by: []
---

# D1209 · A linked table is an own table with a source; its values are a read-only snapshot pulled on request

**A linked table is the same object and the same definition as an own table, plus a `source`**: the source document's uid (D533), server hints, the document's last-known name, the id of the named range or table inside it, its last-known name, the revision at the pull, and who accepted it and when. Its cells are a snapshot and are read-only; its look, total row, caption, placement and name are the author's. **Detach link** makes the cells editable in one undoable step and forgets the source.

**A pull is done by the person's client**, which opens both documents (D72) and sends `core.DefineTable` or `core.PullTable` with the cells it read through `TableSource`; no server reads the other document, and no password is stored in a document. A pull counts as an export and is logged in the source. **Updating** shows old against new and changes nothing until an owner or an editor accepts. The states are *up to date*, *source changed*, *source not found* (looked up by uid on the servers on the person's map, otherwise "Find replacement…", never automatic) and *source sealed*.

**Notes.** The owner asked on 2026-11-18 to build linked tables in a second patch. The link pointer is the part E12.2 will share with charts and text; here it is built for tables first, in `claudia_core.tables`, and E12.2 can lift it. D535's `--no-list` also hides lookup, so a link to such a server never heals; that is recorded, not changed.

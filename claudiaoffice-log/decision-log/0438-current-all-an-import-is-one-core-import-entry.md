---
id: D438
title: "An imported document starts with one core.Import entry that carries the state the import made"
status: current
applies-to: all
date: 2026-11-14
round: "Opening files from the computer (branch one-server)"
supersedes: []
superseded-by: []
---

# D438 · An imported document starts with one `core.Import` entry that carries the state the import made

**A document made from a Word, Excel, PowerPoint or OpenDocument file is a new document of its app whose log begins
with one `core.Import` entry: the file's name and format, the model state the reader made (`serialize()` form), the
SHA-256 of the file and whether the file is kept (D439). Applying it makes the model that state in place
(`DocumentModel.load_state`). It is in the history under the name of who imported it, nobody's undo step, and it
cannot be redacted. The server reads the file in its worker pool before it creates anything (D436).**

**Notes.** A snapshot is only a cache (D15): the state has to come from the log. The alternatives were commands
that rebuild a state cell by cell, paragraph by paragraph (one more interpreter per app, kept in step with every
reader), or a document that starts from a snapshot (against D15). One entry with the whole state is what an import
is, replays exactly, and the baseline that the patching writers need (D441) is in it. `load_state`'s default takes
over a restored model's attributes; `WorkbookModel` then points its calculator at itself again. Redaction would
blank the base every later entry changes, so `Import.redacted()` is the entry itself.

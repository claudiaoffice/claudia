---
id: D342
title: "What a new document starts with is set up by the server, and is nobody's undo step"
status: current
applies-to: all
date: 2026-11-13
round: "QA follow-up: UX consistency across clients (UX-33)"
supersedes: []
superseded-by: []
---

# D342 · What a new document starts with is set up by the server, and is nobody's undo step

**When the server creates a document it runs the app's `setup_commands` once, as one `core.Setup` entry by the maker:**
a workbook's first sheet ("Sheet1"), a text's or presentation's language (D915: the language of the maker's interface,
which the client sends as `locale` in `hello`). The entry is in the history, under the maker's name; it is never an undo
step. Clients no longer do any of it.

**Notes.** QA (UX-33) found that a person's first Ctrl+Z in a new workbook removed its only sheet ("This document has no
sheet yet."), and that a new text offered "Undo Language" before anybody had done anything: the web client had made
both as her own first steps. Doing it on the server also gives every client the same start, the Python client included.
Changing `empty()` instead was not possible: documents already written begin with their own `AddSheet`, and replaying
them on a model that already had the sheet would fail.

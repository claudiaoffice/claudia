---
id: D723
title: "An import is redacted by its app, in full or in parts, and its kept original goes"
status: current
applies-to: all
date: 2026-11-16
round: "The redaction contract (D229), 2026-11-16"
supersedes: [D229]
superseded-by: []
---

# D723 · An import is redacted by its app, in full or in parts, and its kept original goes

**An import is redacted by blanking its content through its app, in full or in parts, and the kept original of the
file goes with it.** `DocumentModel.blank(parts)` blanks in place with the same shape rule as D720. Parts are named by
the app's own ids: a paragraph or an object in composes; a sheet, a range (`s1!A1:B5`), a chart tab or an object in
computes; a slide (with its notes and everything on it) or an object in creates. A full blanking also takes the file's
name; blanking in parts keeps it. The file's digest and the kept original (`content/original.bin`, D439) always go.

**Notes.** Before, `core.Import` could not be redacted at all, so a secret in an imported file stayed forever. The parts
are the granularity a person can point at in the preview; finer (a word inside a paragraph of an import) is not offered.
An app without `blank` refuses with a sentence rather than pretending.

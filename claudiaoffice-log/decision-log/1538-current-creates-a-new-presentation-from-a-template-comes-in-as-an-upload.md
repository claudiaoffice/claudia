---
id: D1538
title: "A new presentation from a template comes in as an upload, the way an import does"
status: current
applies-to: creates
date: 2026-11-23
round: "E10.4 Templates, layouts and placeholders (branch e10-4-templates-and-layouts)"
supersedes: []
superseded-by: []
---

# D1538 · Start from a template through an upload token

`GET /api/templates?locale=` lists the templates (before any document exists, so it is not a method of a document).
`POST /api/templates/{id}/upload?locale=` makes the new presentation the template starts: a copy with one slide on the
first layout that is not hidden, its things named in the language of the person, written as an export and held as any
upload is. What makes it a document is the usual way in, `hello` with `create` and `upload`.

* The person who starts it is its owner, and the starting is no export: nothing is recorded as leaving a document.
* Nothing is shared with the template and nothing follows it. The presentation keeps the note of the template's name,
  purpose and language, and nothing else (D1531).
* The same gate as for making documents: with an access secret, only those who know it.
* The upload is held for the usual few minutes and counts against the usual per-address limits.

Considered and rejected: a `new_from_template` method (a method runs in an open document, and here there is none); a
second way of making a document with its own checks for owner, password and name.

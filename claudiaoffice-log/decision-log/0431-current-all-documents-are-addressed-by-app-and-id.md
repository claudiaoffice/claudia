---
id: D431
title: "Each app keeps its own place in the document folder; a document is addressed by its app and its id"
status: current
applies-to: all
date: 2026-11-14
round: "One server, app modules (branch one-server)"
supersedes: []
superseded-by: []
---

# D431 · Each app keeps its own place in the document folder; a document is addressed by its app and its id

**Under `--dir DIR` each app keeps its documents in `DIR/<app>/` (sealed: `DIR/<app>/docs/<id>.claudia`; plain:
`--plain-dir DIR/<app>/`). Ids are unique per app, not per server. The live connection is
`/api/<app>/docs/<id>/ws`; `/api/<app>/docs` lists one app's documents and `/api/docs` lists all of them, each entry
with its `app`. The old `/api/docs/<id>/ws` stays: it opens the document of that id in the first module (in the order
of `--apps`) that has one, and makes a new document in the app named by `hello.app`, else in the first module.**

**Notes.** The id is the name a person types, and it is bound into the container's encryption (the head record's
associated data), so a document can never be renamed to resolve a clash. "notes" can exist in computes and in
composes; one namespace would have made the second impossible to create, or ambiguous to open. Keeping one place per
app makes a clash impossible and keeps each store exactly as it was (one `SealedDocuments` per module).

The old address picks the first module rather than refusing an id that exists in two apps: refusing would tell a
stranger which ids exist (SEC-04) on a server whose list is switched off. A wrong pick costs the person a refused
password, nothing else. Clients should use the address with the app; the web client changes over in its own patch.

A sealed store refuses to open a file whose manifest says it belongs to another app (`ValueError`), and lists only
its own app's files.

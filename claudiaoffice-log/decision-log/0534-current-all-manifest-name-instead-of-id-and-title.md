---
id: D534
title: "The manifest's id is called name; it has no title"
status: current
applies-to: all
date: 2026-11-15
round: "Document handling on the front page (branch file-handling)"
supersedes: []
superseded-by: []
---

# D534 · The manifest's id is called name; it has no title

**In the container the document's `id` is `name` (manifest key `name`, `Manifest.name`, `create_document(name=...)`) because it is what people call the document and it must be unique on a server; the random id is `uid` (D533). `title` is removed: it was a copy of the name that nothing changed or showed. A document has these properties apart from its sealed content: `name`, `uid`, `app`, `description`, `tags`, `unlisted`, `created`, `last_change`, and for opening it `kdf`, `salt` and `ciphers`; and `slots.json` (locators and sealed keys, no names). On the network the key is still called `id` (list rows, upload answer, `place` answer, routes); renaming it there changes every client and is a follow-up, as is the name `doc_id` inside the server's Python API. `unlisted` is stored and read but nothing in the server uses it yet.**

**Notes.** Owner, 2026-11-15: "the ID field of today sounds like a name, and if that is the case (and it is used like a name) then it should be named such." The container is the only place changed now so that the file and the uid have the right words from the start; the wire keeps `id` because the web app, the shells and the other chat's design all read it today. Not migrated: pre-release.
---
id: D533
title: "Every document has a random uid in its plain manifest, bound into everything sealed, and nobody ever sees it"
status: current
applies-to: all
date: 2026-11-15
round: "Document handling on the front page (branch file-handling)"
supersedes: []
superseded-by: []
---

# D533 · Every document has a random uid in its plain manifest, bound into everything sealed, and nobody ever sees it

**A new document gets a `uid` when it is made: a random version 4 UUID from the system's random source (lower case, 36 characters), written to the plain manifest. It says nothing about the owner, the name, the content or the time. It is never shown to a person: not in the list, not in the upload answer, not on a screen. The server tells it to the client in the welcome (`uid`, `null` for a store that has none), so that a client can keep it in a link later; a person is only told in words, such as that a document "is on this server already, as plan". It stays when the file is moved, copied or placed, and it never changes (a copy that is meant to be another document will need a new uid and a new name: not built). The sealed parts are bound to `name:uid` (`Manifest.binding`), where they were bound to the id: slots, the list of people, blocks, head, snapshot, original and journal. The manifest is plain, so anybody holding the file can change a field; with the binding a changed name or uid makes every slot fail to open, and a forged file cannot pass as another document or hide under another uid, while the plain description and tags stay as unprotected as before (D530). No migration: the format has no released files (the owner).**

**Notes.** Owner, 2026-11-15: "The ID is invisible to the user completely. We may tell him in plain language if there are any collisions." Design from the chat about linking tables from computes into composes (the other session's attachment): a random id like a UUID, in the plain manifest, that makes a document traceable without giving away anything about its content or owner. The uid is a capability in the sense that whoever knows it can ask a server whether it has the document (D535), so it stays out of every list. A name contains no colon (the name rule allows letters, digits, `_` and `-`), so `name:uid` is unambiguous. Version 4 and the canonical form are checked on reading: a manifest with another form is "not a document" rather than a document with an odd id.
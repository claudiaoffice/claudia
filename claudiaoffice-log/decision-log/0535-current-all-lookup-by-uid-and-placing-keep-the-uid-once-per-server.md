---
id: D535
title: "A document is found by its exact uid and a file keeps its uid when it is placed; a uid is never twice on a server"
status: current
applies-to: all
date: 2026-11-15
round: "Document handling on the front page (branch file-handling)"
supersedes: []
superseded-by: []
---

# D535 · A document is found by its exact uid and a file keeps its uid when it is placed; a uid is never twice on a server

**`POST /api/docs/lookup` with `{"uid": "..."}` answers `{app, id, modified}` for the document of any app of the server that has exactly that uid, else 404 (the same 404 for a missing uid and for something that is not a uid; 400 for a body that is not `{"uid": ...}`). It answers whoever may list the server: a server started without a list (`--no-list`) does not answer, one with an access secret asks for it as the list does, and one address may ask 60 times a minute (429, `Retry-After`). It tells no more than the list does. Placing a Claudia file (`POST /api/uploads/<token>/place`) keeps the file as it is, so also its uid, and refuses (409) a file whose uid belongs to a document of this server, in any app and under any name, with a sentence that names the document here ("This document is on this server already, as “plan”. It cannot be added a second time."); the upload answer says it beforehand in `same_document` (the name of that document, or `null`), and the import dialog offers to open the one that is here. A document made on a server gets a fresh uid, so two documents of a server never share one.**

**Notes.** Owner, 2026-11-15: "double IDs on server are forbidden"; "Only focus on the ID lookup and placing for now!" Open, and recorded rather than decided silently: (1) lookup follows `--no-list`: a server that hides its list also hides what it holds, which suits a server that wants to stay unlisted, but a link to a document there then finds nothing; (2) the manifest `unlisted` flag could instead exclude single documents from list and lookup, and is not used yet; (3) the lookup reads every manifest of the server (cheap next to a password hash, and throttled), an index would be the next step for a server with many thousands of documents; (4) the check across modules is not atomic: two files with the same uid placed at the same moment into different apps could both go in; the uid is 122 random bits, so it takes a forged file to try. Out of scope here, from the same design: the links themselves (source uid, server hints, last-known name, who accepted), pull as an export logged in the source, credentials never stored in a document, and the switch of owner.
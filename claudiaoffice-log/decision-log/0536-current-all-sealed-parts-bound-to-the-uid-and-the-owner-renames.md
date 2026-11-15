---
id: D536
title: "The sealed parts are bound to the uid alone; the name is a plain property the owner can change, and clients keep the uid"
status: current
applies-to: all
date: 2026-11-15
round: "QA of 2026-11-15"
supersedes: []
superseded-by: []
---

# D536 · The sealed parts are bound to the uid alone; the name is a plain property the owner can change, and clients keep the uid

**A document's name can be changed; its uid never is. Everything sealed in the file (slots, the list of people,
blocks, head, snapshot, original, journal) is bound to the uid only, no longer to `name:uid` (this replaces that part of
D533). The name stays in the plain manifest, unique on a server (D534), and is changed by the document's owner, with
her own password, as one request on the server (`rename_document`); an editor or a viewer may not, because every
person's saved places name the document. The clients keep the uid next to the name wherever they remember a document
(Mine, collections, recent, a shell's list): the welcome carries it already (D533), and a remembered document whose name
no longer answers is looked up by its uid (D535) and the entry updated, so a rename does not break anybody's list.**

**Notes.** Owner, 2026-11-15, after the QA: "the info dialog about a document warns that the name is baked into the doc
and cannot be changed. That was something we wanted to avoid through the uuid for every doc, so the name of the doc
could be freely chosen while the uuid stayed. Only owners should be able to rename because it would invalidate every
other user's map." He chose binding to the uid alone (over keeping the name sealed and offering a copy), the owner as
the one who renames, clients that key by the uid, and the decision and a story now with the build on its own branch
(E5.21). Why the binding has to change: with `name:uid` every person's key slot is bound to the name, so a rename would
need every member's password to seal the slots again. What the binding to the uid still protects: a file cannot pass as
another document or hide under another uid; what it gives up: somebody who can write the file can change its name, as
they can its description and tags today (D530) — the server's own rename is the only one that also renames the file and
keeps the name unique. Open for the build: the wire still says `id` for the name (D534's follow-up) and the document's
address contains it (`/api/<app>/docs/<name>/ws`), so the people connected when it is renamed are told and reconnect
under the new name; a rename while somebody else holds the document open is refused or waits (to be decided in E5.21).
No migration (D437).

---
id: D440
title: "A file comes in over HTTP first and becomes a document through the usual hello"
status: current
applies-to: all
date: 2026-11-14
round: "Opening files from the computer (branch one-server)"
supersedes: []
superseded-by: []
---

# D440 · A file comes in over HTTP first and becomes a document through the usual `hello`

**`POST /api/uploads` takes the file's bytes as the body (its name in `X-Claudia-Name`), looks at the bytes — never
the name — and holds them under a random token for at most five minutes. It answers what the file is: format, app,
size, a suggested id. Then `hello` with `create: true` and `upload: <token>` at `/api/<app>/docs/<id>/ws` makes the
new document, with all the rules of making one (the access secret, the document cap, the owner). Formats: docx, odt
(composes), xlsx, ods (computes), pptx, odp (creates), and Claudia files (D442). At most 64 MB a file, 16 uploads
waiting, 4 from one address; with an access secret only those who know it may upload.**

**Notes.** The live connection carries JSON frames only; a file over it would have to be base64 in one frame. A
separate import route would have needed its own login, owner and cap rules; letting `hello` do the making keeps one way
in. An upload alone changes nothing on disk. A file of another app's kind, an id that exists, and a token that has
expired are refused with a sentence for the person.

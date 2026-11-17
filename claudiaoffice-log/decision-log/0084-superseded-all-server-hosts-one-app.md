---
id: D84
title: "A server hosts one app, and the list of documents says which"
status: superseded
applies-to: all
date: 2026-11-03
round: "Claudia creates, first draft (fourteenth round)"
supersedes: []
superseded-by: [D430]
---

# D84 · A server hosts one app, and the list of documents says which

**A server hosts one app, and the list of documents says which.** `GET /api/docs` returns `{app, documents}`. A `DocumentProvider` therefore has an `app`.

**Notes.** Breaking for provider implementations. The web app has a shared `DocumentSession` and `DocumentFrame`.

**Checked against the code, 2026-11-17 (`main` at `6814bac`).** Superseded by D430: one server hosts the apps as modules; `/api/docs` lists the documents of every app (`suite.py`, `hub.listing`). Proposed in DOC-03 and confirmed by the code.

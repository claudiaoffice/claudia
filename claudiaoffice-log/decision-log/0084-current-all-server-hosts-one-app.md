---
id: D84
title: "A server hosts one app, and the list of documents says which"
status: current
applies-to: all
date: 2026-11-03
round: "Claudia creates, first draft (fourteenth round)"
supersedes: []
superseded-by: []
---

# D84 · A server hosts one app, and the list of documents says which

**A server hosts one app, and the list of documents says which.** `GET /api/docs` returns `{app, documents}`. A `DocumentProvider` therefore has an `app`.

**Notes.** Breaking for provider implementations. The web app has a shared `DocumentSession` and `DocumentFrame`.

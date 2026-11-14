---
id: D432
title: "Limits, the access secret, the administrators and the settings belong to the server, not to an app"
status: current
applies-to: all
date: 2026-11-14
round: "One server, app modules (branch one-server)"
supersedes: []
superseded-by: []
---

# D432 · Limits, the access secret, the administrators and the settings belong to the server, not to an app

**`max_documents` counts the documents of all apps together; the waiting room (`max_waiting`,
`max_waiting_per_address`) and the password hashing are shared; one access secret gates making documents and reading
the list in every app; one set of administrators manages the whole server, from one state folder (`--state-dir`).
`max_connections` stays per document. The AI settings apply to every module that has a lens (computes, creates); the
others keep their scripted stand-in.**

**Notes.** A per-app document cap would let anybody who can reach the server make three times as many documents as
its administrator allowed (SEC-02 is about the disk, not about an app). Before any release there is nothing to merge:
existing state is not carried over (D437).

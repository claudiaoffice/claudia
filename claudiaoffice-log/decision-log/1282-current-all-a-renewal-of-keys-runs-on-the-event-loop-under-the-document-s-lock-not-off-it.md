---
id: D1282
title: "A renewal of keys runs on the event loop under the document's lock, not off it"
status: current
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round, slice C (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1282 · A renewal of keys runs on the event loop under the document's lock, not off it

**Made while building slice C; the owner has not seen it yet (proposal, built). It deviates from D1263**, which said the
renewal would run off the event loop so that others could keep working.

- The renewal rewrites the file and the journal in one go. Appends from other people would race with it (a record written
  under the old key while the file is replaced), so it runs under `SealedDocuments._lock`, on the loop.
- For a normal document it takes about as long as writing the file once. The dialog says so ("about as long as writing
  the file once") and shows a status line while it runs.

**What it costs.** A very large document stops the server's other documents for that time. If that shows in practice the
way out is a per-document queue in front of the lock and a worker thread behind it; nothing in the file format changes.

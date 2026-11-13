---
id: D50
title: "superseded by D53"
status: current
applies-to: all
date: 2026-11-02
round: "Kernel and server (sixth round)"
supersedes: []
superseded-by: []
---

# D50 · superseded by D53

*Proposal; the listing part is **superseded by D53**.* **Server access:** credentials travel in the first WebSocket frame, never in the URL; name plus password per document; the first person who asks for a document that does not exist becomes its owner; a wrong password, an unknown name and a missing document give the same answer; the name `ai` is refused; TLS by default with a self-made certificate whose fingerprint the client trusts like an SSH host; a browser page from another origin is refused unless named.

**Notes.** With D53 the "same answer" rule can only hold for documents that are not listed.

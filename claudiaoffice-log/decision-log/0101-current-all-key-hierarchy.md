---
id: D101
title: "Key hierarchy"
status: current
applies-to: all
date: 2026-11-02
round: "Document container and encryption (seventeenth round)"
supersedes: []
superseded-by: []
---

# D101 · Key hierarchy

**Key hierarchy.** One slot per user (name and password). A slot wraps the domain keys (content, history, chat) that the user's role may have. Viewers get the content key only. Removing a user deletes the slot; an owner may also rotate keys. The UI says plainly that this cannot recall copies already made.

**Notes.** Refines D20, D34, D35. Key rotation is not built.

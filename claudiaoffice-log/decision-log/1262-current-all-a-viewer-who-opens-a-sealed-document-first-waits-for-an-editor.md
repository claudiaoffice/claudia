---
id: D1262
title: "A viewer who opens a sealed document first waits for an editor; read-only hosting is a story of its own"
status: current
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1262 · A viewer who opens a sealed document first waits for an editor; read-only hosting is a story of its own

**Decided by the owner 2026-11-19 (accepted the proposal). Not built.** A viewer holds the content key only (D101), and
the server brings a document up from the history, which a viewer cannot read. So a viewer who is the first to log in
after the server has let go of the document's keys gets the close code `sealed` (4423) as today, and the web app keeps
trying. What changes is the words: "An editor or owner has to open this document first. This window will open it as soon
as one has." (the same in the desktop clients).

Hosting the snapshot read-only for a viewer, and handing the viewer over to the live document when an editor arrives, is
not part of this round. It is the story E2.11.

**Notes.** An owner or editor is almost always the one who opens a document first. If a deployment shows otherwise,
E2.11 moves up.

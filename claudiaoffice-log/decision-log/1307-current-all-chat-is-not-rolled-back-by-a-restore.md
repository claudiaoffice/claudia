---
id: D1307
title: "Chat is not rolled back by a restore: the conversation that led to it stays"
status: current
applies-to: all
date: 2026-11-19
round: "E1 core, closing out the open stories (branch e1-core)"
supersedes: []
superseded-by: []
---

# D1307 · Chat is not rolled back by a restore: the conversation that led to it stays

**Decided 2026-11-19** by the owner: "I don't think chat should be rolled back, I want to see the conversation that led to the restore!" Settles one of the side effects listed in D235.

A restore (D51, D52) forks the *document*; **the chat is not part of the fork.** Every message stays where it was written, after the restore as before it, and the restore itself appears in the conversation (as its entry in the History & Chat panel does) so the reader can follow what was said and why. Each chat record keeps the revision it was written at (E1.6), so a message written on a line that is now hidden still says which state it was about; it is not hidden with the line.

**Notes.** What is left open of D235: viewers must not see hidden lines, and the `ai` user must rebuild its context after a restore. Redaction (D720–D726) still reaches chat messages, whatever the line.

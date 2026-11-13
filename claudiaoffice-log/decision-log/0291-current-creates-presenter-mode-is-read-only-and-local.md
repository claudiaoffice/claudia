---
id: D291
title: "Presenting is read-only and local: anyone who can open the document may present, it takes no locks and writes no command"
status: current
applies-to: creates
date: 2026-11-13
round: "Presenter mode in creates (E10.2, branch `presenter`)"
supersedes: []
superseded-by: []
---

# D291 · Presenting is read-only and local: anyone who can open the document may present, it takes no locks and writes no command

**Presenting is read-only and local.** Everyone who can open the document may present it. A show takes no locks, writes no command and leaves nothing in the history, so other people keep editing while someone presents. The people list shows one presence line ("anna is presenting · slide 4"), like any other presence; nothing about it is written into the document.

**Notes.** The owner's answer to question 4 of `notes/e10-2-presenter-mode.md`, 2026-11-13 ("yes"). Planned times and notes are document content and are written like any other edit (D293, D294); the show itself is not.

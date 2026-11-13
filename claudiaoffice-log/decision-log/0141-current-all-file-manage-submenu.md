---
id: D141
title: "File ▸ Manage replaces the flat Share item with a submenu of six"
status: current
applies-to: all
date: 2026-11-06
round: "The Manage menu: leaving, handing over ownership, exporting and deleting (twenty-third round)"
supersedes: []
superseded-by: []
---

# D141 · File ▸ Manage replaces the flat Share item with a submenu of six

**File ▸ Manage replaces the flat Share item with a submenu of six:** Share…, Assign new owner…, Accept ownership…, Leave document…, Export…, Delete from server…. Built for composes, computes and creates alike, on the web and in the GTK shell manifest, under the shared id namespace `file.manage.*`.

**Notes.** "Accept ownership…" was not in the original mockup — added because the propose/accept transfer flow (D142) is otherwise unreachable by the person being handed the document. This round also re-fixed `uv.lock.rej`'s staged deletion (D133 deleted the file on disk but never staged the `git rm`) and closed DOC-01 for this round's own new citations.

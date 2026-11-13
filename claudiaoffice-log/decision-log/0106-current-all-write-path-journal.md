---
id: D106
title: "Write path"
status: current
applies-to: all
date: 2026-11-02
round: "Document container and encryption (seventeenth round)"
supersedes: []
superseded-by: []
---

# D106 · Write path

**Write path.** An open document is the container zip plus a journal file next to it. When the document is idle or closed the server packs the journal into compressed, encrypted blocks and replaces the zip atomically. An edit is acknowledged only when it is safely on disk. **Every file a person takes away is one complete file.**

**Notes.** The acknowledge-after-fsync part is built; the **group commit off the event loop is not** (PERF-02).

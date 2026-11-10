---
id: D114
title: "The shell contract is a versioned JSON schema"
status: current
applies-to: all
date: 2026-11-03
round: "Native clients (eighteenth round)"
supersedes: []
superseded-by: []
---

# D114 · The shell contract is a versioned JSON schema

**The shell contract is a versioned JSON schema.** Additive changes keep the version; anything else is a new version with a new file, and the old file stays while a shell or the web app still speaks it. The page names the highest version it speaks in `hello`; the shell answers with the highest both speak. Unknown message types are ignored; messages are at most 64 KiB.

**Notes.** Answers the versioning part of the open question on E5.12.

---
id: D19
title: "JSON-based, zipped and by default encrypted"
status: current
applies-to: all
date: 2026-11-01
round: "Common to all three apps"
supersedes: []
superseded-by: []
---

# D19 · JSON-based, zipped and by default encrypted

Claudia's own format is **JSON-based, zipped and by default encrypted** with a user-provided password. MS Office and OpenDocument are import/export only.

**Notes.** ZIP is only the container; entries are encrypted with our own scheme (D34, D100–D112). ZIP's built-in AES is not usable (PBKDF2-SHA1, 1,000 iterations, and `zipfile` cannot write it).

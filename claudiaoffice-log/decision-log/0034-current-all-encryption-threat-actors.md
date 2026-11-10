---
id: D34
title: "outsiders holding the file"
status: current
applies-to: all
date: 2026-11-01
round: "Security, calculation and extensibility (second round)"
supersedes: []
superseded-by: []
---

# D34 · outsiders holding the file

Encryption defends against **outsiders holding the file** and against **co-editors** who must not see parts of the history or chat.

**Notes.** Design: key slots per password; keys per domain (content, history, chat); commands in blocks, compressed then encrypted; redaction rewrites a block. The server sees plaintext only while a document is open. Detailed by D100–D112.

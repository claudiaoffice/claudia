---
id: D151
title: "Administrator accounts are a separate, server-scoped identity — never a user inside a document"
status: current
applies-to: all
date: 2026-11-07
round: "Server administrators and settings (twenty-seventh round)"
supersedes: []
superseded-by: []
---

# D151 · Administrator accounts are a separate, server-scoped identity — never a user inside a document

**Administrator accounts are a separate, server-scoped identity — never a user inside a document.** Named accounts, scrypt-hashed exactly like a document's own users (D20, D35), held in their own on-disk directory; removing the last administrator is refused.

**Notes.** Keeps the two identity systems from ever mixing: a document's users (D20, D35) answer "who may touch this document," while administrators answer "who may configure this server," and nothing links the two namespaces.

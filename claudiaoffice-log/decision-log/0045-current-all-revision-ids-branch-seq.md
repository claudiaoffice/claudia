---
id: D45
title: "Revision identifiers are `(branch, seq)` with a parent link"
status: current
applies-to: all
date: 2026-11-02
round: "Kernel and server (sixth round)"
supersedes: []
superseded-by: []
---

# D45 · Revision identifiers are `(branch, seq)` with a parent link

**Revision identifiers are `(branch, seq)` with a parent link**, not content hashes and not bare integers.

**Notes.** Sequence numbers continue along a branch from its fork point; redaction never changes an id; no tamper evidence from the id itself.

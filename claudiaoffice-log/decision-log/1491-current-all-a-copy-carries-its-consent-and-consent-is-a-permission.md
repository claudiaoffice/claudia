---
id: D1491
title: "A copy carries its consent to another server; consent is a permission, not an obligation"
status: current
applies-to: all
date: 2026-11-22
round: "E7.11 Claude as an AI provider (branch e7-11-claude-provider)"
supersedes: []
superseded-by: []
---

# D1491 · A copy carries its consent to another server; consent is a permission, not an obligation

**Decided 2026-11-22 (owner's answers on the branch).**

- A copy of a document carries the consent with it; nothing records which server gave it.
- Consent is a **permission**: where Claude is not the server's provider, or the owners did not allow it, the server's own
  provider (the local model, else the scripted stand-in) answers `@ai`, says so under the answer, and nothing is an error.
- The sentence for a document whose owners did not allow Claude: "Claude is not allowed in this document. The owners can
  change that in Preferences ▸ AI…".

Assumption listed in the patch notes: with Claude chosen, the local model is loaded as well when a model folder is set,
so there is something to fall back to; that costs memory.

---
id: D1490
title: "The owners' consent for Claude is a second sealed list in the document file, not the exit record"
status: current
applies-to: all
date: 2026-11-22
round: "E7.11 Claude as an AI provider (branch e7-11-claude-provider)"
supersedes: []
superseded-by: []
---

# D1490 · The owners' consent for Claude is a second sealed list in the document file, not the exit record

**Decided with the owner 2026-11-22; built in E7.11.**

Whether Claude may be sent a document's content is the owners' decision (D264). It is kept in the document file as a
list of its own, beside the exit record: sealed with the content key, covered by the file's head, not part of the
history, the chat or the exit record, and not undoable.

- Format: the file schema is raised to 3 for the new list; 2 is still read; 4 is "newer" and refused. New kinds of list raise it again.
- `ai_consent` (any role, a viewer too) and `set_ai_consent` (owners only; `forbidden` for others, `unavailable` where the
  server keeps no document files, where consent is always off).
- `ai_consent_changed` is an ephemeral event classified CONTENT in the audience rules.
- The administrator holds no document key, so cannot give or fake it (D264).

**Why not the exit record.** The exit record says what *left* the document; allowing Claude is a permission, not an
event that sent anything. Mixing them would make an owner's tick look like an export.

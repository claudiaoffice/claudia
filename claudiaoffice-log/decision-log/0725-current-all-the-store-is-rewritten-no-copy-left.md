---
id: D725
title: "A redaction rewrites the document file and its journal; no copy is left (SEC-05)"
status: current
applies-to: all
date: 2026-11-16
round: "The redaction contract (D229), 2026-11-16"
supersedes: [D229]
superseded-by: []
---

# D725 · A redaction rewrites the document file and its journal; no copy is left (SEC-05)

**A redaction rewrites what the server stores, so that no copy of the content is left in the document folder.** The
store holds exactly the redacted history and chat afterwards (`DocumentStore.rewrite`): the sealed store seals the
blocks of the file anew from them, drops the snapshot and replaces the journal by an empty one
(`claudia_container.rewrite_journal`), with the same crash order as packing; the plain store writes its journal anew,
all at once. Copies, exports and backups made earlier keep the content (D21), and the help text says so; what a file
system or disk keeps of overwritten blocks is outside what Claudia can reach.

**Notes.** Fixes SEC-05. The redaction is not carried out in memory if the store cannot rewrite.

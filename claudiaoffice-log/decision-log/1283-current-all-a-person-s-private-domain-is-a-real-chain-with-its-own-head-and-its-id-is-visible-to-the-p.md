---
id: D1283
title: "A person's private domain is a real chain with its own head, and its id is visible to the people-list readers"
status: current
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round, slice C (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1283 · A person's private domain is a real chain with its own head, and its id is visible to the people-list readers

**Made while building slice C; the owner has not seen it yet (proposal, built).** D1265 left the storage open.

- `private/<id>/NNNNNN.blk` and `private/<id>/head.bin`, sealed with her private-domain key only (stream byte 5). Every
  person has one chain, always at least one (possibly empty) block, so the existence of a chain says nothing.
- The id of her chain is in `people.bin`, which everybody with the content key reads: they can see which entries belong to
  whom, not what is in them.
- Recovery gives her a new key pair and a new private domain and deletes the old chain (the old key is lost with the
  password). Removal and leaving delete it.

**What it costs.** Anybody who holds the file sees the sizes of the chains; a large private domain shows. The content is
what the key protects, not its size.

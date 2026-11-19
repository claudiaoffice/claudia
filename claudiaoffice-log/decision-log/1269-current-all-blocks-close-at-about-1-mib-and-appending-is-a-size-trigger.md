---
id: D1269
title: "Blocks close at about 1 MiB; appending without rewriting is a size trigger, not a promise"
status: current
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1269 · Blocks close at about 1 MiB; appending without rewriting is a size trigger, not a promise

**Decided by the owner 2026-11-19 (accepted the proposal).** The block policy, written down (E2.5):

- A block of history or chat closes when its commands reach 1 MiB before compression (`BLOCK_TARGET_BYTES`; the reader
  accepts up to 64 MiB). Commands are packed into blocks when the document is released, when it has been idle, and after
  every 500 changes (`DEFAULT_PACK_EVERY`).
- A closed block is not changed again, except by redaction (D725), by key renewal (D1263) or by deleting a person's private
  domain (D1265). **The last block, while it is under the target, is replaced when more commands arrive** (`_extend`);
  that is not a violation of the rule, it is the one open block.
- The compression ratio is measured against sealing every command on its own (28 bytes of nonce and tag each, and no
  compression across commands) on the real logs of the test documents, and the result is written to the E2.5 story.
- **"Appending without rewriting old blocks"** (the story's acceptance) is relaxed: packing writes the whole zip again
  (PERF-06), which is accepted up to about 50 MB. Above that a document needs appending, and the size is the trigger for the
  story, not a promise of this round.

**Notes.** Someone who holds the file can count the blocks and so estimate how much was written; that is as readable as the
number of key slots (D100).

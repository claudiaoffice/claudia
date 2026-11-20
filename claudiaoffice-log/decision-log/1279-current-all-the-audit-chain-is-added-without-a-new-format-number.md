---
id: D1279
title: "The record of what left is added to the document format without a new format number"
status: current
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1279 · The record of what left is added to the document format without a new format number

**Made while building slice B; the owner has not seen it yet (proposal, built).** The audit chain (D1271) is a third folder
of blocks, `audit/NNNNNN.blk`, and a third entry in the head. The format text stays `claudia-document 1`:

- A document has the chain only after its first export, print or PDF; a head without it reads as an empty chain, so every
  file written so far opens unchanged in the new program.
- A program that does not know the chain refuses a file that has one, as damaged ("does not belong in the block folders"),
  not with the sentence for a newer version. This is the one thing that is worse than a number would make it.
- Slice C changes the slots and the people list; **the number goes to 2 there**, once, so a program that knows 1 only
  says "written by a newer version" for both changes. Between the two slices no release is made.

**Why.** One number per change would make three numbers in one round, each a file that the next older program would have to
refuse differently; and nobody runs a program of the older kind on these files yet (no release; D1273 puts the external
review before the first one).

**What it costs.** For the days between the slices, a document that was exported once cannot be opened by a server of the
branch before slice B. If that matters, the number can go to 2 in slice B instead: the reader already refuses a higher number
with the right sentence (`UnsupportedFormat`).

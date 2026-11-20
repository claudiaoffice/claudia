---
id: D1281
title: "The format number goes to 2 in slice C, and a file of format 1 is refused"
status: current
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round, slice C (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1281 · The format number goes to 2 in slice C, and a file of format 1 is refused

**Made while building slice C; the owner has not seen it yet (proposal, built).** D1279 promised it: slots, the people list and
the head change, so `claudia-document 2` is written from now on.

- A file of format 1 is refused with `OutdatedFormat` and a sentence that says it was written by an older version. There is
  no upgrade in place: no release has been made (D1273), and the keys of a person cannot be invented for an old slot.
- Format 3 and up is "newer", as before (`UnsupportedFormat`).

**What it costs.** Every `.claudia` file made on the branch before slice C has to be created again.

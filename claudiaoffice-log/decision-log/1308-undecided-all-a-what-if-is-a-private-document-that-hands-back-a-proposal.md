---
id: D1308
title: "A what-if is a private document over a copy that hands back a proposal, applied as one step or refused as outdated"
status: undecided
applies-to: all
date: 2026-11-19
round: "E1 core, closing out the open stories (branch e1-core)"
supersedes: []
superseded-by: []
---

# D1308 · A what-if is a private document over a copy that hands back a proposal, applied as one step or refused as outdated

**Proposed 2026-11-19, not yet confirmed by the owner.** The owner asked to build the API for D236 now. The full proposal, the list of what already scratches and the questions are in `notes/e1-what-if-api.md`.

In short: `Document.what_if(at)` returns a `WhatIf` that runs commands on a copy and remembers them; `proposal()` gives plain data (base revision, commands, footprint); `Document.apply_proposal` applies it on the head as one `Batch`, or raises `ProposalOutdated` with the conflicts when the footprint was touched (or a structural change happened in the same container), and never rebases. A server `WhatIfDesk` keeps what-ifs private to the person, with limits. It is not a line (D48, D263). First consumer: the AI's suggest mode (E7.8).

**Notes.** When confirmed this decision settles D236 (free what-if branches) and its status becomes `current`. Open questions with proposed defaults: private and in memory only; outdated rule; limits; write methods through the method table; a new `Entry.via` field.

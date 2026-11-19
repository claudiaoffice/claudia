---
id: D1308
title: "A what-if is a private document over a copy that hands back a proposal, applied as one step or refused as outdated"
status: current
applies-to: all
date: 2026-11-19
round: "E1 core, closing out the open stories (branch e1-core)"
supersedes: [D236]
superseded-by: []
---

# D1308 · A what-if is a private document over a copy that hands back a proposal, applied as one step or refused as outdated

**Decided 2026-11-19** by the owner ("your WhatIf design is perfect, especially well thought toward the future use cases"; to be built together with the current work on E1). The owner asked to build the API for D236 now. The full proposal, the list of what already scratches and the questions are in `notes/e1-what-if-api.md`.

In short: `Document.what_if(at)` returns a `WhatIf` that runs commands on a copy and remembers them; `proposal()` gives plain data (base revision, commands, footprint); `Document.apply_proposal` applies it on the head as one `Batch`, or raises `ProposalOutdated` with the conflicts when the footprint was touched (or a structural change happened in the same container), and never rebases. A server `WhatIfDesk` keeps what-ifs private to the person, with limits. It is not a line (D48, D263). First consumer: the AI's suggest mode (E7.8).

**Notes.** Settles D236 (free what-if branches), which it supersedes. The six questions at the end of the note (private and in memory only; the outdated rule; limits of 3 per person and 15 minutes; write methods through the method table; a new `Entry.via` field; the word "preview" in screens) were taken with the design as proposed: the owner approved the design without changing them.

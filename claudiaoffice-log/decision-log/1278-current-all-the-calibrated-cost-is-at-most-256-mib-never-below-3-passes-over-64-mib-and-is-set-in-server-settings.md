---
id: D1278
title: "The calibrated cost is at most 256 MiB, never below 3 passes over 64 MiB, and is set in Server settings"
status: current
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1278 · The calibrated cost is at most 256 MiB, never below 3 passes over 64 MiB, and is set in Server settings

**Decided while building slice A, to be confirmed by the owner in the patch notes.** It fills in what D1267 left open (the
numbers around the 0.75 s target).

**The rule.** At start the server measures one pass at the most memory allowed (256 MiB) and chooses the number of passes
that fills the target time. If even the minimum passes would be slower than the target, it gives memory up by halving. It is
never weaker than the old fixed cost (3 passes over 64 MiB, 4 lanes), so a slow machine gets that minimum, slower than the
target if need be. The measuring runs in a background thread: the server is up at once, and until it is done the minimum is
used.

**The setting.** Server settings ▸ Security has one field, the target in seconds (0.1 to 30; default 0.75). Apply saves and
measures again, which is also how to measure after the hardware changed. A memory ceiling is not a setting yet: 256 MiB keeps
two simultaneous hashes (the cap of SEC-03) and a few documents within a small server's memory.

**Consequences.**

- New documents get the calibrated cost; existing ones keep theirs (D1267). The decoy hash for a document that does not
  exist uses the cost of a new document.
- The measured cost on a real server is not known yet (here: 256 MiB and 4 passes take about 0.6 s on a laptop-class
  machine); the owner may want to look at the banner and the Security page on the real server.
- The architecture mock showed a memory ceiling and a "Measure again" button; this slice builds the target field, and Apply
  measures again. The ceiling and a separate button wait for a reason.

**Rejected.** A fixed higher cost (a Raspberry Pi and a workstation need different numbers); measuring on every login (the
measuring itself costs what it tries to measure).

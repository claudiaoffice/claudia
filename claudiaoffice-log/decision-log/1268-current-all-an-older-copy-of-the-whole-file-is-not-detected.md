---
id: D1268
title: "Putting an older copy of the whole file back is not detected, and the documents say so"
status: current
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1268 · Putting an older copy of the whole file back is not detected, and the documents say so

**Decided by the owner 2026-11-19 (accepted the proposal).** The head record detects removed, extra, swapped and changed
blocks, but an older copy of the *whole* file is a valid file: its head fits its own blocks. The threat model already
lists this as "not detected" (D100). It stays that way for now, and the format specification (E2.1) and the help say it
in one sentence.

**Notes.** A server could keep a generation counter outside the file and notice an older copy being put back; that does
nothing for a file in someone's hands. Left for later, not rejected.

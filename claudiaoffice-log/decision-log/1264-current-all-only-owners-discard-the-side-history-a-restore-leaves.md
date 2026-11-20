---
id: D1264
title: "Only owners discard the side history a restore leaves"
status: current
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1264 · Only owners discard the side history a restore leaves

**Decided by the owner 2026-11-19 (accepted the proposal). Not built.** A restore returns to a checkpoint by making a new
one and leaves the line it left behind as side history (E1.7). Throwing that side history away is permanent, so only
owners may. Editors may look at it, as they may at any history. Discarding it goes through the same rewrite as
redaction (D725), so the bytes are gone from the file.

**Notes.** E2.3 listed "who may discard side history after a restore" as open.

**Slice C:** already true in the code (`discard_side_history` is owner-only); a test now says so.

---
id: D1273
title: "The security review is structured now and external before the first release"
status: current
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1273 · The security review is structured now and external before the first release

**Decided by the owner 2026-11-19 (accepted the proposal). Who does the external part, and with what budget, is open.**
E2.8 asks for a written threat model, which exists (D100), and a review, which has not happened.

- **Structured review, now, after the code of this round is in.** By an agent that has not seen the code being written, with
  the threat model and the format specification as its only brief; each finding becomes a story in the bugtracker.
- **External review of the key-slot scheme and the container before the first public release.** The threat model is the
  brief. The reviewer and the budget are the owner's to find.
- **Scope, both.** What the plain manifest and the document list reveal to somebody with no password (D103), including the
  readable title; the locator and key-slot scheme (D101, D102); the authenticated data of the blocks; viewers (D1261); key
  renewal (D1263); the audit chain (D1271); the private domain (D1265); and the exports and imports (D1270, D1272).

**Notes.** The threat model gets a row per new feature of this round (viewer, role change, audit chain, private domain,
unencrypted export and import, back-off) in `notes/e2-container-and-encryption.md`.

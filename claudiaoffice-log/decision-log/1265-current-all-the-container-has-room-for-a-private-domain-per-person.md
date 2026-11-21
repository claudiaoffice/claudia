---
id: D1265
title: "The container has room for a private domain per person"
status: current
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1265 · The container has room for a private domain per person

**Decided by the owner 2026-11-19 (accepted the proposal). Not built.** The private drawer of E16.8 depends on E2.2 and
E2.4 and must not be built on a format that is frozen without it. This round defines the mechanism; E16.8 fills it.

- A person may have a domain of her own: one random key, **wrapped only in her own key slot** — not in the recovery
  slot, not in any other person's — and a chain of blocks of its own, sealed with that key. Its name in the file is a
  random id, not hers (D102).
- No role, setting or recovery key opens another person's domain. The owner's remove dialog says "any private notes of
  this person are deleted" without saying whether there are any.
- Leaving the document or being removed deletes the slot's key and the person's blocks; they are gone from the file at
  the next write (the same rewrite as D725).
- A person who comes back with the recovery key gets a new slot and **loses her private domain**; the key-loss dialog
  says so (E16.8).
- The server holds the domain's key only while that person is connected, and renewing keys for others (D1263) never
  touches it.
- This round tests the mechanism with a stand-in payload. What goes into the domain (the scrapbook's notes) is E16.8.

**Notes.** Whether a viewer has a private domain is for E16.8; the container does not care about the role.

**Built in slice C** (container 0.12.0): `read_private`, `write_private`; see D1283 for how it is stored.

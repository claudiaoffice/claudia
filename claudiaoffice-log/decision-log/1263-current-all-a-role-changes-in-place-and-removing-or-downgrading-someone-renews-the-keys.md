---
id: D1263
title: "A role changes in place; removing or downgrading someone renews the keys they held"
status: current
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1263 · A role changes in place; removing or downgrading someone renews the keys they held

**Decided by the owner 2026-11-19 (accepted the proposal: build it now). Not built.** E2.2 and E2.3 both list key rotation
as not done, and E2.3 lists changing editor↔viewer without removing and re-adding the person.

- **Changing a role** is one action of an owner in the Share dialog. The server lets the person in with her new role at
  once, because it holds the keys while the document is open; what her slot in the file holds catches up at her next login
  (D1274). Only owners change roles; the last owner cannot be changed (ownership moves by handover, D142).
- **Removing a person, or downgrading an editor to viewer, renews the domain keys that person held** (removal: all of
  them; downgrade: history and chat). The blocks of those domains, the people list, the snapshot and the head are sealed
  again under the new keys, in one atomic replacement of the file. It uses the rewrite that redaction made (D725). **How
  the people who stay, and the recovery key, get the new keys is D1274** (decided: a sealed inbox): a slot is opened by its person's
  password, which nobody else has, so the owner cannot rewrite it.
- **What this protects, and what not,** is said in the dialog in words: the person keeps what she has already seen and
  every copy of the file she holds, which her old keys still open (D20). The new keys protect what is written *from now
  on* from anyone who holds only the old keys, for instance a removed person who later gets hold of a backup.
- **Cost.** About the time it takes to write the file again, so for a document of some megabytes a second or two. It runs
  off the event loop. People who are connected stay connected, and the server swaps the keys it holds for the document.
- A person who is connected when her role is lowered has her window told at once and gets the new limits on the next
  event, not at the next login.
- Renewing keys with nobody leaving has no menu entry yet (the menu structure of 2026-11-18 is not changed by this round).

**Notes.** An upgrade needs no rotation, because it gives away nothing the owner had not meant to give. Rotation does not
touch a person's private domain (D1265), which the server cannot read.

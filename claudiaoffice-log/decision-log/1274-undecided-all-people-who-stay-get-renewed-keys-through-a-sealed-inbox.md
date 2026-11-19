---
id: D1274
title: "People who stay get renewed keys through a sealed inbox, one public key per person"
status: undecided
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1274 · People who stay get renewed keys through a sealed inbox, one public key per person

**Proposed 2026-11-19 while planning D1263; waits for the owner. Not built.**

**The problem.** A key slot is opened by a key derived from its person's name and password (D101, D102). When keys are
renewed (D1263), or a role changes, the slots of the people who stay must hold the new keys, and only the person has the
password that opens her slot. An owner cannot rewrite it, and neither can the server for anyone who is not logged in. D1263
as first written ("every remaining slot is rewritten") cannot be done.

**The proposal.** Each person, and the recovery key, gets an X25519 key pair when the slot is made. The private key lives
in her slot, sealed as everything in it is. The public key is written beside her name in the people list (sealed with the
content key, so everyone in the document can read it, and it is not a secret). To give a person new keys, the owner's
server seals them to her public key (ephemeral X25519, HKDF-SHA256, AES-256-GCM, the primitives of D104 plus X25519) into
her **inbox** in the file, named by the same slot locator the people list already holds. At her next login the server opens
her slot with her password, takes the private key, opens the inbox, and writes a slot that holds the new keys; the inbox
entry is deleted. The recovery key's slot is brought up to date the same way, when it is next used. A removed person has no
public key in the list, so no inbox is made for her and nothing in the file opens for her again.

**What it costs.** One more primitive (X25519), a change to the slot and people formats (pre-release, so no migration; the
format specification of E2.1 describes it), and one more thing for the external review to look at (D1273).
A person who has not logged in since a renewal still holds slot keys that open only what they opened before; the server
serves her live as soon as she logs in.

**Rejected.** Making every person present for a renewal (impossible for a person who is away). Chaining new keys under the
old ones (the removed person holds the old ones and would follow the chain). A shared password for the document (D20).

**Notes.** Also what a role change needs: the owner puts the keys the person gains into her inbox. A role change that
takes keys away is the same as a renewal for those domains.

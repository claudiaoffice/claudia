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

## In plain words (added 2026-11-19, after the owner asked for it)

**What is the problem?** Every person has a locker in the file. Her password is the only key to her locker, and in it lie
the keys to the document's parts (the content, the history, the chat). When the owner removes Tobi, the keys Tobi held
must be replaced by new ones, or Tobi's old copy of the file would still open what is written afterwards. The new keys have
to reach everybody who stays, Anna and Ben. But the owner **cannot open Anna's locker**: only Anna's password does, and
nobody keeps passwords. So there is no way for the owner to put the new keys into it.

**What do we do about it?** Give every locker a **letter slot**. Everybody may post a letter through the slot, but only the
person whose locker it is can take the letters out. Technically: each person has a pair of keys, a public one (the slot,
stored in the people list, which is not secret) and a private one (stored inside her locker). The owner seals the new keys
with Anna's public key and leaves the letter in the file. When Anna next logs in, her password opens her locker, her
private key opens the letter, she takes the new keys out and the server puts them into her locker. The letter is then
deleted. Nobody but Anna can read Anna's letter, not even Tobi, whose old keys open nothing of it.

**What does it cost?** One more kind of key in the file (X25519, a well-known, small, standard one), and one more step at
login for people who were away during a renewal. Nothing changes for people who are online, because the server holds the
keys of an open document. If Anna was away for two renewals, the newest letter holds all the current keys, so she only
needs it.

**What was the alternative?** Ask everybody to type their password again whenever someone is removed. That does not work for
people who are not there, and it would be a reason never to remove anybody.

**Notes.** Also what a role change needs: the owner puts the keys the person gains into her inbox. A role change that
takes keys away is the same as a renewal for those domains.

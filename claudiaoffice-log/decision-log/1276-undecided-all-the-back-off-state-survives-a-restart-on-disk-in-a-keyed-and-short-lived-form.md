---
id: D1276
title: "The back-off state survives a restart: written to disk in a keyed, short-lived form"
status: undecided
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1276 · The back-off state survives a restart: written to disk in a keyed, short-lived form

**Proposed 2026-11-19 after the owner asked "can we write the backoff state to disk? Wouldn't that make it safer?". Waits for
the owner. Not built.** It changes D1266, which keeps the counters in memory.

**What it would buy.** The counters of D1266 live in memory, so a restart forgets them. Someone who guesses passwords
can therefore start again after the server restarts: by waiting for a deployment, or by making the server crash (a request
that exhausts its memory, say). What is lost is at most the current wait, 30 seconds at the top. Writing the state to
disk closes exactly that gap. It does **not** make guessing slower in any other way: the pace of guessing is set by the
wait and by the 0.75 second hashing (D1267), and neither depends on where the counters live. Many addresses at once
(a botnet) are not stopped by it either.

**So: a little safer, in one narrow case.** The cost is also modest, if done carefully:

- **Personal data.** An address is personal data in the EU. The file would hold neither addresses nor names, only a keyed
  hash of each (HMAC with a secret that stays in the server's state folder), and every entry would expire after
  15 minutes, so the file holds nothing after a quiet quarter of an hour. The same key hides the document and the name, so
  the file does not tell which documents exist (D50, SEC-04).
- **Writes an attacker can force.** A failed login would change the file. The snapshot is written at most every
  10 seconds and at shutdown, atomically; a crash loses at most those 10 seconds, which is far less than the wait the
  guesser would have got from a restart.
- **A table that grows by whatever an attacker sends** (names that do not exist count like those that do) is bounded;
  when it is full the oldest quiet entries go first.
- **More state, more code, and a file to protect** (mode 0600 in the state folder, as the certificate is).

**Proposal.** Yes, in that form, built together with D1266. **Alternative:** keep it in memory, state the gap in the
threat model (as it is now) and accept it, because a restart is rare and a wait of 30 seconds is all that is lost.

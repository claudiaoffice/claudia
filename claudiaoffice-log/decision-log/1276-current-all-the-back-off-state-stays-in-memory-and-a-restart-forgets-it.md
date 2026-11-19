---
id: D1276
title: "The back-off state stays in memory, and a restart forgets it"
status: current
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1276 · The back-off state stays in memory, and a restart forgets it

**Decided by the owner 2026-11-19 ("D1276: we'll keep back-off state in memory, not on disk"), after the owner had asked
whether writing it to disk would be safer. Built with D1266 in slice A of the second round of E2.** It confirms the
choice D1266 already made and records why the other one was not taken.

**What the choice means.** The counters of D1266 (failures per address and per document and name) live in the server's
memory only. A restart forgets them. Someone who guesses passwords can start again after the server restarts, by waiting
for a deployment or by making the server crash. What is lost is at most the wait the guesser had earned, 30 seconds at the
top.

**Why that is accepted.** Writing the state to disk would close exactly that gap and no other: the pace of guessing is set
by the wait and by the 0.75 second hashing (D1267), and neither depends on where the counters live; many addresses at
once are not stopped by it either. A disk copy would cost more than it buys: addresses are personal data in the EU (a
keyed, expiring file would be needed), a failed login would become a disk write that an attacker can force, a table that
grows by whatever an attacker sends would need a bound, and a file would have to be protected. A restart is rare.

**Consequences.**

- The threat model states the gap: *a restart forgets the back-off counters; a guesser regains at most one wait.*
- No file in the server's state folder holds addresses or names, which also keeps the privacy statement short (nothing
  about logins is stored beyond the fifteen minutes in memory).
- The `LoginThrottle` takes an injected clock and has no persistence hook; if a later decision wants one it is a new
  decision.

**Rejected.** A keyed, short-lived snapshot on disk (written at most every 10 seconds and at shutdown, atomic, mode 0600,
HMAC of address and name, fifteen-minute expiry): safer only in the one narrow case above.

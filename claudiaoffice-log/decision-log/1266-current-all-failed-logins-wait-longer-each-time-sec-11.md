---
id: D1266
title: "Failed logins wait longer each time, per address and per document and name, without a lock-out (SEC-11)"
status: current
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1266 · Failed logins wait longer each time, per address and per document and name, without a lock-out (SEC-11)

**Decided by the owner 2026-11-19 (the proposal accepted; "see SEC-11 as part of this work"). Not built.** The queue caps
bound how many sockets wait to be let in (SEC-02), but nothing slows a patient guesser who fails, reconnects and tries
again. With the hashing cost raised (D1267) one bad login per second would also keep the server's hashing busy, so this
comes before, or with, the new cost.

- **What is counted.** Failures per *address*, which a success from that address resets, and per *(document id, name as
  typed)*, counted whether or not the document or the name exists, so the answer still tells nothing (D50, SEC-04). Kept
  in memory only and forgotten after fifteen minutes without a failure.
- **The wait.** The first three failures are free; then 1, 2, 4, 8 and 16 seconds, and never more than 30 seconds for an
  address and **10 seconds for a (document, name)**, so that a stranger who keeps guessing a colleague's name can delay
  her by 10 seconds at most. These are starting values; they are server settings and are tuned with the back-off scenario.
- **How it is said.** A login inside its wait is refused before any hashing, so a guesser costs the server nothing, with
  the close code or error `retry_after` carrying the seconds. The web and desktop login say "Too many tries. Try again in
  N seconds." and count down.
- **Where it applies.** The document `hello` (password and recovery key) and the administrator's sign-in
  (`POST /api/admin/login`).
- **No lock-out, ever.** Nothing locks a document or a name for good, because that would let anybody lock the owner out.
- **Which address.** The socket's, or behind a proxy the one the proxy appended (D1275, undecided); until that is decided
  the wait is only safe on a server that is not behind a proxy.
- **Shared addresses** (a school, an office behind one address) get the benefit of the reset on success; if they still
  run into it the server setting is raised for them.

**Notes.** Closes SEC-11 and the last item of E2.7. The thresholds count failures, not sockets, and are independent of
`max_waiting_per_address`.

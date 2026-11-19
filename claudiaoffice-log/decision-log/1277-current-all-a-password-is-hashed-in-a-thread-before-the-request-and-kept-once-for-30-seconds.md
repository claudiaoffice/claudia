---
id: D1277
title: "A password is hashed in a thread before the request that needs it, and the result is kept once for 30 seconds"
status: current
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1277 · A password is hashed in a thread before the request that needs it, and the result is kept once for 30 seconds

**Decided while building slice A (SEC-21); proposed to the owner in the patch notes, built.** With the hashing at 0.75 s
(D1267), a request that confirms a password (`set_details`, `download_claudia`, `change_password`, `add_user`, `leave`,
`delete_document`, `propose_owner`, `accept_owner`) would stop every connection of the server for that long if it hashed in
`Connection.handle`, which runs on the event loop, and a person with a password could do it in a loop.

**The choice.** The request's methods say which parameters are passwords (`hashes=` on `MethodTable.method`). Before the
gateway hands such a frame to `Connection.handle`, it hashes them in a worker thread, behind the same cap of two as the
logins (SEC-03). The result goes into a small cache in `claudia_container.crypto` and the call that follows takes it.

**What the cache is.** One-shot (taken away by the first use), at most 30 seconds old, at most 64 entries (the oldest go
first), filed under an HMAC of password, normalised name, document salt and cost with a key that exists only in the
running process. It holds the *derived* login material (a locator and a key-encryption key), never the password or the
name. A call that does not find it hashes as before, so a directory without `warm` still works.

**Consequences.**

- The process holds, for up to 30 seconds and until it is used, what is needed to open one slot of one document. Whoever
  can read the server's memory could read the keys of an open document anyway (the operator sees plaintext while a
  document is open, D100); the threat model says it in one sentence.
- A request that fails before it reaches the hash (a text too long, say) leaves one entry to expire.
- Wrong passwords are hashed once, in the thread, and are subject to the same cap, so the server is not stopped by a
  flood of them and the cap bounds how many hash at once.

**Rejected.** Making the handlers asynchronous (a change to every method's signature and to the dispatch for a handful of
methods); one worker per connection (no cap on memory, the Argon2id run needs 64 MiB and more).

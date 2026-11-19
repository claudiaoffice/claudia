---
id: D1275
title: "Behind a proxy, the address of a login is the one the proxy appended"
status: undecided
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1275 · Behind a proxy, the address of a login is the one the proxy appended

**Proposed 2026-11-19 while planning D1266; waits for the owner. Not built.**

**The problem.** The server takes an address from the socket (`websocket.client.host`, in `Gateway.serve`). With
`--behind-proxy`, which the demo and every Docker deployment behind TLS termination use, that is the proxy's address for
everybody. A per-address wait (D1266) would then be one wait for the whole server: one guesser slows every person who logs
in. The same flaw already weakens the per-address cap of SEC-02 (`max_waiting_per_address`).

**The proposal.** With `--behind-proxy`, the address of a connection is the right-most entry of `X-Forwarded-For`, the one
the nearest proxy appended, because an entry further left can be written by the client. A setting says how many proxies
are trusted (default 1). Without `--behind-proxy` the header is ignored, and the socket's address stays the only one.
Pages that report the address (the banner, the logs) say which they use.

**Notes.** Needs the proxy to set the header: Caddy and nginx do by default, a bare TCP proxy does not, and then the
server says in its log that the header is missing instead of falling back to the proxy's address silently.

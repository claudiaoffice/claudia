---
id: D1275
title: "Behind a proxy, the address of a login is the one the proxy appended"
status: current
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1275 · Behind a proxy, the address of a login is the one the proxy appended

**Decided by the owner 2026-11-19 ("D1275 ok"). Built on branch `e2-document-sec` as a bug fix of SEC-02, ahead of the back-off
(D1266) that needs it.**

**The problem.** The server takes an address from the socket (`websocket.client.host`, in `Gateway.serve`). With
`--behind-proxy`, which the demo and every Docker deployment behind TLS termination use, that is the proxy's address for
everybody. A per-address wait (D1266) would then be one wait for the whole server: one guesser slows every person who logs
in. The same flaw already weakens the per-address cap of SEC-02 (`max_waiting_per_address`).

**The decision.** With `--behind-proxy`, the address of a connection is the right-most entry of `X-Forwarded-For`, the one
the nearest proxy appended, because an entry further left can be written by the client. A setting, `--proxy-hops N`, says how many
proxies are trusted (default 1; 0 counts by the socket and ignores the header). Without `--behind-proxy` the header is ignored, and the socket's address stays the only one.
Pages that report the address (the banner, the logs) say which they use.

**Notes.** Needs the proxy to set the header: Caddy and nginx do by default, a bare TCP proxy does not, and then the
server says in its log that the header is missing instead of falling back to the proxy's address silently.

**Built.** `claudia_server/client_address.py` (`ClientAddress`, `forwarded_address`): the entry N places from the right, and only
if it is an IP address; a missing, short or bad header counts the proxy's own address and is said once in the log.
`Gateway` and the three HTTP endpoints that count an address (lookup, upload, WebSocket) use it; the health answer keeps
the raw socket address on purpose (it decides whether the caller is on this computer). The start-up banner says how
people are counted. Tests: `test_server_client_address.py`, `test_server_cli.py`, `test_server_uid.py`. Not run: a real
proxy (Caddy, nginx) in front of a real server.

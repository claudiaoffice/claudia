---
id: D1372
title: "The banner gives a link that carries the setup code in its fragment; the page takes it from there and forgets the address"
status: current
applies-to: all
date: 2026-11-20
round: "SEC-12: the first administrator needs a setup code (branch sec-12-setup-code)"
supersedes: []
superseded-by: []
---

# D1372 · The banner gives a link that carries the setup code in its fragment; the page takes it from there and forgets the address

**Decided 2026-11-20** (mock-up panels 1 and 3).

- When the server serves the web app (`--web`), the banner adds `or open <scheme>://<name>[:port]/admin#setup=<code>`:
  the first name the server answers to, https behind a proxy or with TLS, and no port behind a proxy (the proxy's port
  is not known). Without the web app it gives the code only.
- The code is in the **fragment**, which a browser never sends: neither the server nor a proxy logs it.
- The page takes it at start on any route (`lib/setup-code.ts`), removes the fragment at once with
  `history.replaceState` so it is not bookmarked or shared, and keeps the code for this tab only (`sessionStorage`,
  guarded; in memory where storage throws). It is dropped once an administrator exists.
- On the setup page a code from a link is shown filled in and is checked first (`POST /api/admin/setup-code`, 204 or
  403; a try in the sense of D1371), with "From the link you opened" and "Use another code".

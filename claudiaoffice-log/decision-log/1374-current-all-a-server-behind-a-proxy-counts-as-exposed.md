---
id: D1374
title: "A server behind a proxy counts as exposed, whatever address it listens on"
status: current
applies-to: all
date: 2026-11-20
round: "SEC-12: the first administrator needs a setup code (branch sec-12-setup-code)"
supersedes: []
superseded-by: []
---

# D1374 · A server behind a proxy counts as exposed, whatever address it listens on

**Decided 2026-11-20** (found while drawing the SEC-12 mock-up, panel 6).

"Exposed" (D152) meant only that `--host` is not a loopback address. A server on 127.0.0.1 with `--behind-proxy`
is reached through the proxy from everywhere. It now counts as exposed (`hosts.is_exposed(host, behind_proxy)`):
the setup page uses its exposed wording, and the banner asks for an administrator. Since D1370 the code is needed in
either case; this decision is about what the page and the banner say.

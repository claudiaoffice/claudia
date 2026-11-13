---
id: D244
title: "Plain http is only for this computer; a bare host means https"
status: current
applies-to: all
date: 2026-11-10
round: "E5.8 Linux client: three apps, other servers, HTTPS"
supersedes: []
superseded-by: []
---

# D244 · Plain http is only for this computer; a bare host means https

**An address names one origin. `http` is accepted only for loopback addresses; a bare `host[:port]` means `https`; everything else is refused with the reason.**

**Notes.** A typing slip must never send a password or a document over a network unencrypted. The web start page builds an `http://` address from the page it is on (the local server is plain http), so the shell does not take the page's scheme as a hint. Open point: a bare `localhost:8420` means https, which fails against a plain local server; the person types `http://localhost:8420`. Refusal confirmed by the owner on 2026-11-10.

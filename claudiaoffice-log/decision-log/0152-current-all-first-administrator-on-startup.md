---
id: D152
title: "A server that is exposed beyond loopback and has no administrator yet asks for one once, on start-up, and never again once one exists"
status: current
applies-to: all
date: 2026-11-07
round: "Server administrators and settings (twenty-seventh round)"
supersedes: []
superseded-by: []
---

# D152 · A server that is exposed beyond loopback and has no administrator yet asks for one once, on start-up, and never again once one exists

**A server that is exposed beyond loopback and has no administrator yet asks for one once, on start-up, and never again once one exists.** `needs_administrator(exposed, admin_count) = exposed and admin_count == 0`, reusing the loopback signal D103 already uses for the access secret.

**Notes.** A server that only ever runs on loopback (the common single-user case) is never asked, matching D103's existing "creation otherwise only from loopback" carve-out. Exposure is checked once per decision, not watched continuously: a server that later becomes exposed with an administrator already in place is not re-prompted, and one that starts exposed and gains an administrator is never asked a second time even if it is restarted still exposed.

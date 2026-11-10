---
id: D109
title: "Password rules"
status: current
applies-to: all
date: 2026-11-02
round: "Document container and encryption (seventeenth round)"
supersedes: []
superseded-by: []
---

# D109 · Password rules

**Password rules.** At least 8 characters, containing capital letters, small letters and digits, checked at creation and at every change. Argon2id cost set so one login takes about half a second on the reference machine; the cost is stored in the manifest so it can be raised; a server-wide cap limits how many hashes run at once.

**Notes.** Claude's standing note: against an attacker holding the file, length matters more than composition, and 8 characters is the weak point. **Open:** the measured default is about 0.09–0.4 s, not 0.5 s; a `calibrate(target_seconds)` was proposed and not decided.

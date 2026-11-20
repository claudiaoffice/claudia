---
id: D1375
title: "--reset-administrators removes the administrators only; settings, documents and fonts stay, and the next administrators are told"
status: current
applies-to: all
date: 2026-11-20
round: "SEC-12: the first administrator needs a setup code (branch sec-12-setup-code)"
supersedes: []
superseded-by: []
---

# D1375 · --reset-administrators removes the administrators only; settings, documents and fonts stay, and the next administrators are told

**Decided 2026-11-20** by the owner (mock-up panels 7 and 8).

- **A start option**, so only someone who can start the server (its console, its service, its container) can use it.
  It runs before the server listens.
- **Removed:** the administrator accounts. `admins.json` is moved aside as
  `admin/admins-before-reset-<UTC time>.json` (same permissions), so a mistaken reset can be undone by hand while the
  server is stopped; the server never tidies these files away (owner, review of 2026-11-20). Their sessions are only
  in memory and end with any restart.
- **Kept as they are:** `settings.json` (the document cap, the access secret, the AI model and device, the LaTeX and
  rendering tools, the password-hashing cost), the fonts and who may receive them, and the record of who last changed
  each setting, which keeps the old names. **Not touched:** documents, their people, passwords and recovery keys;
  server administrators have no way into them anyway.
- **Why keep the settings:** whoever can start the server can already read `settings.json` (the access secret
  included) and start it with any option. Throwing the settings away would lose configuration and protect nothing.
- **Then:** nobody is named, so a new setup code is made (D1371), unless `--admin` names one in the same start (D1376).
- **A trace:** the banner of that start (only that one) says `administrators reset: anna, ben removed`, and
  `admin/reset.json` keeps when and whom.
  Access & documents ▸ Administrators shows every administrator "Administrators were reset from the server's console
  on <date> (previously …). If they should no longer know the access secret, rotate it below." until one of them
  dismisses it (`DELETE /api/admin/reset-note`). Rotating stays the administrator's choice: it means everyone needs
  the new secret.

---
id: D246
title: "hello.app is optional"
status: current
applies-to: all
date: 2026-11-10
round: "E5.8 Linux client: three apps, other servers, HTTPS"
supersedes: []
superseded-by: []
---

# D246 · hello.app is optional

**Proposed: a page that does not yet know which app its server runs may send `hello` without `app`; the shell takes it to be its own.**

**Notes.** A server that keeps `/api/docs` behind an access secret does not say which app it runs before a login, yet its start page still needs the shell (to show the Servers list and get back). Making a field optional is compatible for the page and for new shells; an old shell answers `bad_message` and the page then works as in a browser. Shell contract README and schema are changed accordingly.

**Checked against the code, 2026-11-17 (`main` at `6814bac`).** Built as proposed: the shells accept a `hello` without `app` (`clients/linux/src/claudia_shell_gtk/contract.py`, `clients/neutralino/src/contract.ts`, the shell contract schema). The owner made the code the record of what is decided (log audit of 2026-11-17), so the status is current; replace it with a new decision to change it.

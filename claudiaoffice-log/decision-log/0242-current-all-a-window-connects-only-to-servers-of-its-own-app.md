---
id: D242
title: "A window connects only to servers of its own app"
status: current
applies-to: all
date: 2026-11-10
round: "E5.8 Linux client: three apps, other servers, HTTPS"
supersedes: []
superseded-by: []
---

# D242 · A window connects only to servers of its own app

**A window of one app connects only to servers that run the same app.**

**Notes.** Checked from `/api/docs` (`app`) before the window switches, and again by the page's `hello` (D121 bridge) when it loads, for servers that keep their listing behind a secret. A server of another app is refused with a message naming both apps. This keeps the client simple: no window ever has to show a document of an app it has no manifest for. Confirmed by the owner on 2026-11-10.

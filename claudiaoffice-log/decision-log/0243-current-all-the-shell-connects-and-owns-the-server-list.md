---
id: D243
title: "The shell connects to other servers and keeps the list of servers"
status: current
applies-to: all
date: 2026-11-10
round: "E5.8 Linux client: three apps, other servers, HTTPS"
supersedes: []
superseded-by: []
---

# D243 · The shell connects to other servers and keeps the list of servers

**The page asks the shell to connect (`connect`); the shell checks the server and shows it in the same window; the shell, not the page, keeps one list of servers per app, with "This computer" first when the window started a server.**

**Notes.** D102's origin lock stays: the view never leaves the server it shows, so a page that navigated to another server itself was handed to the person's browser (the bug that started this). The page's `localStorage` is per origin and so cannot hold a list that spans servers. `--server URL` starts no local server, saves the address to the list and applies the same checks. Messages `connect`, `connect_failed` and `servers` are additive to contract v1. The list is `shell.json` (`servers`, per app), sanitized on every read and write, at most 64 entries. Confirmed by the owner on 2026-11-10.

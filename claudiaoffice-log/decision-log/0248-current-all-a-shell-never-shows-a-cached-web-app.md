---
id: D248
title: "A page is never taken from a cache: the server revalidates, the shell empties its cache"
status: current
applies-to: all
date: 2026-11-10
round: "E5.8 Linux client: three apps, other servers, HTTPS"
supersedes: []
superseded-by: []
---

# D248 · A page is never taken from a cache: the server revalidates, the shell empties its cache

**The server answers every file of the web app with a `Cache-Control` (pages and files not named by their content: `no-cache`; content-hashed files under `_nuxt/`: kept for good). The Linux shell, independently, empties WebKit's page cache before it loads a server's page.**

**Notes.** Seen on 2026-11-10: after the demo server was updated, the desktop client still showed the previous web app (four menus, the old connection indicator, no shell contract, so the native menus stayed disabled) while a browser showed the new one. The shell contract needs the shell and the page to be the same generation, so a stale page is a functional bug, not a cosmetic one. Both sides are needed: the header protects every client of every server from now on; the shell's own rule also covers servers that were deployed before the header existed. Cost: the page's files are downloaded again on each window start and connect (`_nuxt/` is small); revalidation with an ETag is cheap otherwise. The WebKit part (`WebPage._load_current`) is covered by gtk tests that were written but not run where it was made.

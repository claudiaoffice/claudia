---
id: D170
title: "Moving between bookmarked servers, opening a bookmarked server's settings, and leaving the settings pages are always a full `location.href` navigation to…"
status: current
applies-to: all
date: 2026-11-07
round: "Server settings, frontend half (thirtieth round)"
supersedes: []
superseded-by: []
---

# D170 · Moving between bookmarked servers, opening a bookmarked server's settings, and leaving the settings pages are always a full `location.href` navigation to…

**Moving between bookmarked servers, opening a bookmarked server's settings, and leaving the settings pages are always a full `location.href` navigation to that server's own origin — never an in-page cross-origin fetch.** Extends D115's "page and socket share one origin" from the Linux shell's loopback case to the web app's own multi-server bookmark list.

**Notes.** Consequence (D171): nothing in the current page can check whether the *viewer* is an administrator of a *different*, bookmarked server without violating this rule.

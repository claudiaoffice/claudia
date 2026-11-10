---
id: D169
title: "The settings pages are reached by one `location.pathname` check (`/admin` or `/admin/…`) inside the existing single-file `app.vue`, not a router"
status: current
applies-to: all
date: 2026-11-07
round: "Server settings, frontend half (thirtieth round)"
supersedes: []
superseded-by: []
---

# D169 · The settings pages are reached by one `location.pathname` check (`/admin` or `/admin/…`) inside the existing single-file `app.vue`, not a router

**The settings pages are reached by one `location.pathname` check (`/admin` or `/admin/…`) inside the existing single-file `app.vue`, not a router.** Chosen with the owner via `AskUserQuestion`: the web app has no vue-router and never has (D117's shim-based shell adapter exists precisely because the app has no routes to drive), and adding one for a single additional screen was judged disproportionate. The check runs once at setup, since the path cannot change without a real navigation.

**Notes.** If a second routed screen is ever needed, this is the moment to introduce a real router instead of a second hand-rolled path check.

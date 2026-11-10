---
id: D176
title: "Bug fix: whether the settings pages offer becoming the first administrator is decided by `administrator === null` (nobody has ever become one), never by…"
status: current
applies-to: all
date: 2026-11-08
round: "Server settings, frontend half (thirtieth round)"
supersedes: []
superseded-by: []
---

# D176 · Bug fix: whether the settings pages offer becoming the first administrator is decided by `administrator === null` (nobody has ever become one), never by…

**Bug fix: whether the settings pages offer becoming the first administrator is decided by `administrator === null` (nobody has ever become one), never by `needs_administrator` alone.** The latter also requires the server to be exposed beyond loopback (D152), so on the common loopback-only server it stayed `false` with zero administrators — the settings pages fell straight to the sign-in form, which could never succeed, surfacing as a plain "wrong name or password". `FirstAdminSetup.vue` now takes an `exposed` prop and adapts its wording (forced phrasing when exposed; an optional, skippable offer — "Skip for now" — when not) rather than changing which screen appears.

**Notes.** Found by the owner while trying the patch for the first time: opening `/admin` on a loopback-only server with no administrator went straight to a login form with no account to log into. The one-line decision (`hasNoAdministrator`, `admin-api.ts`) is unit-tested directly, matching this codebase's usual pure-function-over-component-test style.

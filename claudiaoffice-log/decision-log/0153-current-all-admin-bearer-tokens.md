---
id: D153
title: "Administrator sessions are bearer tokens, issued on sign-in, kept only in server memory, and lazily expired — never cookies"
status: current
applies-to: all
date: 2026-11-07
round: "Server administrators and settings (twenty-seventh round)"
supersedes: []
superseded-by: []
---

# D153 · Administrator sessions are bearer tokens, issued on sign-in, kept only in server memory, and lazily expired — never cookies

**Administrator sessions are bearer tokens, issued on sign-in, kept only in server memory, and lazily expired — never cookies.** Mirrors the existing `Authorization: Bearer` precedent the access secret already uses on the document socket.

**Notes.** Chosen over a cookie-based session to avoid a CSRF surface entirely, at the cost of the client having to hold and resend the token itself (the settings dialogs' job, not yet built).

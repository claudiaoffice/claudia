---
id: D174
title: "The Access & Documents page's one shared Cancel/Apply footer governs only `max_documents`"
status: current
applies-to: all
date: 2026-11-07
round: "Server settings, frontend half (thirtieth round)"
supersedes: []
superseded-by: []
---

# D174 · The Access & Documents page's one shared Cancel/Apply footer governs only `max_documents`

**The Access & Documents page's one shared Cancel/Apply footer governs only `max_documents`** — the one setting that behaves like an editable draft. Administrators (add, remove, change password) and the access secret (toggle, reveal, rotate) each act immediately on their own button, matching their own independent REST endpoint rather than a fictional unified "Apply" for the whole page. The signed-in administrator's own row hides its "Remove" button, even though the backend permits self-removal when not the last admin.

**Notes.** Self-removal mid-session is allowed by the backend but confusing in the UI (signing yourself out from under yourself); hiding it is a UI-only guard, not a new backend rule.

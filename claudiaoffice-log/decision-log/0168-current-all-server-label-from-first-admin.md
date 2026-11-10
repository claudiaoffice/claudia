---
id: D168
title: "The label shown for a server (TopBar indicator, Open dialog sidebar, admin shell) is derived from its first administrator's name, reported by…"
status: current
applies-to: all
date: 2026-11-07
round: "Server settings, frontend half (thirtieth round)"
supersedes: []
superseded-by: []
---

# D168 · The label shown for a server (TopBar indicator, Open dialog sidebar, admin shell) is derived from its first administrator's name, reported by…

**The label shown for a server (TopBar indicator, Open dialog sidebar, admin shell) is derived from its first administrator's name, reported by `/api/admin/status`; a person may override it with a rename that lives only in that browser's bookmark and is never sent to the server.** Chosen with the owner via `AskUserQuestion` over a server-supplied display name field (would need new backend state) or the bare host/port (less legible with several servers bookmarked).

**Notes.** `friendlyLabel()` falls back to the bare host whenever no bookmark and no administrator name exist yet (a brand-new, unconfigured server). The rename is deliberately client-side-only: two people bookmarking the same server may see different labels, which is accepted as the cost of needing no new backend concept.

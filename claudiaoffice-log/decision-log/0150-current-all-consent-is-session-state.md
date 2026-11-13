---
id: D150
title: "The consent itself — who must agree, the open proposal, the policy for silence at the deadline — is session state, not document state, and lives in…"
status: current
applies-to: all
date: 2026-11-07
round: "Restore with consent, and the line picker (twenty-sixth round)"
supersedes: []
superseded-by: []
---

# D150 · The consent itself — who must agree, the open proposal, the policy for silence at the deadline — is session state, not document state, and lives in…

**The consent itself — who must agree, the open proposal, the policy for silence at the deadline — is session state, not document state, and lives in `claudia-server` (a new `RestoreCoordinator`), not the kernel.** Every wire method it needs sits on the shared `core_methods` table, the same table `history`/`chat`/`lines` already sit on, so composes and creates get restore-with-consent for free the same way they already get history and chat.

**Notes.** Consistent with D51/D52: the kernel already restores and switches outright (`restore_checkpoint`, `switch_to`); nothing about *whether it is allowed to happen right now* belongs in a document that might be opened by a batch job or a single person with nobody to ask. `RestoreCoordinator` is plain, dependency-free Python (27 tests in isolation, no kernel, no sockets) owned by `HostedDocument`, exactly as ephemeral as presence and locks: an open proposal and the one-time "what happened while you were away" notice live only as long as the document is held open in memory, with nothing to recover after a restart. Reached from the stateless wire methods through `Context`, the same injection pattern already used for `users` and `directory`. The frontend mirrors the placement: the new session methods and the consent banner live in `base-session.ts`/`SidePanel.vue`, the layer every app already shares for history and chat, not duplicated per app.

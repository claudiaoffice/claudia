---
id: D142
title: "Handing over ownership is a two-password handshake, not a single action"
status: current
applies-to: all
date: 2026-11-06
round: "The Manage menu: leaving, handing over ownership, exporting and deleting (twenty-third round)"
supersedes: []
superseded-by: []
---

# D142 · Handing over ownership is a two-password handshake, not a single action

**Handing over ownership is a two-password handshake, not a single action.** The current owner proposes with their own password and the new owner's name; the new owner must already be an editor; the new owner then accepts with their own password, inside a time window.

**Notes.** A person's role is baked inside their own password-sealed slot (D101); changing it means re-deriving the sealing key from that person's *current* password, which only that person's own password can do. This is also why a role change could not previously be done without remove-and-re-add.

---
id: D1499
title: "A document has one owner, but the consent specs and texts say the owners"
status: undecided
applies-to: all
date: 2026-11-22
round: "E7.11 Claude as an AI provider (branch e7-11-claude-provider)"
supersedes: []
superseded-by: []
---

# D1499 · A document has one owner, but the consent specs and texts say the owners

**Open; found while writing the end-to-end steps 2026-11-22.**

`add_user` refuses the role `owner`, and ownership is handed over (`propose_owner`; the old owner becomes an editor). So the
scenarios that need two owners ("Jonas is an owner and Ben is an editor", "Only the owners can change this: Anna and Jonas",
"Jonas switches Claude off while Anna's question runs") cannot be set up, and are skipped with their words.
The dialog, the server and the page already handle any number of owners (`owners` is a list).

**Options.** (a) Documents get more than one owner (a larger change to roles, passwords and keys). (b) Keep one owner and
change the texts to "the owner" and the scenarios to one owner plus an editor who is refused. **Recommendation: (b)** until
there is a story for co-owners; the two scenarios that need Jonas then use Anna as the one who switches Claude off.

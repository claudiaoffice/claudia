---
id: D1499
title: "A document has one owner, and the consent specs and texts say the owner"
status: current
applies-to: all
date: 2026-11-23
round: "E7.11 Claude as an AI provider (branch e7-11-claude-provider)"
supersedes: []
superseded-by: []
---

# D1499 · A document has one owner, and the consent specs and texts say the owner

**Decided 2026-11-23 by the owner: option (b).** Found while writing the end-to-end steps 2026-11-22.

`add_user` refuses the role `owner`, and ownership is handed over (`propose_owner`; the old owner becomes an editor). So the
scenarios that need two owners ("Jonas is an owner and Ben is an editor", "Only the owners can change this: Anna and Jonas",
"Jonas switches Claude off while Anna's question runs") cannot be set up, and are skipped with their words.
The dialog, the server and the page already handle any number of owners (`owners` is a list).

**Options.** (a) Documents get more than one owner (a larger change to roles, passwords and keys). (b) Keep one owner and
change the texts to "the owner" and the scenarios to one owner plus an editor who is refused. **Recommendation: (b)** until
there is a story for co-owners; the two scenarios that need Jonas then use Anna as the one who switches Claude off.

## Decision

(b): a document keeps one owner. Co-owners are not part of E7.11; they need their own story (roles, passwords, keys).

## Consequences (done in the patch on branch `d1499-one-owner`)

- The consent texts and their translations say "the owner" instead of "the owners" (the dialog, the refusal, the badge
  line "Only the owner can change it.", the English source strings and every catalogue).
- The scenarios in `specs/document-file/ai-consent.feature` and `specs/server/claude-answers.feature` that need a second
  owner are rewritten to one owner plus an editor who is refused; the scenario "Jonas switches Claude off while Anna's
  question runs" uses Anna. They stop being skipped with their words.
- The server and the dialog keep handling a list of owners; nothing is removed from them.

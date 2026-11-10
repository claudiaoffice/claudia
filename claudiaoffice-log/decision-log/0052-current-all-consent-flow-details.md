---
id: D52
title: "Details of the consent flow"
status: current
applies-to: all
date: 2026-11-02
round: "Live sessions (seventh round)"
supersedes: []
superseded-by: []
---

# D52 · Details of the consent flow

**Details of the consent flow.** (1) *Who is asked:* connected owners and editors. Viewers are told, never asked, never block. `ai` is never asked and never blocks; its running jobs are cancelled or marked stale. A sole editor restores at once. (2) *How a vote ends:* any "no" ends it; one open proposal per document; the proposer may withdraw; an unanswered proposal expires after a fixed time (two minutes to start with). (3) *Coming and going:* someone who disconnects is no longer asked; an editor who connects is added and asked. (4) *Work during the vote:* editing continues; on restore, edits in flight are refused with `stale` (D49) and the banner offers to copy what was refused; locks and presence are cleared. (5) *Switching back to a hidden line* follows the same flow. (6) *Users who were away* get a notice on return.

**Notes.** The two-minute expiry is a starting value. Implementation: E3.7, not started.

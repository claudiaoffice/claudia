---
id: D143
title: "A proposed transfer lives only in server memory, for five minutes by default, and is used at most once"
status: current
applies-to: all
date: 2026-11-06
round: "The Manage menu: leaving, handing over ownership, exporting and deleting (twenty-third round)"
supersedes: []
superseded-by: []
---

# D143 · A proposed transfer lives only in server memory, for five minutes by default, and is used at most once

**A proposed transfer lives only in server memory, for five minutes by default, and is used at most once** — popped on the first accept attempt whether it succeeds or fails.

**Notes.** Keeping the old owner's plaintext password briefly in memory is a deliberate, precedented tradeoff: `sealed.py` already holds raw domain keys in memory the same way between login and open.

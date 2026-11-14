---
id: D288
title: "The search engine runs on `regex` with a deadline, in its own package claudia-search"
status: current
applies-to: all
date: 2026-11-13
round: "Search & replace in all three apps (branch `regex-builder`); QA follow-up SEC-18"
supersedes: []
superseded-by: []
---

# D288 · The search engine runs on `regex` with a deadline, in its own package claudia-search

**Patterns run on the `regex` package, and every call that runs one takes a deadline.** A search request has one
deadline (two seconds in computes, `SEARCH_SECONDS`); each call gets what is left of it as `regex`'s `timeout` and
stops inside the pattern when it passes. The answer then says `timed_out` with what was found so far; a preview says
the same, and a replace refuses rather than replace part of what was asked. Without a deadline a call may take one
second (`MAX_SECONDS`). Patterns are still **read by Python's `re` first**: the syntax a person is told is Python's
(D284), and `re` names a mistake where it is, in the words the clients explain; `regex` (version 0 syntax) reads them
the same way. `regex`-only syntax (`\p{L}`, variable look-behind) is therefore refused for now.

**The engine moved out of claudia-core into a new package, claudia-search** (the engine, plus the app-neutral search
over a document's texts, D289). The kernel imports the standard library only (CONTRIBUTING, rule 6), and `regex` is
not part of it; claudia-core 0.19.0 no longer has `Query`, `CompiledSearch`, `Match` or `SearchError`.

**Notes.** Answers D287 (2). Decided by the owner on 2026-11-13 ("we'll use the regex package"; the new package
chosen over amending rule 6 or injecting a matcher into the kernel). *Why:* QA found (SEC-18) that the shape guard of
D284's as-built note let exponential patterns through: `(a|a?)+!` ran 12.5 s on 24 characters, doubling per character,
on the event loop, so one request from anybody who could open a document stopped the whole server. A guard that
recognises dangerous shapes is a guess that misses some and refuses harmless ones; a deadline is not a guess. The
alternative D284 named, the worker pool with a hard kill, would also have worked but costs a process hop per request
and pickling the workbook's texts. *Licence:* `regex` is Apache-2.0 AND CNRI-Python (the latter for code derived from
Python's own `sre`), both GPL-compatible as far as the project knows; worth confirming with the licence review.
*Kept:* the size caps of D284 (pattern length, parts, conditions); the shape guard is gone.

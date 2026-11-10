---
id: D92
title: "The typesetting API is authenticated wire methods"
status: current
applies-to: composes
date: 2026-11-03
round: "Fonts and typesetting services (sixteenth round)"
supersedes: []
superseded-by: []
---

# D92 · The typesetting API is authenticated wire methods

**The typesetting API is authenticated wire methods** (submit, status, cancel), not an open HTTP endpoint; **v1 uses its own small subprocess runner** behind `run_sandboxed`, which the worker pool of E3.5 replaces later.

**Notes.** Fonts for browsers are the exception: public, immutable, behind the host guard. **The wire methods do not exist yet.**

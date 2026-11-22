---
id: D1451
title: "A spec file waiting for the owner's review carries @draft on its Feature line; approving and binding it is one commit"
status: current
applies-to: all
date: 2026-11-22
round: "E2E guard (E11.8, branch e2e-guard)"
supersedes: []
superseded-by: []
---

# D1451 · A spec file waiting for the owner's review carries `@draft`

**Proposed 2026-11-22, agreed by the owner 2026-11-22.**

Scenarios are written before the owner approves them (D1241), and step code only after. Without a mark, a draft looks
like an approved file nobody runs, and D1450 would fail CI for every draft. So a draft says so: `@draft` on its
`Feature:` line. D1450 lets a draft through; `tests/test_specs_are_bound.py` fails when a file is bound and still
`@draft`. When the owner approves a draft, `@draft` comes off: the commit binds the file to step code, or, when no
step code is written yet, puts the file into `NOT_BOUND_YET` with its story (D1450).

The owner finds what waits for review with `grep -rl "^@draft" claudiaoffice-log/specs`. The first draft marked so was
`objects/the-same-in-all-three-apps.feature` (2026-11-21, D1431, D1432, CODE-75); the owner approved it on 2026-11-22
without its chart-tab scenario, and it waits in `NOT_BOUND_YET` for step code.

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
`@draft`, so the commit that binds an approved file is the one that takes `@draft` off.

The owner finds what waits for review with `grep -rl "^@draft" claudiaoffice-log/specs`. The first draft marked so is
`objects/the-same-in-all-three-apps.feature` (2026-11-21, D1431, D1432, CODE-75).
